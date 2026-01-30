from django.urls import path
from .api_views import programmation_api

urlpatterns = [
    path("programmation/", programmation_api, name="programmation_api"),
]
