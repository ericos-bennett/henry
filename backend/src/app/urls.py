from django.contrib import admin
from django.urls import path

from app.api import api

urlpatterns = [
    path("controls/", admin.site.urls),
    path("api/", api.urls),
]
