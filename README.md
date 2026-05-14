# TGMoviePoster — 5-Channel Telegram Movie Auto-Poster

Fully automated, free forever, runs on GitHub Actions. Posts HD posters + movie details
to 5 Telegram channels on a schedule. 100% safe content (TMDB + YouTube + Internet Archive)
so your channels stay alive and stay **eligible for Telegram monetization**.

## What gets posted

| # | Channel | Source | What it posts |
|---|---------|--------|---------------|
| 1 | New Movies (Worldwide) | TMDB `now_playing` | HD poster + title, year, rating, genre, plot, cast, trailer link |
| 2 | Bollywood / Hindi | TMDB discover (lang=hi) | Same as above, Hindi movies only |
| 3 | Hollywood | TMDB discover (lang=en) | Same as above, English movies only |
| 4 | Trailers | TMDB + YouTube | Poster + embedded trailer link |
| 5 | Free Movies (Public Domain) | Internet Archive | **Actual video file** uploaded to channel (legal, free) |

Posts are randomized in tone (5+ caption templates) so they don't look bot-like.

## Setup (one-time, ~15 minutes, no coding)

### Step 1 — Create 5 Telegram channels
1. Open Telegram → New Channel → make it **Public** (easier) or Private
2. Repeat for all 5. Name them whatever you like.
3. For each channel: Settings → Administrators → Add your bot → give it **Post Messages** permission.
4. Note each channel's username (e.g. `@mymovies1`) or numeric ID.

### Step 2 — Fork / upload this repo to your GitHub
1. Create a new **private** repo on GitHub called `tg-movie-poster`.
2. Upload all files from this folder to it (drag-drop on GitHub web works).

### Step 3 — Add secrets in GitHub
Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**.
Add these one by one:

| Secret name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Your bot token from @BotFather |
| `TMDB_API_KEY` | Your TMDB v3 API key |
| `CHANNEL_NEW` | `@yourchannel1` (or `-100123456789`) |
| `CHANNEL_HINDI` | `@yourchannel2` |
| `CHANNEL_HOLLYWOOD` | `@yourchannel3` |
| `CHANNEL_TRAILERS` | `@yourchannel4` |
| `CHANNEL_FREE` | `@yourchannel5` |

### Step 4 — Turn it on
1. In your repo, go to **Actions** tab → enable workflows.
2. Click **Movie Poster** workflow → **Run workflow** (manual test).
3. Check your channels — posts should appear within 1 minute.
4. After that it auto-runs every 2 hours forever. Free.

## How to change posting frequency
Edit `.github/workflows/poster.yml` → change the `cron:` line.
Default `0 */2 * * *` = every 2 hours.

## How duplicates are prevented
`posted.json` stores IDs of already-posted movies. The workflow commits it back
to your repo after each run. No database needed.

## Cost
**$0 forever.** GitHub Actions gives 2,000 free minutes/month for private repos
(unlimited for public). Each run uses ~1 minute. 12 runs/day = 360 min/month.

## Monetization tips
- Grow each channel to 1,000+ subs → eligible for Telegram Ad Revenue / Stars
- Post times: bot already randomizes, but peak hours (6–10pm local) get best reach
- Pin a "What this channel is" message manually in each
- Add your own affiliate links (Amazon Prime / Netflix referral) in caption footer — edit `templates.py`
