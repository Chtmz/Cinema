from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import Film, Genre, Person, FilmCast, Salle, Seance

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.http import urlencode

from .providers.tmdb import search_movies, fetch_movie_details, TMDbProviderError

@admin.register(Genre)
class GenreAdmin(ModelAdmin):
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Person)
class PersonAdmin(ModelAdmin):
    search_fields = ("name",)
    ordering = ("name",)


class FilmCastInline(TabularInline):
    model = FilmCast
    extra = 1
    autocomplete_fields = ("person",)
    ordering = ("billing_order",)


@admin.register(Film)
class FilmAdmin(ModelAdmin):
    change_form_template = "film/change_form.html"
    list_display = ("title", "status", "release_date", "duration_minutes", "director")
    list_filter = ("status", "genres")
    search_fields = ("title", "external_id")
    filter_horizontal = ("genres",)
    inlines = (FilmCastInline,)
    ordering = ("title",)
    readonly_fields = ("status",)


@admin.register(Salle)
class SalleAdmin(ModelAdmin):
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Seance)
class SeanceAdmin(ModelAdmin):
    list_display = ("starts_at", "ends_at", "film", "salle", "language", "format")
    list_filter = ("salle", "language", "format", "starts_at")
    search_fields = ("film__title", "salle__name")
    ordering = ("starts_at",)
    date_hierarchy = "starts_at"

    # ends_at is computed from duration_minutes
    readonly_fields = ("ends_at",)

    # faster UX if you have many films/salles
    autocomplete_fields = ("film", "salle")

    fieldsets = (
        ("Séance", {"fields": ("film", "salle")}),
        ("Horaire", {"fields": ("starts_at", "ends_at")}),
        ("Options", {"fields": ("language", "format")}),
    )
