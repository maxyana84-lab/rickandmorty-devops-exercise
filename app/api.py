"""REST service: the same data as the script, returned as JSON (or CSV)."""
from __future__ import annotations

import os
import threading
import time
from typing import Callable

from flask import Flask, Response, jsonify

from .rickandmorty import Character, UpstreamError, find_characters, to_csv


class TTLCache:
    """Keeps the result for a while so that every request does not hit the public API."""

    def __init__(self, loader: Callable[[], list[Character]], ttl: float) -> None:
        self._loader = loader
        self._ttl = ttl
        self._lock = threading.Lock()
        self._value: list[Character] | None = None
        self._expires = 0.0

    def get(self) -> list[Character]:
        with self._lock:
            now = time.monotonic()
            if self._value is None or now >= self._expires:
                self._value = self._loader()  # raises UpstreamError, nothing is cached then
                self._expires = now + self._ttl
            return self._value


def create_app(
    loader: Callable[[], list[Character]] | None = None, cache_ttl: float | None = None
) -> Flask:
    app = Flask(__name__)
    app.json.sort_keys = False
    ttl = cache_ttl if cache_ttl is not None else float(os.environ.get("CACHE_TTL_SECONDS", "300"))
    cache = TTLCache(loader or find_characters, ttl)

    @app.get("/healthcheck")
    def healthcheck():
        # Liveness only: it must not depend on the public API being up.
        return jsonify(status="ok")

    @app.get("/characters")
    def characters():
        found = cache.get()
        return jsonify(count=len(found), characters=[c.as_dict() for c in found])

    @app.get("/characters.csv")
    def characters_csv():
        return Response(
            to_csv(cache.get()),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=characters.csv"},
        )

    @app.errorhandler(UpstreamError)
    def upstream_error(exc: UpstreamError):
        return jsonify(error=str(exc)), 502

    return app
