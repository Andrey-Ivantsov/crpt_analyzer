from django.urls import path
from . import views

urlpatterns = [
    path("",               views.index,          name="index"),
    path("api/snapshot/",  views.fetch_snapshot,  name="fetch_snapshot"),
]
