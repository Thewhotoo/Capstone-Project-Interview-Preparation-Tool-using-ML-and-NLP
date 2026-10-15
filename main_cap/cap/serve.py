"""
Production server: the same app as `python app.py`, served by waitress (a
multi-threaded WSGI server that runs on Windows and Linux) instead of Flask's
development server.

    python serve.py

Settings (environment variables):
    CAP_HOST      interface to listen on            default 127.0.0.1 (0.0.0.0 in Docker)
    CAP_PORT      port                              default 5000
    CAP_THREADS   requests handled at once          default 8

Several of these processes can serve the same users only with shared state:
PostgreSQL (`CAP_DATABASE_URL`), Redis for live interviews
(`CAP_LIVE_STORE=redis`, `CAP_REDIS_URL`), the same `CAP_SECRET_KEY` (login
cookies) and the same upload folder (`CAP_UPLOAD_DIR`). See
PRODUCTION_INFRA_PROGRESS.md.
"""

import logging
import os

from waitress import serve

import model_warmup
from app import app

logger = logging.getLogger(__name__)


def main() -> None:
    host = os.environ.get("CAP_HOST", "127.0.0.1")
    port = int(os.environ.get("CAP_PORT", "5000"))
    threads = int(os.environ.get("CAP_THREADS", "8"))
    # Load every model now, in the background, so no user action waits for one.
    model_warmup.start_background_warmup()
    logger.info("Serving on http://%s:%d with %d threads", host, port, threads)
    serve(app, host=host, port=port, threads=threads)


if __name__ == "__main__":
    main()
