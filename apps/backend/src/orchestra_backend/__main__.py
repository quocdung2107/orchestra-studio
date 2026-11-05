from __future__ import annotations

import logging

import uvicorn

from orchestra_backend.app import create_app
from orchestra_backend.core.config import LOOPBACK_HOST, Settings


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings()
    app = create_app(settings)
    logging.getLogger("orchestra").info(
        "Backend on http://%s:%s (token file: %s)",
        LOOPBACK_HOST,
        settings.port,
        settings.token_file,
    )
    uvicorn.run(app, host=LOOPBACK_HOST, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
