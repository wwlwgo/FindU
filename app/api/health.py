from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/v1/health")
def api_health_check(verbose: bool = False) -> dict[str, str]:
    del verbose
    return {"status": "ok"}
