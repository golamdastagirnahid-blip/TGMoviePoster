"""Pick a random public-domain movie from Internet Archive's feature_films collection.
Returns a small (<50 MB) mp4 path so Telegram bot upload limit (50 MB) is respected."""
import os
import random
import tempfile
import requests

SEARCH = "https://archive.org/advancedsearch.php"
META = "https://archive.org/metadata/{}"
DL = "https://archive.org/download/{}/{}"


def pick_random_film():
    params = {
        "q": "collection:feature_films AND mediatype:movies",
        "fl[]": "identifier,title,year,description",
        "rows": 50,
        "page": random.randint(1, 40),
        "output": "json",
    }
    r = requests.get(SEARCH, params=params, timeout=30).json()
    docs = r.get("response", {}).get("docs", [])
    random.shuffle(docs)
    return docs


def find_small_mp4(identifier, max_mb=48):
    meta = requests.get(META.format(identifier), timeout=30).json()
    files = meta.get("files", [])
    candidates = []
    for f in files:
        name = f.get("name", "")
        if name.lower().endswith(".mp4"):
            try:
                size_mb = int(f.get("size", "0")) / 1_000_000
            except Exception:
                continue
            if size_mb <= max_mb:
                candidates.append((size_mb, name))
    candidates.sort(reverse=True)  # largest under limit
    return candidates[0][1] if candidates else None


def download(identifier, filename, dest_dir=None):
    dest_dir = dest_dir or tempfile.gettempdir()
    path = os.path.join(dest_dir, filename.replace("/", "_"))
    url = DL.format(identifier, filename)
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    return path


def get_one(skip_ids):
    """Return (info_dict, video_path) or None."""
    for doc in pick_random_film():
        ident = doc.get("identifier")
        if not ident or ident in skip_ids:
            continue
        try:
            fname = find_small_mp4(ident)
            if not fname:
                continue
            path = download(ident, fname)
            info = {
                "id": ident,
                "title": doc.get("title", ident),
                "year": str(doc.get("year", "")),
                "overview": (doc.get("description") or "")[:500] if isinstance(doc.get("description"), str) else "",
            }
            return info, path
        except Exception as e:
            print(f"skip {ident}: {e}")
            continue
    return None
