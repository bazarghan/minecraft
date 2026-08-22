import asyncio
import logging
import re
import time
from html.parser import HTMLParser
from urllib.parse import quote, urljoin

import httpx


logger = logging.getLogger("minecraft_manager.hielke_catalog")

BASE_URL = "https://hielkemaps.com"
CATALOG_TTL_SECONDS = 15 * 60
CATALOG_PAGES = {
    "official": f"{BASE_URL}/maps/",
    "community": f"{BASE_URL}/community-maps/",
}

FALLBACK_MAPS = (
    ("Parkour Volcano", "parkour-volcano"),
    ("Parkour Egg", "parkour-egg"),
    ("Parkour Town", "parkour-town"),
    ("Parkour Spiral", "parkour-spiral"),
    ("Parkour Spiral 2", "parkour-spiral-2"),
    ("Parkour Spiral 3", "parkour-spiral-3"),
    ("Parkour Paradise", "parkour-paradise"),
    ("Parkour Paradise 2", "parkour-paradise-2"),
    ("Parkour Paradise 3", "parkour-paradise-3"),
    ("Dimension Parkour", "dimension-parkour"),
    ("Parkour Pyramid", "parkour-pyramid"),
)

_cache: tuple[float, list[dict[str, str]], str] | None = None
_cache_lock = asyncio.Lock()


def _absolute_url(value: str) -> str:
    absolute = urljoin(f"{BASE_URL}/", value.replace("/media//", "/media/"))
    return quote(absolute, safe=":/?=&%")


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


class _MapCardParser(HTMLParser):
    def __init__(self, category: str) -> None:
        super().__init__(convert_charrefs=True)
        self.category = category
        self.items: list[dict[str, str]] = []
        self.card: dict[str, str] | None = None
        self.card_depth = 0
        self.capture: str | None = None
        self.capture_parts: list[str] = []
        self.badges: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        classes = set(attributes.get("class", "").split())
        if tag == "div" and "mapcard" in classes and self.card is None:
            self.card = {}
            self.card_depth = 1
            self.badges = []
            onclick = attributes.get("onclick", "")
            match = re.search(r"location\.href=['\"]([^'\"]+)", onclick)
            if match:
                self.card["page_path"] = match.group(1)
            return
        if self.card is None:
            return
        if tag == "div":
            self.card_depth += 1
        if tag == "img" and "card-img-top" in classes:
            self.card["thumbnail_url"] = _absolute_url(attributes.get("src", ""))
        elif tag == "h4" and "card-title" in classes:
            self._start_capture("name")
        elif tag == "p" and "card-text" in classes:
            self._start_capture("description")
        elif tag == "small":
            self._start_capture("version")
        elif tag == "span" and "badge" in classes:
            self._start_capture("badge")
        elif tag == "a" and attributes.get("href", "").lower().endswith(".zip"):
            self.card["download_url"] = _absolute_url(attributes["href"])

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.capture_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.card is None:
            return
        capture_tags = {"name": "h4", "description": "p", "version": "small", "badge": "span"}
        if self.capture and capture_tags[self.capture] == tag:
            value = " ".join("".join(self.capture_parts).split())
            if self.capture == "badge":
                self.badges.append(value)
            elif value:
                self.card[self.capture] = value
            self.capture = None
            self.capture_parts = []
        if tag == "div":
            self.card_depth -= 1
            if self.card_depth == 0:
                self._finish_card()

    def _start_capture(self, field: str) -> None:
        self.capture = field
        self.capture_parts = []

    def _finish_card(self) -> None:
        assert self.card is not None
        name = self.card.get("name", "")
        page_path = self.card.get("page_path", "")
        if self.category == "official" and not page_path.startswith("/maps/"):
            self.card = None
            return
        if name:
            version = self.card.get("version", "")
            for badge in self.badges:
                if badge.startswith("Java "):
                    version = badge.removeprefix("Java ")
                    break
            slug = page_path.rstrip("/").rsplit("/", 1)[-1] if page_path else _slugify(name)
            download_url = self.card.get("download_url")
            if not download_url:
                download_url = f"{BASE_URL}/downloads/{quote(name, safe='')}.zip"
            page_url = _absolute_url(page_path or CATALOG_PAGES[self.category])
            self.items.append(
                {
                    "id": f"{self.category}:{slug}",
                    "slug": slug,
                    "name": name,
                    "description": self.card.get("description", ""),
                    "author": "Hielke Maps" if self.category == "official" else "Hielke Maps community",
                    "minecraft_version": version.removeprefix("Java "),
                    "download_url": download_url,
                    "page_url": page_url,
                    "thumbnail_url": self.card.get("thumbnail_url", ""),
                    "category": self.category,
                }
            )
        self.card = None


def parse_hielke_catalog(html: str, category: str) -> list[dict[str, str]]:
    if category not in CATALOG_PAGES:
        raise ValueError("Unsupported HielkeMaps catalog category")
    parser = _MapCardParser(category)
    parser.feed(html)
    return parser.items


def _fallback_catalog() -> list[dict[str, str]]:
    return [
        {
            "id": f"official:{slug}",
            "slug": slug,
            "name": name,
            "description": "",
            "author": "Hielke Maps",
            "minecraft_version": "26.2",
            "download_url": f"{BASE_URL}/downloads/{quote(name, safe='')}.zip",
            "page_url": f"{BASE_URL}/maps/{slug}",
            "thumbnail_url": f"{BASE_URL}/media/maps/{slug}/thumbnail-compressed.jpg",
            "category": "official",
        }
        for name, slug in FALLBACK_MAPS
    ]


async def _fetch_catalog() -> list[dict[str, str]]:
    timeout = httpx.Timeout(15, connect=5)
    headers = {"User-Agent": "MinecraftServerManager/0.1"}
    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=False, trust_env=False) as client:
        responses = await asyncio.gather(*(client.get(url) for url in CATALOG_PAGES.values()))
    items: list[dict[str, str]] = []
    for category, response in zip(CATALOG_PAGES, responses, strict=True):
        response.raise_for_status()
        items.extend(parse_hielke_catalog(response.text, category))
    if not items:
        raise ValueError("HielkeMaps catalog contained no map cards")
    return items


async def get_hielke_catalog() -> tuple[list[dict[str, str]], str]:
    global _cache
    now = time.monotonic()
    if _cache and now - _cache[0] < CATALOG_TTL_SECONDS:
        return _cache[1], _cache[2]
    async with _cache_lock:
        now = time.monotonic()
        if _cache and now - _cache[0] < CATALOG_TTL_SECONDS:
            return _cache[1], _cache[2]
        try:
            items = await _fetch_catalog()
            source = "live"
        except (httpx.HTTPError, ValueError):
            logger.warning("Could not refresh HielkeMaps catalog; using fallback", exc_info=True)
            items = _fallback_catalog()
            source = "fallback"
        _cache = (now, items, source)
        return items, source
