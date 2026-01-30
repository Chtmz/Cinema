import requests
from django.conf import settings


TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMG_BASE = "https://image.tmdb.org/t/p/w500"


class TMDbProviderError(Exception):
    pass


def _require_key():
    if not settings.TMDB_API_KEY:
        raise TMDbProviderError("TMDB_API_KEY is missing in settings.")


def search_movies(query: str, limit: int = 8):
    """
    Returns a list of suggestions:
    [{id, title, release_date, poster_url}, ...]
    """
    _require_key()

    if not query or not query.strip():
        return []

    url = f"{TMDB_BASE_URL}/search/movie"
    params = {
        "api_key": settings.TMDB_API_KEY,
        "query": query,
        "include_adult": "false",
        "language": "fr-FR",
        "page": 1,
    }

    try:
        r = requests.get(url, params=params, timeout=15)
    except requests.RequestException as e:
        raise TMDbProviderError(f"TMDb request failed: {e}") from e

    if r.status_code != 200:
        raise TMDbProviderError(f"TMDb search error: {r.status_code} {r.text[:200]}")

    data = r.json()
    results = data.get("results", [])[:limit]

    out = []
    for item in results:
        poster_path = item.get("poster_path")
        out.append(
            {
                "id": item.get("id"),
                "title": item.get("title") or "",
                "release_date": item.get("release_date") or None,
                "poster_url": f"{TMDB_IMG_BASE}{poster_path}" if poster_path else None,
            }
        )
    return out


def fetch_movie_details(tmdb_id: int):
    """
    Fetches full details (movie + credits):
    {
      title, synopsis, release_date, poster_url,
      genres: [str],
      cast: [{name, character, order}]
    }
    """
    _require_key()

    if not tmdb_id:
        raise TMDbProviderError("tmdb_id is required")

    movie_url = f"{TMDB_BASE_URL}/movie/{tmdb_id}"
    credits_url = f"{TMDB_BASE_URL}/movie/{tmdb_id}/credits"
    videos_url = f"{TMDB_BASE_URL}/movie/{tmdb_id}/videos"

    params = {
        "api_key": settings.TMDB_API_KEY,
        "language": "fr-FR",
    }

    try:
        movie_r = requests.get(movie_url, params=params, timeout=15)
        credits_r = requests.get(credits_url, params=params, timeout=15)
        videos_r = requests.get(videos_url, params=params, timeout=15)
    except requests.RequestException as e:
        raise TMDbProviderError(f"TMDb request failed: {e}") from e

    if movie_r.status_code != 200:
        raise TMDbProviderError(f"TMDb movie error: {movie_r.status_code} {movie_r.text[:200]}")
    if credits_r.status_code != 200:
        raise TMDbProviderError(f"TMDb credits error: {credits_r.status_code} {credits_r.text[:200]}")

    movie = movie_r.json()
    credits = credits_r.json()
    videos = videos_r.json().get("results", []) if videos_r.status_code == 200 else []

    # Extract Trailer (French preference from params, but fallback could be needed in future)
    trailer = next((v for v in videos if v.get("site") == "YouTube" and v.get("type") == "Trailer"), None)
    trailer_url = f"https://www.youtube.com/watch?v={trailer['key']}" if trailer else None

    poster_path = movie.get("poster_path")
    genres = [g.get("name") for g in movie.get("genres", []) if g.get("name")]

    cast_list = []
    for c in credits.get("cast", [])[:12]:  # top 12 billed
        name = c.get("name")
        if not name:
            continue
        cast_list.append(
            {
                "name": name,
                "character": c.get("character") or "",
                "order": c.get("order") or 0,
            }
        )
    
    # Extract Director
    directors = [
        c["name"] for c in credits.get("crew", []) 
        if c.get("job") == "Director"
    ]
    director_name = directors[0] if directors else ""

    return {
        "tmdb_id": movie.get("id"),
        "title": movie.get("title") or "",
        "synopsis": movie.get("overview") or "",
        "release_date": movie.get("release_date") or None,
        "poster_url": f"{TMDB_IMG_BASE}{poster_path}" if poster_path else None,
        "trailer_url": trailer_url,
        "duration_minutes": movie.get("runtime"),
        "director": director_name,
        "genres": genres,
        "cast": cast_list,
    }
