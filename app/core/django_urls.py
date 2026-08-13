# filename: app/core/django_urls.py
"""Django URL routing configuration for Admin interface and Core views."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
]
