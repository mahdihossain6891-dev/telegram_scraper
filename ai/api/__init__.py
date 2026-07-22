"""Isolated FastAPI router package for ``/api/ai``.

Communicate only via ``build_ai_router`` / ``AIServiceFacade``.
Routes never expose database sessions.
"""

from __future__ import annotations

from .facade import AIServiceFacade
from .routes import build_ai_router

__all__ = ["AIServiceFacade", "build_ai_router"]
