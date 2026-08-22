from fastapi import APIRouter

from . import auth, backups, maps, minecraft, servers, system, users


router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(minecraft.router)
router.include_router(servers.router)
router.include_router(maps.router)
router.include_router(backups.router)
router.include_router(system.router)
