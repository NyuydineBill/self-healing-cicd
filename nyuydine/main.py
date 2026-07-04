"""Run the Nyuydine platform API server."""

import uvicorn

from nyuydine.config import get_platform_settings


def main() -> None:
    settings = get_platform_settings()
    uvicorn.run(
        "nyuydine.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
