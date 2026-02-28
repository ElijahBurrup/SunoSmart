# Kingdom Builders AI — SunoSmart

## Project Overview
AI-powered Suno knowledge base with video transcript search, community suggestions, and auto-generated news articles. Users can search across indexed YouTube transcripts using Claude Haiku for intelligent results.

## Tech Stack
- **Framework**: Flask (Python) with Flask-Login
- **Database**: SQLite (data/sunosmart.db)
- **AI**: Anthropic Claude Haiku (claude-haiku-4-5) for search and news generation
- **Transcript Fetching**: yt-dlp, youtube-transcript-api
- **Hosting**: Render (auto-deploy from master branch)
- **Tests**: Playwright (Node.js)

## Key Files
- `app.py` — Flask app factory, Blueprint routes (public search, suggestions, news, admin dashboard)
- `config.py` — Anthropic API key, URL_PREFIX, Flask config (env-driven)
- `database.py` — SQLite schema: sources, transcripts, suggestions, searches, news articles, admins
- `search_engine.py` — Claude Haiku-powered semantic search across transcripts
- `news_generator.py` — Auto-generates news articles from recent transcripts
- `channel_scanner.py` — Scans YouTube channels for new videos, fetches transcripts
- `transcript_fetcher.py` — yt-dlp + youtube-transcript-api transcript extraction
- `scheduler.py` — APScheduler: periodic channel scanning and news generation
- `templates/` — Jinja2 templates (index, news, admin dashboard)
- `static/` — CSS, JS assets
- `tests/sunosmart.spec.js` — Playwright test suite

## Deployment
- **Live URL**: https://sunosmart.onrender.com/sunosmart/
- **URL_PREFIX**: `/sunosmart` (set via env var on Render, empty locally)
- **GitHub**: https://github.com/ElijahBurrup/SunoSmart (master branch)
- **GitHub Account**: ElijahBurrup (elijah@kingdombuilders.ai)
- **Render Service ID**: srv-d6h46uma2pns738affa0
- **Local dev**: `python app.py` → http://localhost:6001 (no URL_PREFIX locally)

## Pre-Commit Checklist
1. Update this CLAUDE.md if architecture, key files, or deployment details changed
2. Run Playwright tests: `npx playwright test`

## Architecture Notes
- All routes use a Flask Blueprint with optional URL_PREFIX for subpath deployment
- Admin section at /admin/dashboard with Flask-Login authentication
- Community suggestion system: users submit YouTube URLs, auto-approved at 10 unique votes
- Scheduler runs channel scans every 4 hours and news generation at midnight UTC
