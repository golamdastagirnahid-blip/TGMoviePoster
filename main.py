"""Entry point. Posts one item to each of the 5 Movie Bell channels.
Config-driven: edit CHANNELS below to change behavior per channel.
"""
import json
import os
import random
import time
from pathlib import Path

import tmdb
import templates
import telegram_post as tg
import facebook_post as fb
import archive_free

ROOT = Path(__file__).parent
STATE_FILE = ROOT / "posted.json"
MAX_HISTORY = 500

# -----------------------------------------------------------------------------
# CHANNEL CONFIG — one entry per Telegram channel
# -----------------------------------------------------------------------------
# kind:       "movie" (info + album), "trailer", or "free" (public-domain film)
# env:        GitHub secret name holding @channel or -100xxxx id
# state_key:  unique key in posted.json (dedup)
# region:     ISO country code for "Where to Watch" + Amazon
# amazon:     ("domain", "associates_tag") — earnings region
# fb:         True = also crosspost to Facebook Page
# pool:       TMDB source — "now_playing" or {"discover": {...kwargs...}}
# -----------------------------------------------------------------------------
CHANNELS = [
    {
        "name": "Movie Bell",
        "kind": "movie",
        "env": "CHANNEL_MAIN",
        "state_key": "main",
        "region": "US",
        "amazon": ("amazon.com", "moviebell-20"),
        "fb": True,
        "pool": "now_playing",
    },
    {
        "name": "Movie Bell Pro",
        "kind": "trailer",
        "env": "CHANNEL_PRO",
        "state_key": "pro",
        "region": "US",
        "amazon": ("amazon.com", "moviebell-20"),
        "fb": False,
        "pool": "now_playing",
    },
    {
        "name": "Movie Bell Max",
        "kind": "free",
        "env": "CHANNEL_MAX",
        "state_key": "max",
        "region": "US",
        "amazon": ("amazon.com", "moviebell-20"),
        "fb": False,
    },
    {
        "name": "Movie Bell US",
        "kind": "movie",
        "env": "CHANNEL_US",
        "state_key": "us",
        "region": "US",
        "amazon": ("amazon.com", "moviebell-20"),
        "fb": False,
        "pool": {"discover": {"region": "US", "language": "en"}},
    },
    {
        "name": "Movie Bell UK",
        "kind": "movie",
        "env": "CHANNEL_UK",
        "state_key": "uk",
        "region": "GB",
        "amazon": ("amazon.co.uk", "moviebelluk-21"),
        "fb": False,
        "pool": {"discover": {"region": "GB", "language": "en"}},
    },
]


def load_state():
    if STATE_FILE.exists():
        data = json.loads(STATE_FILE.read_text())
    else:
        data = {}
    for ch in CHANNELS:
        data.setdefault(ch["state_key"], [])
    return data


def save_state(state):
    for k in state:
        state[k] = state[k][-MAX_HISTORY:]
    STATE_FILE.write_text(json.dumps(state, indent=2))


def pick_unposted(candidates, posted_ids):
    random.shuffle(candidates)
    for c in candidates:
        if c["id"] not in posted_ids:
            return c
    return None


def get_pool(spec):
    if spec == "now_playing":
        return tmdb.now_playing()
    if isinstance(spec, dict) and "discover" in spec:
        return tmdb.discover(**spec["discover"])
    return []


def post_movie(ch, state):
    chat = os.environ.get(ch["env"])
    if not chat:
        print(f"[skip] {ch['name']} — env {ch['env']} not set")
        return
    pool = get_pool(ch["pool"])
    pick = pick_unposted(pool, set(state[ch["state_key"]]))
    if not pick:
        print(f"[{ch['name']}] no new movies")
        return
    details = tmdb.movie_details(pick["id"])
    domain, tag = ch["amazon"]
    m = tmdb.format_movie(details, region=ch["region"], amazon_domain=domain, amazon_tag=tag)
    caption = templates.info_caption(m)
    images = tmdb.movie_images(details, max_count=5)

    ok = False
    if len(images) >= 2:
        ok = tg.send_media_group(chat, images, caption)
    elif images:
        ok = tg.send_photo(chat, images[0], caption)
    if not ok:
        ok = tg.send_message(chat, caption)

    if ok:
        state[ch["state_key"]].append(m["id"])
        print(f"[{ch['name']}] posted: {m['title']}")
        if ch["fb"] and images:
            if fb.post_album(images, caption):
                print(f"[fb] posted: {m['title']}")


def post_trailer(ch, state):
    chat = os.environ.get(ch["env"])
    if not chat:
        print(f"[skip] {ch['name']}")
        return
    pool = tmdb.now_playing() + tmdb.discover()
    pick = pick_unposted(pool, set(state[ch["state_key"]]))
    if not pick:
        return
    details = tmdb.movie_details(pick["id"])
    domain, tag = ch["amazon"]
    m = tmdb.format_movie(details, region=ch["region"], amazon_domain=domain, amazon_tag=tag)
    if m["trailer"] == "N/A":
        return
    caption = templates.trailer_caption(m)
    images = tmdb.movie_images(details, max_count=4)
    ok = False
    if len(images) >= 2:
        ok = tg.send_media_group(chat, images, caption)
    elif m["poster_url"]:
        ok = tg.send_photo(chat, m["poster_url"], caption)
    if ok:
        state[ch["state_key"]].append(m["id"])
        print(f"[{ch['name']}] trailer: {m['title']}")


def post_free(ch, state):
    chat = os.environ.get(ch["env"])
    if not chat:
        print(f"[skip] {ch['name']}")
        return
    res = archive_free.get_one(set(state[ch["state_key"]]))
    if not res:
        print(f"[{ch['name']}] nothing found")
        return
    info, path = res
    caption = templates.free_caption(info)
    ok = tg.send_video_file(chat, path, caption)
    try:
        os.remove(path)
    except OSError:
        pass
    if ok:
        state[ch["state_key"]].append(info["id"])
        print(f"[{ch['name']}] free film: {info['title']}")


def main():
    state = load_state()
    for ch in CHANNELS:
        try:
            if ch["kind"] == "movie":
                post_movie(ch, state)
            elif ch["kind"] == "trailer":
                post_trailer(ch, state)
            elif ch["kind"] == "free":
                post_free(ch, state)
        except Exception as e:
            print(f"[error] {ch['name']}: {e}")
        time.sleep(3)
    save_state(state)
    print("done.")


if __name__ == "__main__":
    main()
