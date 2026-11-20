from django.contrib import admin
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from fuel import views

urlpatterns = [
    path("", views.map_page, name="map"),
    path("api/route/", views.RouteView.as_view(), name="route"),
    path("api/health/", views.health, name="health"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("admin/", admin.site.urls),
]
