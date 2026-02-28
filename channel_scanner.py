"""Background job: scan tracked YouTube channels for new videos."""
import logging

import database
import search_engine
import transcript_fetcher

logger = logging.getLogger(__name__)


def scan_channels():
    """Scan all active YouTube channel sources for new videos."""
    sources = database.get_active_sources(source_type="channel")
    new_videos = []

    for source in sources:
        channel_url = source["url"]
        source_id = source["id"]
        channel_name = source["channel_name"] or ""

        logger.info(f"Scanning channel: {channel_name} ({channel_url})")

        videos = transcript_fetcher.list_channel_videos(channel_url)
        for video in videos:
            existing = database.get_transcript_by_video_id(video["id"])
            if existing:
                continue

            logger.info(f"  New video: {video['title']} ({video['id']})")
            success, msg = transcript_fetcher.fetch_transcript(
                video_id=video["id"],
                title=video["title"],
                duration=video["duration"],
                source_id=source_id,
                channel_name=channel_name,
            )
            if success and msg != "already_exists":
                new_videos.append(video)
                logger.info(f"    Fetched: {msg}")
            elif not success:
                logger.warning(f"    Failed: {msg}")

        database.update_source_scanned(source_id)

    # Refresh search cache if new content was added
    if new_videos:
        search_engine.refresh_cache()
        logger.info(f"Scan complete: {len(new_videos)} new videos added")
    else:
        logger.info("Scan complete: no new videos found")

    return new_videos
