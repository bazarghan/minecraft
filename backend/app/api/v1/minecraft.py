import asyncio

from fastapi import APIRouter

from ...deps import CurrentUser
from ...services.minecraft_versions import get_version_catalog


router = APIRouter(prefix="/minecraft", tags=["Minecraft versions"])


@router.get("/versions")
async def minecraft_versions(_: CurrentUser):
    return await asyncio.to_thread(get_version_catalog)
