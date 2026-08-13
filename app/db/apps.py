# filename: app/db/apps.py
"""Django AppConfig for the domain database models app."""

from pathlib import Path

from django.apps import AppConfig


class DbConfig(AppConfig):
    """Configuration for the app.db Django application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "app.db"
    verbose_name = "Eidos Domain Database Models"
    path = str(Path(__file__).resolve().parent)
