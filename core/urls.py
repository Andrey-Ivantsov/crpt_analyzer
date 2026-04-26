from django.urls import path, include

urlpatterns = [
    path("", include("market.urls")),
]
