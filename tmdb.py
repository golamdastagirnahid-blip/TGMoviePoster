"""TMDB API helper. Free key from https://www.themoviedb.org/settings/api
Region + Amazon tag are passed per-call so each channel can target its own market.
"""
import os
import random
from urllib.parse import quote_plus

import requests

import shortener

API = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/original"  # original = up to 4K
KEY = os.environ.get("TMDB_API_KEY", "")

# Search-URL templates per streaming provider. {q} = url-encoded title.
PROVIDER_URLS = {
    "Netflix": "https://www.netflix.com/search?q={q}",
    "Disney Plus": "https://www.disneyplus.com/search?q={q}",
    "Disney+ Hotstar": "https://www.hotstar.com/in/search?q={q}",
    "JioCinema": "https://www.jiocinema.com/search/{q}",
    "ZEE5": "https://www.zee5.com/search?q={q}",
    "Sony LIV": "https://www.sonyliv.com/search?searchTerm={q}",
    "Apple TV Plus": "https://tv.apple.com/search?term={q}",
    "Apple TV": "https://tv.apple.com/search?term={q}",
    "YouTube": "https://www.youtube.com/results?search_query={q}+full+movie",
    "Google Play Movies": "https://play.google.com/store/search?q={q}&c=movies",
    "MX Player": "https://www.mxplayer.in/search?q={q}",
}


def _get(path, **params):
    params["api_key"] = KEY
    r = requests.get(f"{API}{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def now_playing(page=None):
    page = page or random.randint(1, 5)
    return _get("/movie/now_playing", page=page).get("results", [])


def discover(language=None, sort_by="popularity.desc", page=None, region=None):
    page = page or random.randint(1, 10)
    params = {"sort_by": sort_by, "page": page, "vote_count.gte": 50}
    if language:
        params["with_original_language"] = language
    if region:
        params["region"] = region
    return _get("/discover/movie", **params).get("results", [])


def movie_details(movie_id):
    return _get(
        f"/movie/{movie_id}",
        append_to_response="credits,videos,watch/providers,images",
    )


def fb_images(d, count=4):
    """Pro-arranged image set for Facebook album:
    - Cover: highest-rated landscape backdrop (fills feed properly)
    - Then poster (portrait)
    - Then more top backdrops
    4 photos = clean 2x2 grid in FB feed.
    """
    backdrops = sorted(
        (d.get("images", {}) or {}).get("backdrops", []) or [],
        key=lambda b: (b.get("vote_average", 0), b.get("width", 0)),
        reverse=True,
    )
    imgs = []
    if backdrops and backdrops[0].get("file_path"):
        imgs.append(f"{IMG}{backdrops[0]['file_path']}")
    if d.get("poster_path"):
        imgs.append(f"{IMG}{d['poster_path']}")
    for b in backdrops[1:]:
        if len(imgs) >= count:
            break
        url = f"{IMG}{b['file_path']}"
        if url not in imgs:
            imgs.append(url)
    return imgs[:count]


def movie_images(d, max_count=5):
    """Return up to N HD image URLs: main poster first, then best stills."""
    imgs = []
    if d.get("poster_path"):
        imgs.append(f"{IMG}{d['poster_path']}")
    backdrops = (d.get("images", {}) or {}).get("backdrops", []) or []
    backdrops.sort(key=lambda b: b.get("vote_average", 0), reverse=True)
    for b in backdrops:
        if b.get("file_path"):
            url = f"{IMG}{b['file_path']}"
            if url not in imgs:
                imgs.append(url)
        if len(imgs) >= max_count:
            break
    if len(imgs) < max_count:
        for p in (d.get("images", {}) or {}).get("posters", []) or []:
            url = f"{IMG}{p['file_path']}"
            if url not in imgs:
                imgs.append(url)
            if len(imgs) >= max_count:
                break
    return imgs[:max_count]


def _amazon_url(domain, tag, query):
    return f"https://www.{domain}/s?k={query}&i=movies-tv&tag={tag}"


def _build_watch_links(providers_block, title, region, amazon_domain, amazon_tag):
    q = quote_plus(title)
    amazon = _amazon_url(amazon_domain, amazon_tag, q)
    lines = []
    region_data = (providers_block or {}).get("results", {}).get(region) or {}
    seen = []
    for kind in ("flatrate", "free", "ads", "rent", "buy"):
        for p in region_data.get(kind, []) or []:
            name = p.get("provider_name")
            if name and name not in seen and name != "Amazon Prime Video":
                seen.append(name)
    for name in seen[:5]:
        tpl = PROVIDER_URLS.get(name)
        if tpl:
            lines.append(f"• [{name}]({shortener.shorten(tpl.format(q=q))})")
        else:
            lines.append(f"• {name}")
    lines.append(f"• [🛒 Buy / Rent on Amazon]({amazon})")  # always
    return "\n\n📺 *Where to Watch* ({}):\n{}".format(region, "\n".join(lines))


def format_movie(d, region="US", amazon_domain="amazon.com", amazon_tag="moviebell-20"):
    """Turn TMDB details JSON into a flat dict for templates."""
    cast = ", ".join(c["name"] for c in d.get("credits", {}).get("cast", [])[:4]) or "—"
    director = next(
        (c["name"] for c in d.get("credits", {}).get("crew", []) if c.get("job") == "Director"),
        "",
    )
    genres = ", ".join(g["name"] for g in d.get("genres", [])) or "—"
    trailer = ""
    for v in d.get("videos", {}).get("results", []):
        if v.get("site") == "YouTube" and v.get("type") == "Trailer":
            trailer = shortener.shorten(f"https://youtu.be/{v['key']}")
            break
    title = d.get("title") or d.get("original_title", "Untitled")
    poster = d.get("poster_path")
    backdrop = d.get("backdrop_path")
    watch = _build_watch_links(
        d.get("watch/providers"), title, region, amazon_domain, amazon_tag
    )
    return {
        "id": d["id"],
        "title": title,
        "year": (d.get("release_date") or "----")[:4],
        "rating": round(d.get("vote_average") or 0, 1),
        "genres": genres,
        "language": (d.get("original_language") or "").upper(),
        "runtime": d.get("runtime") or "?",
        "overview": (d.get("overview") or "No description available.")[:600],
        "cast": cast,
        "director": director,
        "trailer": trailer or "N/A",
        "watch": watch,
        "poster_url": f"{IMG}{poster}" if poster else None,
        "backdrop_url": f"{IMG}{backdrop}" if backdrop else None,
    }
