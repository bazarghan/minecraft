from app.services.hielke_catalog import parse_hielke_catalog


def test_parses_official_map_card() -> None:
    html = """
    <div class="card mapcard" onclick="location.href='/maps/parkour-paradise';">
      <img class="card-img-top" src="/media//maps/parkour-paradise/thumbnail.jpg">
      <div class="card-body">
        <h4 class="card-title">Parkour Paradise</h4>
        <span class="badge badge-secondary">Bedrock</span>
        <span class="badge badge-secondary">Java 26.2</span>
        <p class="card-text">One hundred parkour levels.</p>
      </div>
    </div>
    """

    assert parse_hielke_catalog(html, "official") == [
        {
            "id": "official:parkour-paradise",
            "slug": "parkour-paradise",
            "name": "Parkour Paradise",
            "description": "One hundred parkour levels.",
            "author": "Hielke Maps",
            "minecraft_version": "26.2",
            "download_url": "https://hielkemaps.com/downloads/Parkour%20Paradise.zip",
            "page_url": "https://hielkemaps.com/maps/parkour-paradise",
            "thumbnail_url": "https://hielkemaps.com/media/maps/parkour-paradise/thumbnail.jpg",
            "category": "official",
        }
    ]


def test_parses_community_download_link() -> None:
    html = """
    <div class="card mapcard">
      <img class="card-img-top" src="/media/community-maps/halloween-spiral.jpg">
      <div class="card-body">
        <h4 class="card-title mb-1">Halloween Spiral</h4>
        <small class="text-muted">Java 1.17.1</small>
        <a href="/downloads/community/Halloween Spiral.zip">Download</a>
      </div>
    </div>
    """

    result = parse_hielke_catalog(html, "community")

    assert result[0]["name"] == "Halloween Spiral"
    assert result[0]["minecraft_version"] == "1.17.1"
    assert result[0]["download_url"] == (
        "https://hielkemaps.com/downloads/community/Halloween%20Spiral.zip"
    )
    assert result[0]["category"] == "community"
