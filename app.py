"""SunoSmart — AI-powered Suno knowledge base."""
import hashlib
import re
from urllib.parse import urlparse, parse_qs

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

import config
import database
import search_engine
import scheduler as sched_module

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = config.FLASK_SECRET_KEY

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "admin_login"


class AdminUser(UserMixin):
    def __init__(self, admin_row):
        self.id = admin_row["id"]
        self.email = admin_row["email"]


@login_manager.user_loader
def load_user(user_id):
    conn = database.get_connection()
    row = conn.execute("SELECT * FROM admins WHERE id = ?", (user_id,)).fetchone()
    if row:
        return AdminUser(row)
    return None


# --- Initialize on startup ---
database.initialize_db()
sched_module.init_scheduler()


# --- URL Normalization ---

def normalize_youtube_url(url):
    """Extract a canonical form from YouTube URLs."""
    parsed = urlparse(url)
    host = parsed.hostname or ""

    # Channel URLs
    if "/channel/" in parsed.path:
        channel_id = parsed.path.split("/channel/")[1].split("/")[0]
        return f"youtube:channel:{channel_id}"
    if "/@" in parsed.path:
        handle = parsed.path.split("/@")[1].split("/")[0]
        return f"youtube:handle:{handle}"

    # Video URLs
    if "youtube.com" in host or "youtu.be" in host:
        if "youtu.be" in host:
            video_id = parsed.path.lstrip("/")
        else:
            qs = parse_qs(parsed.query)
            video_id = qs.get("v", [""])[0]
        if video_id:
            return f"youtube:video:{video_id}"

    # Fallback: strip protocol and trailing slash
    return re.sub(r'^https?://(www\.)?', '', url).rstrip("/")


# === PUBLIC ROUTES ===

@app.route("/")
def index():
    news = database.get_latest_news(limit=3)
    return render_template("index.html", news=news)


@app.route("/search", methods=["POST"])
def search_route():
    data = request.get_json() or {}
    query = data.get("query", "").strip()
    if not query or len(query) < 2:
        return jsonify({"error": "Query too short"}), 400
    if len(query) > 500:
        return jsonify({"error": "Query too long"}), 400

    result = search_engine.search(query)
    database.log_search(query, len(result.get("citations", [])), request.remote_addr)

    return jsonify(result)


@app.route("/suggest", methods=["POST"])
def suggest_route():
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL is required"}), 400
    if not re.match(r'https?://(www\.)?(youtube\.com|youtu\.be)/', url):
        return jsonify({"error": "Only YouTube URLs are supported right now"}), 400

    normalized = normalize_youtube_url(url)
    count, status = database.create_suggestion(
        url=url,
        normalized_url=normalized,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent", ""),
    )

    if status == "already_suggested":
        return jsonify({"message": "You've already suggested this source. Thanks!", "count": 0})

    # Auto-approve at 10 unique users
    if count and count >= 10:
        database.auto_approve_suggestion(normalized)
        # TODO: automatically add as a source and trigger scan
        return jsonify({"message": "This source just hit 10 votes and has been auto-approved!", "count": count})

    return jsonify({
        "message": f"Thanks! This source now has {count} vote(s). It will be auto-added at 10.",
        "count": count,
    })


@app.route("/news")
def news_archive():
    page = request.args.get("page", 1, type=int)
    articles, total = database.get_news_archive(page=page)
    total_pages = (total + 9) // 10
    return render_template("news_archive.html", articles=articles, page=page, total_pages=total_pages)


@app.route("/news/<int:article_id>")
def news_article(article_id):
    article = database.get_news_article(article_id)
    if not article:
        return render_template("error.html", message="Article not found"), 404
    return render_template("news_article.html", article=article)


# === ADMIN ROUTES ===

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        admin = database.get_admin_by_email(email)
        if admin and check_password_hash(admin["password_hash"], password):
            login_user(AdminUser(admin))
            return redirect(url_for("admin_dashboard"))
        flash("Invalid credentials", "error")
    return render_template("admin/login.html")


@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    sources = database.get_active_sources()
    suggestions = database.get_suggestion_counts()
    stats = database.get_search_stats()
    transcripts = database.get_all_transcripts()
    return render_template("admin/dashboard.html",
                           sources=sources, suggestions=suggestions,
                           stats=stats, transcripts=transcripts)


@app.route("/admin/sources", methods=["POST"])
@login_required
def admin_add_source():
    url = request.form.get("url", "").strip()
    source_type = request.form.get("type", "channel")
    channel_name = request.form.get("name", "").strip()

    normalized = normalize_youtube_url(url)
    channel_id = None
    if "youtube:channel:" in normalized:
        channel_id = normalized.split("youtube:channel:")[1]
    elif "youtube:handle:" in normalized:
        channel_id = normalized.split("youtube:handle:")[1]

    database.create_source(
        source_type=source_type,
        url=url,
        channel_id=channel_id,
        channel_name=channel_name or None,
        added_by="admin",
    )
    flash(f"Source added: {url}", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/suggestions/<normalized>/approve", methods=["POST"])
@login_required
def admin_approve_suggestion(normalized):
    database.approve_suggestion(normalized)
    flash("Suggestion approved", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/scan", methods=["POST"])
@login_required
def admin_trigger_scan():
    from channel_scanner import scan_channels
    new_videos = scan_channels()
    flash(f"Scan complete: {len(new_videos)} new videos found", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/news", methods=["POST"])
@login_required
def admin_trigger_news():
    from news_generator import generate_daily_news
    articles = generate_daily_news()
    flash(f"Generated {len(articles)} news article(s)", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/logout")
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for("index"))


# === API ===

@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


# === CLI Commands ===

@app.cli.command("create-admin")
def create_admin_cmd():
    """Create an admin user."""
    import click
    email = click.prompt("Email")
    password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
    pw_hash = generate_password_hash(password)
    database.create_admin(email, pw_hash)
    click.echo(f"Admin created: {email}")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
