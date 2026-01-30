from .models import Film, Genre, Person, FilmCast
from .providers.tmdb import fetch_movie_details, TMDbProviderError

def create_or_update_film_from_tmdb(tmdb_id: int):
    """
    Fetches details from TMDb and creates/updates the Film, Genres, and Cast.
    Returns (film, created).
    Raises TMDbProviderError if something goes wrong.
    """
    details = fetch_movie_details(tmdb_id)

    # Create or update the Film
    film, created = Film.objects.get_or_create(
        external_id=str(details["tmdb_id"]),
        defaults={
            "title": details["title"],
        },
    )

    # Update fields if they are empty or if we want to enforce sync
    # Strategy: overwrite if empty, or maybe always overwrite? 
    # The original api code only filled empty fields. Let's stick to that for safety.
    changed = False
    if details.get("title") and (not film.title):
        film.title = details["title"]; changed = True
    if details.get("synopsis") and (not film.synopsis):
        film.synopsis = details["synopsis"]; changed = True
    if details.get("poster_url") and (not film.poster_url):
        film.poster_url = details["poster_url"]; changed = True
    if details.get("release_date") and (not film.release_date):
        film.release_date = details["release_date"]; changed = True

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
    # We strip existing cast for this film and re-add to avoid duplicates/ordering issues
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

    # Recompute derived status
    film.refresh_status(save=True)

    return film, created
