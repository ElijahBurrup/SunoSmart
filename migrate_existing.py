"""One-time migration: import existing 25 transcripts from SunoKnowledgeBase into the DB."""
import json
import os
import shutil
import sys

# Ensure we can import our modules
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

import config
import database

EXISTING_DIR = os.path.join(os.path.dirname(__file__), "seed_data")
EXISTING_INDEX = os.path.join(EXISTING_DIR, "index.json")
EXISTING_TRANSCRIPTS = os.path.join(EXISTING_DIR, "transcripts")


def migrate():
    database.initialize_db()

    if not os.path.exists(EXISTING_INDEX):
        print(f"ERROR: index.json not found at {EXISTING_INDEX}")
        sys.exit(1)

    with open(EXISTING_INDEX, "r", encoding="utf-8") as f:
        index = json.load(f)

    channel_id = index.get("channel", "UCj83I0PrbdTDmoUXBosTyXg")

    # Create the source channel
    source = database.create_source(
        source_type="channel",
        url=f"https://www.youtube.com/channel/{channel_id}",
        channel_id=channel_id,
        channel_name="Suno AI Tutorial Channel",
        added_by="migration",
    )
    source_id = source["id"]
    print(f"Created source: channel {channel_id} (id={source_id})")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for video in index["videos"]:
        if video.get("status") != "ok":
            print(f"  SKIP (error status): {video['title']}")
            skip_count += 1
            continue

        vid = video["id"]
        title = video["title"]
        duration = video.get("duration", 0)

        # Check if already migrated
        existing = database.get_transcript_by_video_id(vid)
        if existing:
            print(f"  SKIP (exists): {title}")
            skip_count += 1
            continue

        # Load transcript segments from JSON file
        json_path = os.path.join(EXISTING_TRANSCRIPTS, f"{vid}.json")
        if not os.path.exists(json_path):
            print(f"  FAIL (no JSON): {title}")
            fail_count += 1
            continue

        with open(json_path, "r", encoding="utf-8") as f:
            segments = json.load(f)

        # Insert transcript record
        transcript = database.create_transcript(
            source_id=source_id,
            video_id=vid,
            title=title,
            duration=duration,
            channel_name="Suno AI Tutorial Channel",
            segment_count=len(segments),
        )

        # Insert segments
        formatted_segments = []
        for s in segments:
            formatted_segments.append({
                "text": s["text"],
                "start": s["start"],
                "duration": s["duration"],
            })
        database.insert_segments(transcript["id"], formatted_segments)

        # Copy JSON backup
        config.TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        dest_path = config.TRANSCRIPTS_DIR / f"{vid}.json"
        shutil.copy2(json_path, str(dest_path))

        print(f"  OK: {title} ({len(segments)} segments)")
        success_count += 1

    print(f"\nMigration complete: {success_count} imported, {skip_count} skipped, {fail_count} failed")


if __name__ == "__main__":
    migrate()
