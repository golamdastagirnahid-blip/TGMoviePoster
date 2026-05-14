"""Caption templates. Edit emojis/wording to match your channel vibe.
Add affiliate links / your channel branding in FOOTER."""
import random

FOOTER = "{watch}\n\n📢 Join @YOURCHANNEL for daily updates"

INFO_TEMPLATES = [
    "🎬 *{title}* ({year})\n\n⭐ IMDb-style Rating: *{rating}/10*\n🎭 Genre: {genres}\n🌍 Language: {language}\n⏱ Runtime: {runtime} min\n\n📝 _{overview}_\n\n🎟 Cast: {cast}\n🎥 [Watch Trailer]({trailer})",
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
    return m

def info_caption(m):
    m = _safe(m)
    t = random.choice(INFO_TEMPLATES)
    return t.format(**m) + FOOTER.format(**m)

def trailer_caption(m):
    m = _safe(m)
    t = random.choice(TRAILER_TEMPLATES)
    return t.format(**m) + FOOTER.format(**m)

def free_caption(m):
    m = _safe(m)
    t = random.choice(FREE_TEMPLATES)
    return t.format(**m) + FOOTER.format(**m)
