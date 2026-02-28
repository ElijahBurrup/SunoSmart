"""Generate daily news articles from new knowledge base content."""
import json
import logging
from datetime import datetime, timedelta, timezone

import anthropic

import config
import database

logger = logging.getLogger(__name__)


def generate_daily_news():
    """Analyze content added in the last 24 hours and generate 1-3 news articles."""
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    new_transcripts = database.get_transcripts_since(since)

    if not new_transcripts:
        logger.info("No new content today, skipping news generation")
        return []

    # Build context of new content
    new_content_parts = []
    for t in new_transcripts:
        segments = database.get_segments_for_transcript(t["id"])
        # Take a representative sample (first 50 segments) to keep prompt manageable
        sample = segments[:50]
        text = " ".join(s["text"] for s in sample)
        new_content_parts.append(
            f'Video: "{t["title"]}" (ID: {t["video_id"]})\n'
            f'Excerpt: {text[:2000]}'
        )
    new_content = "\n\n---\n\n".join(new_content_parts)

    # Build existing topic summary
    all_transcripts = database.get_all_transcripts()
    existing_titles = [t["title"] for t in all_transcripts if t["video_id"] not in
                       {nt["video_id"] for nt in new_transcripts}]
    topic_summary = "\n".join(f"- {title}" for title in existing_titles[:50])

    prompt = f"""You are SunoSmart's news editor. Analyze the following new transcript content that was added to our Suno AI knowledge base today.

Compare it to the existing topics we already cover (listed below) and identify the 1-3 most interesting, novel, or practically useful findings for Suno AI users.

Write each finding as a short news article in this JSON format:
[
  {{
    "title": "Catchy headline here",
    "summary": "One sentence summary for the feed",
    "content": "Full article (150-250 words) in HTML with <p>, <strong>, <em> tags. Include the key insight, why it matters, and a source citation with timestamp link like: <a href='https://youtube.com/watch?v=VIDEO_ID&t=MmSs'>[MM:SS] Video Title</a>"
  }}
]

Write in an engaging, enthusiast-community tone. Return ONLY valid JSON, no other text.

=== EXISTING TOPICS (for novelty comparison) ===
{topic_summary}

=== NEW CONTENT ADDED TODAY ===
{new_content}"""

    if not config.ANTHROPIC_API_KEY:
        logger.warning("No API key, skipping news generation")
        return []

    try:
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        # Extract JSON from response (handle markdown code blocks)
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        articles = json.loads(text)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        video_ids = json.dumps([t["video_id"] for t in new_transcripts])

        created = []
        for article in articles:
            database.create_news_article(
                title=article["title"],
                content=article["content"],
                summary=article.get("summary", ""),
                sources_referenced=video_ids,
                generated_date=today,
            )
            created.append(article["title"])
            logger.info(f"Created news article: {article['title']}")

        return created

    except Exception as e:
        logger.error(f"News generation failed: {e}")
        return []
