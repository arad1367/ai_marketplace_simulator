"""Vercel serverless entrypoint.

Vercel's Python runtime serves the ASGI ``app`` exported here. We add the
``backend`` directory to ``sys.path`` so the existing ``app`` package imports
unchanged, then re-export the FastAPI application.

Note on serverless limits: a single request runs the whole simulation and
writes its logs. Very large runs (e.g. 10 firms × 500 timesteps) can approach
the function's max duration. For heavy research runs, host the backend on a
long-running service (Render, Railway, Fly.io) and point the frontend at it via
``VITE_API_BASE_URL`` instead.
"""

import os
import sys

_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.main import app  # noqa: E402  (path setup must run first)

# Vercel looks for a module-level `app` (ASGI) — re-exported above.
__all__ = ["app"]
