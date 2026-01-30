from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


# -----------------------
# Genre (tags like IMDb)
# -----------------------
class Genre(models.Model):
    name = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Genre"
        verbose_name_plural = "Genres"

    def __str__(self) -> str:
        return self.name


# -----------------------
# Person (actors, cast)
# -----------------------
class Person(models.Model):
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Personne"
        verbose_name_plural = "Personnes"

    def __str__(self) -> str:
        return self.name


# -----------------------
# Film
# -----------------------
class Film(models.Model):
    class Status(models.TextChoices):
        NOW_SHOWING = "NOW", "À l’affiche"
        COMING_SOON = "SOON", "Prochainement"
        ARCHIVED = "ARCH", "Archivé"

    title = models.CharField(max_length=255)
    synopsis = models.TextField(blank=True)
    director = models.CharField(max_length=200, blank=True)

    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    release_date = models.DateField(null=True, blank=True)

    poster_url = models.URLField(max_length=500, null=True, blank=True)
    trailer_url = models.URLField(max_length=500, null=True, blank=True)

    # Derived (system-managed) status
    status = models.CharField(
        max_length=4,
        choices=Status.choices,
        default=Status.COMING_SOON,
        editable=False,  # IMPORTANT: admin cannot manually edit
    )

    external_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="ID du film depuis une API externe (ex: TMDb)",
    )

    genres = models.ManyToManyField(
        Genre,
        blank=True,
        related_name="films",
    )

    cast = models.ManyToManyField(
        Person,
        through="FilmCast",
        blank=True,
        related_name="films",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Film"
        verbose_name_plural = "Films"

    def __str__(self) -> str:
        return self.title

    def has_future_seances(self) -> bool:
        """True if there is at least one seance starting in the future."""
        now = timezone.now()
        return self.seances.filter(starts_at__gte=now).exists()

    def compute_status(self) -> str:
        """
        Model A: status is derived, not manually chosen.

        Rules:
        - If release_date > today => COMING_SOON
        - Else if has future seances => NOW_SHOWING
        - Else => ARCHIVED

        If release_date is NULL:
        - If has future seances => NOW_SHOWING (because it is scheduled)
        - Else => COMING_SOON (unknown / not active yet)
        """
        today = timezone.localdate()

        if self.release_date and self.release_date > today:
            return Film.Status.COMING_SOON

        if self.has_future_seances():
            return Film.Status.NOW_SHOWING

        # release_date <= today (or missing) and no future seances
        if self.release_date and self.release_date <= today:
            return Film.Status.ARCHIVED

        # release_date is missing and no future seances
        return Film.Status.COMING_SOON

    def refresh_status(self, save: bool = True) -> str:
        """Recompute status and optionally persist if it changed."""
        new_status = self.compute_status()
        if self.status != new_status:
            self.status = new_status
            if save:
                # Update only the status column (avoid recursion / noise)
                Film.objects.filter(pk=self.pk).update(status=new_status)
        return new_status

    def save(self, *args, **kwargs):
        # Save first (so pk exists), then derive status (can query seances safely)
        super().save(*args, **kwargs)
        self.refresh_status(save=True)


# ---------------------------------------
# Through table for Film ↔ Cast
# ---------------------------------------
class FilmCast(models.Model):
    film = models.ForeignKey(Film, on_delete=models.CASCADE)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)

    character_name = models.CharField(max_length=120, blank=True)
    billing_order = models.PositiveSmallIntegerField(default=0)
    is_main = models.BooleanField(default=True)

    class Meta:
        ordering = ["film", "billing_order", "person__name"]
        verbose_name = "Casting"
        verbose_name_plural = "Casting"
        constraints = [
            models.UniqueConstraint(
                fields=["film", "person"],
                name="unique_person_per_film",
            )
        ]

    def __str__(self) -> str:
        return f"{self.person} — {self.film}"


# -----------------------
# Salle (Hall)
# -----------------------
class Salle(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Salle"
        verbose_name_plural = "Salles"

    def __str__(self) -> str:
        return self.name


# -----------------------
# Séance (Showtime)
# -----------------------
class Seance(models.Model):
    film = models.ForeignKey(
        Film,
        on_delete=models.CASCADE,
        related_name="seances",
    )

    salle = models.ForeignKey(
        Salle,
        on_delete=models.PROTECT,
        related_name="seances",
    )

    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)

    class Language(models.TextChoices):
        VF = "VF", "VF"
        VOSTFR = "VOSTFR", "VOSTFR"

    class Format(models.TextChoices):
        TWO_D = "2D", "2D"
        THREE_D = "3D", "3D"
        IMAX = "IMAX", "IMAX"
        FOUR_DX = "4DX", "4DX"
        DOLBY = "DOLBY", "DOLBY"

    language = models.CharField(
        max_length=10,
        choices=Language.choices,
        default=Language.VF,
    )

    format = models.CharField(
        max_length=10,
        choices=Format.choices,
        default=Format.TWO_D,
        blank=True,
    )

    class Meta:
        ordering = ["starts_at"]
        verbose_name = "Séance"
        verbose_name_plural = "Séances"

    def __str__(self) -> str:
        return f"{self.starts_at:%Y-%m-%d %H:%M} — {self.film} ({self.salle})"

    def compute_ends_at(self):
        if not self.film_id:
            return None
        if not self.film.duration_minutes:
            raise ValidationError(
                "Le film doit avoir une durée (duration_minutes) pour programmer une séance."
            )
        if not self.starts_at:
            return None
        return self.starts_at + timedelta(minutes=self.film.duration_minutes)

    def clean(self):
        super().clean()

        # Auto-calculate real movie end time (no buffer here)
        if self.film_id and self.starts_at:
            self.ends_at = self.compute_ends_at()

        # If incomplete data, skip overlap checks
        if not self.salle_id or not self.starts_at or not self.ends_at:
            return

        turnover = getattr(settings, "CINEMA_TURNOVER_MINUTES", 30)
        buffer_delta = timedelta(minutes=turnover)

        # Consider the salle occupied until ends_at + buffer
        this_start = self.starts_at
        this_end_with_buffer = self.ends_at + buffer_delta

        candidates = (
            Seance.objects.filter(salle=self.salle)
            .exclude(pk=self.pk)
            .filter(starts_at__lt=this_end_with_buffer)
            .filter(ends_at__gt=this_start - buffer_delta)
        )

        if candidates.exists():
            conflict = candidates.order_by("starts_at").first()
            raise ValidationError(
                f"Conflit: la salle '{self.salle}' est occupée par '{conflict.film}' "
                f"({conflict.starts_at:%Y-%m-%d %H:%M}–{conflict.ends_at:%H:%M}). "
                f"Il faut {turnover} min entre deux séances."
            )

    def save(self, *args, **kwargs):
        # Validate + compute ends_at before saving
        self.full_clean()
        super().save(*args, **kwargs)

        # After saving a seance, the film may become NOW_SHOWING/ARCHIVED
        if self.film_id:
            self.film.refresh_status(save=True)

    def delete(self, *args, **kwargs):
        film = self.film  # keep reference before deletion
        super().delete(*args, **kwargs)
        if film and film.pk:
            film.refresh_status(save=True)
