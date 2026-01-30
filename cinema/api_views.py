from datetime import datetime, time

from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Prefetch

from .models import Film, Seance


def programmation_api(request):
    """
    GET /api/programmation/?date=YYYY-MM-DD
    Returns films that have seances on that date, with showtimes.
    """
    date_str = request.GET.get("date")

    # Default: today (server local date)
    if not date_str:
        selected_date = timezone.localdate()
    else:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    start_dt = timezone.make_aware(datetime.combine(selected_date, time.min))
    end_dt = timezone.make_aware(datetime.combine(selected_date, time.max))

    day_seances_qs = Seance.objects.filter(
        starts_at__range=(start_dt, end_dt)
    ).order_by("starts_at")

    films_qs = (
        Film.objects.filter(seances__in=day_seances_qs)
        .distinct()
        .prefetch_related(
            "genres",
            Prefetch("seances", queryset=day_seances_qs, to_attr="day_seances"),
        )
        .order_by("title")
    )

    payload = {
        "date": selected_date.isoformat(),
        "films": [
            {
                "id": film.id,
                "title": film.title,
                "poster_url": film.poster_url,
                "duration_minutes": film.duration_minutes,
                "genres": [g.name for g in film.genres.all()],
                "seances": [
                    {
                        "id": s.id,
                        "starts_at": s.starts_at.isoformat(),
                        "time": timezone.localtime(s.starts_at).strftime("%H:%M"),
                        "language": s.language,
                        "format": s.format,
                    }
                    for s in getattr(film, "day_seances", [])
                ],
            }
            for film in films_qs
        ],
    }

    return JsonResponse(payload)
