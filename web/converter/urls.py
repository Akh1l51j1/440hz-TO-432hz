from django.urls import path
from . import views

urlpatterns = [
    path("",                 views.index,           name="index"),
    path("api/status/",      views.api_status,      name="api_status"),
    path("api/start/",       views.api_start,       name="api_start"),
    path("api/stop/",        views.api_stop,        name="api_stop"),
    path("api/clear-error/", views.api_clear_error, name="api_clear_error"),
]
