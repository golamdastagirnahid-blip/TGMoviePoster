"""Entry point. Posts one item to each of the 5 Movie Bell channels.
Config-driven: edit CHANNELS below to change behavior per channel.
"""
import json
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import tmdb
import templates
import telegram_post as tg
import facebook_post as fb
import archive_free

ROOT = Path(__file__).parent
STATE_FILE = ROOT / "posted.json"
MAX_HISTORY = 500

# ----------------------------------------------------------------------------
# HUMANIZED SCHEDULE
# ----------------------------------------------------------------------------
# Workflow fires every 30 min; each channel only posts if enough hours have
# passed since its last post AND we're inside its active hour window (UTC).
# Adds 1-15 min random jitter so posts don't land on the same minute every
# time. Total posts per day per channel: ~4-8 (looks human, not bot).
# ----------------------------------------------------------------------------
MIN_HOURS_BETWEEN = {
    "main": (3, 5),   # 3-5 hours randomized cooldown
    "pro": (4, 7),
    "max": (8, 12),   # free films less frequent
    "us": (4, 6),
    "uk": (4, 6),
}
# Active hour windows in UTC (24h). Skip sleeping hours to look human.
# US audience peak: 13:00-04:00 UTC (9am-midnight ET)
# UK audience peak: 07:00-22:00 UTC
ACTIVE_HOURS_UTC = {
    "main": list(range(0, 24)),               # always on
    "pro": list(range(8, 23)),
    "max": list(range(10, 22)),
    "us": list(range(13, 24)) + list(range(0, 5)),
    "uk": list(range(7, 23)),
}
# Only ONE channel crossposts to Facebook per workflow run (rotates).
# This keeps FB frequency at ~1 post per 30 min worst-case, healthy for FB algo.
FB_ROTATION = ["main", "us", "uk"]

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
        "fb": True,
        "pool": {"discover": {"region": "US", "language": "en"}},
    },
    {
        "name": "Movie Bell UK",
        "kind": "movie",
        "env": "CHANNEL_UK",
        "state_key": "uk",
        "region": "GB",
        "amazon": ("amazon.co.uk", "moviebelluk-21"),
        "fb": True,
        "pool": {"discover": {"region": "GB", "language": "en"}},
    },
]


def load_state():
    if STATE_FILE.exists():
        data = json.loads(STATE_FILE.read_text())
    else:
        data = {}
    data.setdefault("_last_post_ts", {})  # state_key -> iso timestamp
    data.setdefault("_fb_rotation_idx", 0)
    for ch in CHANNELS:
        data.setdefault(ch["state_key"], [])
    return data


def save_state(state):
    for k in state:
        state[k] = state[k][-MAX_HISTORY:]
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _hours_since(iso_ts):
    if not iso_ts:
        return 1e9
    try:
        dt = datetime.fromisoformat(iso_ts)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    except Exception:
        return 1e9


def _should_post_now(state_key, state):
    """Humanized gate: cooldown elapsed + within active hour window."""
    hour = datetime.now(timezone.utc).hour
    if hour not in ACTIVE_HOURS_UTC.get(state_key, list(range(24))):
        return False, f"outside active window (UTC hour={hour})"
    lo, hi = MIN_HOURS_BETWEEN.get(state_key, (3, 5))
    cooldown = random.uniform(lo, hi)
    elapsed = _hours_since(state["_last_post_ts"].get(state_key))
    if elapsed < cooldown:
        return False, f"cooldown {elapsed:.1f}h < {cooldown:.1f}h"
    return True, "ok"


def _mark_posted(state_key, state):
    state["_last_post_ts"][state_key] = datetime.now(timezone.utc).isoformat()


def _humanize_sleep():
    """Random 30s-4min pause to simulate human composing time."""
    time.sleep(random.uniform(30, 240))


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
    caption = templates.info_caption(m, state_key=ch["state_key"])
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
        # FB is intentionally throttled: only the rotation winner crossposts
        if ch["fb"] and ch["state_key"] == _fb_winner(state):
            fb_imgs = tmdb.fb_images(details, count=4)
            if fb_imgs:
                fb_text = templates.fb_caption(m)
                if fb.post_album(fb_imgs, fb_text):
                    print(f"[fb] posted ({ch['state_key']}): {m['title']}")
        _mark_posted(ch["state_key"], state)


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
    caption = templates.trailer_caption(m, state_key=ch["state_key"])
    images = tmdb.movie_images(details, max_count=4)
    ok = False
    if len(images) >= 2:
        ok = tg.send_media_group(chat, images, caption)
    elif m["poster_url"]:
        ok = tg.send_photo(chat, m["poster_url"], caption)
    if ok:
        state[ch["state_key"]].append(m["id"])
        _mark_posted(ch["state_key"], state)
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
    caption = templates.free_caption(info, state_key=ch["state_key"])
    ok = tg.send_video_file(chat, path, caption)
    try:
        os.remove(path)
    except OSError:
        pass
    if ok:
        state[ch["state_key"]].append(info["id"])
        _mark_posted(ch["state_key"], state)
        print(f"[{ch['name']}] free film: {info['title']}")


def _fb_winner(state):
    """Pick which channel crossposts to FB this run (round-robin)."""
    idx = state.get("_fb_rotation_idx", 0) % len(FB_ROTATION)
    return FB_ROTATION[idx]


def _advance_fb_rotation(state):
    state["_fb_rotation_idx"] = (state.get("_fb_rotation_idx", 0) + 1) % len(FB_ROTATION)


def main():
    state = load_state()
    # Channel order randomized each run so the bot looks less mechanical
    channels = CHANNELS[:]
    random.shuffle(channels)
    posted_anything = False

    for ch in channels:
        sk = ch["state_key"]
        ok_to_post, why = _should_post_now(sk, state)
        if not ok_to_post:
            print(f"[skip] {ch['name']}: {why}")
            continue
        try:
            _humanize_sleep()
            if ch["kind"] == "movie":
                post_movie(ch, state)
            elif ch["kind"] == "trailer":
                post_trailer(ch, state)
            elif ch["kind"] == "free":
                post_free(ch, state)
            posted_anything = True
        except Exception as e:
            print(f"[error] {ch['name']}: {e}")

    if posted_anything:
        _advance_fb_rotation(state)
    save_state(state)
    print("done.")


if __name__ == "__main__":
    main()
