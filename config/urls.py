from django.contrib import admin
from django.urls import include, path

from core.views import home_view

urlpatterns = [
    path("", home_view, name="home"),
    path("home/", home_view, name="home"),
    path("", include("valuation.urls")),
    path("admin/", admin.site.urls),
]
