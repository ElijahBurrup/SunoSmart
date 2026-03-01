"""Fetch YouTube video transcripts and store in database."""
import json
import subprocess

from youtube_transcript_api import YouTubeTranscriptApi

import config
import database


def fetch_transcript(video_id, title=None, duration=None, source_id=None, channel_name=None):
    """Fetch a single video transcript and store in DB. Returns (success, message)."""
    existing = database.get_transcript_by_video_id(video_id)
    if existing:
        return True, "already_exists"

    api = YouTubeTranscriptApi()
    try:
        raw = api.fetch(video_id, languages=["en"])
        segments = [{"text": s.text, "start": s.start, "duration": s.duration} for s in raw]
    except Exception as e:
        return False, str(e)

    if not title:
        title = f"Video {video_id}"

    transcript = database.create_transcript(
        source_id=source_id,
        video_id=video_id,
        title=title,
        duration=duration,
        channel_name=channel_name,
        segment_count=len(segments),
    )
    if transcript is None:
        return False, "failed to create transcript record"

    database.insert_segments(transcript["id"], segments)

    # Save JSON backup
    config.TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = config.TRANSCRIPTS_DIR / f"{video_id}.json"
    with open(str(backup_path), "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False)

    return True, f"ok ({len(segments)} segments)"


def list_channel_videos(channel_url, max_videos=50):
    """Use yt-dlp to list recent videos from a YouTube channel."""
    try:
        result = subprocess.run(
            [
                "python", "-m", "yt_dlp",
                "--flat-playlist",
                f"--playlist-end={max_videos}",
                "--print", "%(id)s|%(title)s|%(duration)s",
                f"{channel_url}/videos",
            ],
            capture_output=True, text=True, timeout=300,
        )
        videos = []
        for line in result.stdout.strip().split("\n"):
            if not line or "|" not in line:
                continue
            parts = line.split("|", 2)
            if len(parts) >= 3:
                vid_id = parts[0].strip()
                title = parts[1].strip()
                try:
                    duration = int(float(parts[2].strip()))
                except (ValueError, TypeError):
                    duration = 0
                videos.append({"id": vid_id, "title": title, "duration": duration})
        return videos
    except Exception as e:
        return []
