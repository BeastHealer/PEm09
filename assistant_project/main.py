"""Web server entry point."""

import uvicorn

from utils.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "web.app:app",
        host=settings.web_host,
        port=settings.web_port,
        reload=settings.web_debug,
    )


if __name__ == "__main__":
    main()
