from django.urls import path
from .tmdb_views import tmdb_search_api, tmdb_import_api

urlpatterns = [
    path("tmdb/search/", tmdb_search_api, name="tmdb_search_api"),
    path("tmdb/import/", tmdb_import_api, name="tmdb_import_api"),
]
