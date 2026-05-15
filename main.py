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
# ----------------------------------------------------------------------------
# FACEBOOK STRATEGY (maximize-but-safe)
# ----------------------------------------------------------------------------
# Every fb-eligible Telegram post is queued for crossposting. We then drain
# the queue under two safety rules so Facebook's algorithm doesn't down-rank
# us for spam-like behavior:
#   - FB_MIN_GAP_MIN: minimum minutes between two consecutive FB posts.
#   - FB_DAILY_CAP:   max FB posts in a single UTC day.
# Sweet-spot research: Facebook Pages get best organic reach posting
# 5-15 times/day with >=30 min spacing. We aim at the high end of safe.
# ----------------------------------------------------------------------------
FB_MIN_GAP_MIN = 25         # min minutes between two FB posts
FB_DAILY_CAP = 18           # never exceed this many FB posts in a UTC day
FB_ROTATION = ["main", "us", "uk"]  # preferred draining order

# Manual trigger detection — bypass humanize gates so the button works instantly.
# GitHub Actions sets GITHUB_EVENT_NAME=workflow_dispatch when you click "Run workflow".
# You can also force this locally by setting MANUAL_RUN=1.
MANUAL_RUN = (
    os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
    or os.environ.get("MANUAL_RUN") == "1"
)

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
    for k, v in state.items():
        if isinstance(v, list):
            state[k] = v[-MAX_HISTORY:]
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
    """Humanized gate: cooldown elapsed + within active hour window.
    Manual triggers bypass all gates for instant testing.
    """
    if MANUAL_RUN:
        return True, "manual run (gates bypassed)"
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
    """Random 30s-4min pause to simulate human composing time.
    Manual triggers use a tiny pause (1-3s) so the test run finishes fast.
    """
    if MANUAL_RUN:
        time.sleep(random.uniform(1, 3))
        return
    time.sleep(random.uniform(30, 240))


def _release_key(c):
    """Sort key: newest release first, then highest popularity as tiebreaker."""
    return (c.get("release_date") or "", c.get("popularity") or 0)


def pick_unposted(candidates, posted_ids):
    """Always pick the NEWEST unposted candidate (latest release_date first).
    Popularity breaks ties when several movies share a release date.
    """
    candidates = sorted(candidates, key=_release_key, reverse=True)
    for c in candidates:
        if c["id"] not in posted_ids:
            return c
    return None


def get_pool(spec):
    """Build a candidate pool. We always merge multiple sources so the freshest
    theatrical releases + newly-discovered titles are all considered, and
    pick_unposted picks the newest one.
    """
    if spec == "now_playing":
        # Latest in cinemas + recently released globally (sorted desc by date)
        latest = tmdb.discover(sort_by="primary_release_date.desc")
        return tmdb.now_playing() + latest + tmdb.discover()
    if isinstance(spec, dict) and "discover" in spec:
        kwargs = dict(spec["discover"])
        # Always also pull the freshest releases for that region/language
        latest_kwargs = dict(kwargs)
        latest_kwargs["sort_by"] = "primary_release_date.desc"
        return tmdb.discover(**latest_kwargs) + tmdb.discover(**kwargs)
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
        _mark_posted(ch["state_key"], state)
        # Stash for potential FB crosspost at end of run
        if ch["fb"]:
            FB_QUEUE.append({"ch": ch, "m": m, "details": details})


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


# Queue of fb-eligible posts collected during a run.
FB_QUEUE = []


def _fb_state(state):
    """Reset daily counter at UTC date change."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fs = state.setdefault("_fb", {"last_ts": "", "date": today, "count": 0})
    if fs.get("date") != today:
        fs["date"] = today
        fs["count"] = 0
    return fs


def _fb_minutes_since_last(fs):
    last = fs.get("last_ts") or ""
    if not last:
        return 1e9
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() / 60
    except Exception:
        return 1e9


def _crosspost_one(item, state):
    """Crosspost a single queued item; returns True on success."""
    m = item["m"]
    fb_imgs = tmdb.fb_images(item["details"], count=4)
    if not fb_imgs:
        print(f"[fb] no images for {m['title']}")
        return False
    fb_text = templates.fb_caption(m)
    if not fb.post_album(fb_imgs, fb_text):
        return False
    print(f"[fb] posted ({item['ch']['state_key']}): {m['title']}")
    fs = _fb_state(state)
    fs["last_ts"] = datetime.now(timezone.utc).isoformat()
    fs["count"] = fs.get("count", 0) + 1
    return True


def _drain_fb_queue(state):
    """Crosspost as many queued items as safety rules allow.
    Order: preferred channel from rotation first, then the rest.
    Safety: min gap between FB posts + daily cap.
    """
    if not FB_QUEUE:
        return
    fs = _fb_state(state)
    # Drain order: rotation winner first, then others by FB_ROTATION order
    idx = state.get("_fb_rotation_idx", 0) % len(FB_ROTATION)
    priority = FB_ROTATION[idx:] + FB_ROTATION[:idx]
    queue = sorted(
        FB_QUEUE,
        key=lambda it: priority.index(it["ch"]["state_key"]) if it["ch"]["state_key"] in priority else 999,
    )
    for item in queue:
        if fs["count"] >= FB_DAILY_CAP:
            print(f"[fb] daily cap reached ({FB_DAILY_CAP}); stopping")
            break
        gap = _fb_minutes_since_last(fs)
        if gap < FB_MIN_GAP_MIN:
            wait_s = (FB_MIN_GAP_MIN - gap) * 60
            # On scheduled runs, just skip leftover items (next cron picks up)
            if not MANUAL_RUN and wait_s > 120:
                print(f"[fb] skipping {item['m']['title']} (gap {gap:.0f}m < {FB_MIN_GAP_MIN}m)")
                continue
            # Manual run: wait so user sees all queued posts
            print(f"[fb] waiting {wait_s:.0f}s for safe gap")
            time.sleep(wait_s)
        _crosspost_one(item, state)
        # advance rotation index by 1 so next run prefers a different source
        state["_fb_rotation_idx"] = (state.get("_fb_rotation_idx", 0) + 1) % len(FB_ROTATION)


def main():
    if MANUAL_RUN:
        print("[manual] workflow_dispatch detected -> bypassing cooldowns & humanize sleeps")
    state = load_state()
    FB_QUEUE.clear()
    # Channel order randomized each run so the bot looks less mechanical
    channels = CHANNELS[:]
    random.shuffle(channels)

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
        except Exception as e:
            print(f"[error] {ch['name']}: {e}")

    _drain_fb_queue(state)
    save_state(state)
    print("done.")


if __name__ == "__main__":
    main()
