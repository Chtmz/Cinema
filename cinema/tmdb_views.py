import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt

from .providers.tmdb import search_movies, fetch_movie_details, TMDbProviderError
from .models import Film, Genre, Person, FilmCast


@require_GET
def tmdb_search_api(request):
    q = request.GET.get("q", "").strip()
    try:
        results = search_movies(q)
        return JsonResponse(results, safe=False)
    except TMDbProviderError as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
@require_POST
def tmdb_import_api(request):
    """
    POST body: {"tmdb_id": 123}
    Creates/updates a Film + genres + cast.
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    tmdb_id = data.get("tmdb_id")
    if not tmdb_id:
        return JsonResponse({"error": "tmdb_id is required"}, status=400)

    try:
        details = fetch_movie_details(int(tmdb_id))
    except TMDbProviderError as e:
        return JsonResponse({"error": str(e)}, status=400)

    # Create or update the Film
    film, created = Film.objects.get_or_create(
        external_id=str(details["tmdb_id"]),
        defaults={
            "title": details["title"],
        },
    )

    # Fill only empty fields (safe behavior)
    changed = False
    if details.get("title") and (not film.title):
        film.title = details["title"]; changed = True
    if details.get("synopsis") and (not film.synopsis):
        film.synopsis = details["synopsis"]; changed = True
    if details.get("poster_url") and (not film.poster_url):
        film.poster_url = details["poster_url"]; changed = True
    if details.get("director") and (not film.director):
        film.director = details["director"]; changed = True
    if details.get("duration_minutes") and (not film.duration_minutes):
        film.duration_minutes = details["duration_minutes"]; changed = True
    if details.get("trailer_url") and (not film.trailer_url):
        film.trailer_url = details["trailer_url"]; changed = True
    if details.get("release_date") and (not film.release_date):
        # Parse "YYYY-MM-DD" to date object to avoid type errors in compute_status
        try:
            from datetime import datetime
            dt = datetime.strptime(details["release_date"], "%Y-%m-%d").date()
            film.release_date = dt; changed = True
        except ValueError:
            pass  # Invalid date format, ignore

    if changed or created:
        film.save()

    # Genres (upsert)
    genre_names = details.get("genres", [])
    if genre_names:
        genre_objs = []
        for name in genre_names:
            g, _ = Genre.objects.get_or_create(name=name)
            genre_objs.append(g)
        film.genres.set(genre_objs)

    # Cast (upsert top billed)
    # For MVP we rebuild cast each import (simple and consistent)
    FilmCast.objects.filter(film=film).delete()
    for c in details.get("cast", []):
        p, _ = Person.objects.get_or_create(name=c["name"])
        FilmCast.objects.create(
            film=film,
            person=p,
            character_name=c.get("character", ""),
            billing_order=c.get("order", 0),
            is_main=True,
        )

    # Recompute derived status (your Film.refresh_status exists)
    film.refresh_status(save=True)

    return JsonResponse({"ok": True, "film_id": film.id, "created": created})
