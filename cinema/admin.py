from datetime import datetime, timedelta
import re

from django import forms
from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import Film, Genre, Person, FilmCast, Salle, Seance

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import path
from django.utils import timezone

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
    change_list_template = "admin/cinema/seance/change_list.html"

    # ends_at is computed from duration_minutes
    readonly_fields = ("ends_at",)

    # faster UX if you have many films/salles
    autocomplete_fields = ("film", "salle")

    fieldsets = (
        ("Séance", {"fields": ("film", "salle")}),
        ("Horaire", {"fields": ("starts_at", "ends_at")}),
        ("Options", {"fields": ("language", "format")}),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "bulk-create/",
                self.admin_site.admin_view(self.bulk_create_view),
                name="cinema_seance_bulk_create",
            ),
        ]
        return custom_urls + urls

    def bulk_create_view(self, request):
        if request.method == "POST":
            form = BulkSeanceCreateForm(request.POST)
            if form.is_valid():
                created_count, skipped_count, error_messages = form.save()
                if created_count:
                    messages.success(
                        request,
                        f"{created_count} séance(s) créées avec succès.",
                    )
                if skipped_count:
                    messages.info(
                        request,
                        f"{skipped_count} séance(s) ignorées (déjà existantes).",
                    )
                for error in error_messages:
                    messages.error(request, error)
                return redirect("..")
        else:
            form = BulkSeanceCreateForm()

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "form": form,
            "title": "Création rapide de séances",
        }
        return render(request, "admin/cinema/seance/bulk_create.html", context)


class BulkSeanceCreateForm(forms.Form):
    WEEKDAY_CHOICES = [
        ("0", "Lundi"),
        ("1", "Mardi"),
        ("2", "Mercredi"),
        ("3", "Jeudi"),
        ("4", "Vendredi"),
        ("5", "Samedi"),
        ("6", "Dimanche"),
    ]

    film = forms.ModelChoiceField(queryset=Film.objects.all())
    salle = forms.ModelChoiceField(queryset=Salle.objects.all())
    start_date = forms.DateField(label="Date de début")
    end_date = forms.DateField(label="Date de fin")
    times = forms.CharField(
        label="Horaires",
        help_text="Ex: 10:00, 14:30, 19:00",
    )
    weekdays = forms.MultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Jours de la semaine",
        help_text="Laissez vide pour tous les jours.",
    )
    language = forms.ChoiceField(
        choices=Seance.Language.choices,
        label="Langue",
    )
    format = forms.ChoiceField(
        choices=Seance.Format.choices,
        label="Format",
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "La date de fin doit être après la date de début.")
        return cleaned_data

    def clean_times(self):
        raw_times = self.cleaned_data["times"]
        parts = [p for p in re.split(r"[\s,;]+", raw_times.strip()) if p]
        parsed_times = []
        invalid = []
        for part in parts:
            try:
                parsed_times.append(datetime.strptime(part, "%H:%M").time())
            except ValueError:
                invalid.append(part)
        if invalid:
            raise forms.ValidationError(
                f"Horaires invalides: {', '.join(invalid)} (format HH:MM)."
            )
        if not parsed_times:
            raise forms.ValidationError("Veuillez fournir au moins un horaire valide.")
        return parsed_times

    def save(self):
        film = self.cleaned_data["film"]
        salle = self.cleaned_data["salle"]
        start_date = self.cleaned_data["start_date"]
        end_date = self.cleaned_data["end_date"]
        times = self.cleaned_data["times"]
        weekdays = {int(day) for day in self.cleaned_data.get("weekdays", [])}
        language = self.cleaned_data["language"]
        format_value = self.cleaned_data["format"]

        created_count = 0
        skipped_count = 0
        error_messages = []

        tz = timezone.get_current_timezone()
        current_date = start_date
        while current_date <= end_date:
            if weekdays and current_date.weekday() not in weekdays:
                current_date += timedelta(days=1)
                continue
            for show_time in times:
                starts_at = timezone.make_aware(
                    datetime.combine(current_date, show_time),
                    tz,
                )
                if Seance.objects.filter(
                    film=film,
                    salle=salle,
                    starts_at=starts_at,
                ).exists():
                    skipped_count += 1
                    continue
                try:
                    Seance.objects.create(
                        film=film,
                        salle=salle,
                        starts_at=starts_at,
                        language=language,
                        format=format_value,
                    )
                    created_count += 1
                except Exception as exc:  # noqa: BLE001 - surface admin validation errors
                    error_messages.append(
                        f"{current_date:%Y-%m-%d} {show_time:%H:%M} : {exc}"
                    )
            current_date += timedelta(days=1)

        return created_count, skipped_count, error_messages