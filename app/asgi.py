# filename: app/asgi.py
"""Unified ASGI Dispatcher combining Django ASGI (with Static Files Handler) and FastAPI.

Routes request paths starting with '/admin' or '/django-static' to Django's ASGI handler,
and dispatches all production RESTful API and static UI traffic to FastAPI.
"""

import os
from collections.abc import Callable

import django
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.asgi import get_asgi_application

# Initialize Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.core.django_settings")
django.setup()

# Wrap Django ASGI application with Static Files Handler for admin CSS/JS rendering
django_asgi_app = ASGIStaticFilesHandler(get_asgi_application())

# Import FastAPI application after Django setup
from app.main import app as fastapi_app  # noqa: E402


class UnifiedASGIApplication:
    """ASGI Dispatcher routing requests to either Django or FastAPI based on URI prefix."""

    def __init__(self, django_app: Callable, fastapi_app: Callable) -> None:
        self.django_app = django_app
        self.fastapi_app = fastapi_app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] in ("http", "websocket"):
            path: str = scope.get("path", "")
            # Route Django Admin, Allauth accounts, and Django static files to Django ASGI handler
            if (
                path.startswith("/admin")
                or path.startswith("/accounts")
                or path.startswith("/django-static")
            ):
                await self.django_app(scope, receive, send)
                return

        # Route all other traffic (FastAPI REST endpoints, OpenAPI docs, UI) to FastAPI
        await self.fastapi_app(scope, receive, send)


application = UnifiedASGIApplication(django_app=django_asgi_app, fastapi_app=fastapi_app)
