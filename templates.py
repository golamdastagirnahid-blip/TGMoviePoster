"""Caption templates for Telegram + Facebook (SEO-optimized).
Each channel gets its own branded footer. Facebook captions include
keyword hashtags for SEO discoverability.
"""
import random
import re

# All Movie Bell channels — used in cross-promo footer
ALL_CHANNELS = {
    "main": ("Movie Bell", "https://t.me/moviebell20"),
    "pro": ("Movie Bell Pro", "https://t.me/MovieBellPro"),
    "max": ("Movie Bell Max", "https://t.me/MovieBellMax"),
    "us": ("Movie Bell US", "https://t.me/MovieBellUS"),
    "uk": ("Movie Bell UK", "https://t.me/MovieBellUK"),
}
FB_PAGE_URL = "https://www.facebook.com/MovieBell"  # adjust if your handle differs

# ---------------------------------------------------------------------------
# Telegram templates (Markdown)
# ---------------------------------------------------------------------------
INFO_TEMPLATES = [
    "🎬 *{title}* ({year})\n\n⭐ Rating: *{rating}/10*\n🎭 Genre: {genres}\n🌍 Language: {language}\n⏱ Runtime: {runtime} min\n\n📝 _{overview}_\n\n🎟 Cast: {cast}\n🎥 [Watch Trailer]({trailer})",
    "🍿 New on the radar: *{title}* ({year})\n\n{overview}\n\n⭐ {rating}/10  |  🎭 {genres}\n👥 Starring: {cast}\n▶️ [Trailer]({trailer})",
    "🔥 *{title}* — {year}\n\n{overview}\n\nGenre: {genres}\nLanguage: {language}\nRating: ⭐ {rating}\nCast: {cast}\n\n🎬 [Watch Trailer]({trailer})",
    "✨ *{title}*  `({year})`\n\n_{overview}_\n\n📊 Rating: {rating}/10\n🎭 {genres}\n🎤 {cast}\n\n🎥 Trailer → {trailer}",
    "🎞 Spotlight: *{title}* ({year})\n\n{overview}\n\n• Rating: ⭐ {rating}\n• Genre: {genres}\n• Cast: {cast}\n• Lang: {language}\n\n[▶ Trailer]({trailer})",
]
TRAILER_TEMPLATES = [
    "🎥 *{title}* ({year}) — Official Trailer\n\n{overview}\n\n▶️ {trailer}",
    "🍿 New trailer drop: *{title}* ({year})\n\n_{overview}_\n\nWatch: {trailer}",
    "🔥 Trailer alert — *{title}* ({year})\n\n{overview}\n\n{trailer}",
]
FREE_TEMPLATES = [
    "🎬 *{title}* ({year}) — Free to watch (Public Domain)\n\n{overview}\n\nEnjoy! 🍿",
    "🆓 Classic film: *{title}* ({year})\n\n_{overview}_\n\nLegally free — Public Domain.",
]


def _safe(m):
    m = dict(m)
    m.setdefault("watch", "")
    m.setdefault("director", "")
    return m


def _tg_footer(state_key):
    """Telegram footer: own channel + 2 sister channels."""
    own = ALL_CHANNELS.get(state_key)
    sisters = [v for k, v in ALL_CHANNELS.items() if k != state_key][:2]
    lines = ["", ""]
    if own:
        lines.append(f"📢 Join *{own[0]}* → {own[1]}")
    if sisters:
        lines.append("")
        lines.append("🎬 More channels:")
        for name, url in sisters:
            lines.append(f"• [{name}]({url})")
    lines.append("")
    lines.append("🌐 Facebook → " + FB_PAGE_URL)
    return "\n".join(lines)


def info_caption(m, state_key="main"):
    m = _safe(m)
    t = random.choice(INFO_TEMPLATES)
    return t.format(**m) + m["watch"] + _tg_footer(state_key)


def trailer_caption(m, state_key="pro"):
    m = _safe(m)
    t = random.choice(TRAILER_TEMPLATES)
    return t.format(**m) + m["watch"] + _tg_footer(state_key)


def free_caption(m, state_key="max"):
    m = _safe(m)
    t = random.choice(FREE_TEMPLATES)
    return t.format(**m) + _tg_footer(state_key)


# ---------------------------------------------------------------------------
# Facebook caption — SEO-optimized (plain text, hashtags, keywords)
# ---------------------------------------------------------------------------

# Genre/keyword → hashtag map (lowercase keys)
GENRE_TAGS = {
    "action": "#ActionMovies",
    "adventure": "#AdventureMovies",
    "animation": "#Animation",
    "comedy": "#Comedy",
    "crime": "#CrimeThriller",
    "documentary": "#Documentary",
    "drama": "#Drama",
    "family": "#FamilyMovie",
    "fantasy": "#Fantasy",
    "history": "#HistoricalFilm",
    "horror": "#HorrorMovies",
    "music": "#MusicalFilm",
    "mystery": "#Mystery",
    "romance": "#RomanceMovies",
    "science fiction": "#SciFi",
    "tv movie": "#TVMovie",
    "thriller": "#Thriller",
    "war": "#WarMovies",
    "western": "#Western",
}

# Always-on hashtags for max reach
EVERGREEN_TAGS = [
    "#Movies", "#MovieReview", "#FilmTwitter", "#NowShowing",
    "#WhatToWatch", "#Cinema", "#MovieNight", "#Trailer", "#MovieFans",
]


def _slug(s):
    """'The Wild Robot' -> 'TheWildRobot' for hashtag use."""
    return re.sub(r"[^A-Za-z0-9]", "", s)


def _build_hashtags(m):
    tags = []
    # Movie-specific (highest SEO value)
    tags.append(f"#{_slug(m['title'])}")
    tags.append(f"#{_slug(m['title'])}{m['year']}")
    tags.append(f"#{m['year']}Movies")
    # Genres
    for g in (m.get("genres") or "").split(","):
        g = g.strip().lower()
        if g in GENRE_TAGS:
            tags.append(GENRE_TAGS[g])
    # Director / lead actor (great for SEO — people search names)
    if m.get("director"):
        tags.append(f"#{_slug(m['director'])}")
    for actor in (m.get("cast") or "").split(",")[:2]:
        actor = actor.strip()
        if actor and actor != "—":
            tags.append(f"#{_slug(actor)}")
    # Evergreen
    tags += EVERGREEN_TAGS
    # Dedup preserve order
    seen, out = set(), []
    for t in tags:
        if t.lower() not in seen and len(t) > 1:
            seen.add(t.lower())
            out.append(t)
    return " ".join(out[:25])  # FB caps useful hashtag visibility ~30


def _strip_markdown(text):
    """Facebook doesn't render Markdown. Strip *, _, backticks, link syntax."""
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1: \2", text)  # [a](b) -> a: b
    text = re.sub(r"[\*_`]", "", text)
    return text


def fb_caption(m):
    """SEO-rich Facebook caption. Long-form for max reach."""
    m = _safe(m)
    director = f"\n🎬 Director: {m['director']}" if m["director"] else ""
    body = (
        f"🎬 {m['title']} ({m['year']})\n"
        f"⭐ Rating: {m['rating']}/10  |  ⏱ {m['runtime']} min  |  🌍 {m['language']}\n"
        f"🎭 Genre: {m['genres']}"
        f"{director}\n"
        f"🎟 Cast: {m['cast']}\n\n"
        f"📝 {m['overview']}\n\n"
        f"🎥 Watch the Trailer: {m['trailer']}"
    )
    if m["watch"]:
        body += "\n" + _strip_markdown(m["watch"])
    # SEO footer with channel mentions
    body += (
        "\n\n———\n"
        "📢 Follow for daily movie picks, trailers & where-to-watch guides.\n"
        f"📱 Telegram: {ALL_CHANNELS['main'][1]}\n\n"
    )
    body += _build_hashtags(m)
    return body
