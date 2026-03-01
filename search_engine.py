"""Two-stage search engine: keyword pre-filter + Claude Haiku synthesis."""
import anthropic

import config
import database


# In-memory cache of all segments grouped by video
_segment_cache = None
_video_index = None


def _build_cache():
    """Load all segments from DB into memory for fast keyword search."""
    global _segment_cache, _video_index
    rows = database.get_all_segments_with_video_info()
    _segment_cache = {}
    _video_index = {}
    for row in rows:
        tid = row["transcript_id"]
        vid = row["video_id"]
        if tid not in _segment_cache:
            _segment_cache[tid] = []
            _video_index[tid] = {"video_id": vid, "title": row["video_title"]}
        _segment_cache[tid].append({
            "text": row["text"],
            "start": row["start_time"],
            "duration": row["duration"],
            "index": row["segment_index"],
        })
    # Sort segments within each transcript
    for tid in _segment_cache:
        _segment_cache[tid].sort(key=lambda s: s["index"])


def refresh_cache():
    """Force-refresh the in-memory segment cache."""
    _build_cache()


def _ensure_cache():
    if _segment_cache is None:
        _build_cache()


def seconds_to_timestamp(s):
    m = int(s) // 60
    sec = int(s) % 60
    return f"{m}:{sec:02d}"


def seconds_to_yt_param(s):
    m = int(s) // 60
    sec = int(s) % 60
    return f"{m}m{sec}s"


def keyword_search(query, context_window=None, max_results=None):
    """Stage 1: keyword pre-filter across all transcripts."""
    _ensure_cache()
    if context_window is None:
        context_window = config.SEARCH_CONTEXT_WINDOW
    if max_results is None:
        max_results = config.MAX_SEARCH_RESULTS

    query_lower = query.lower()
    keywords = query_lower.split()
    if not keywords:
        return []

    results = []

    for tid, segments in _segment_cache.items():
        info = _video_index[tid]
        vid = info["video_id"]
        title = info["title"]

        for i, seg in enumerate(segments):
            start_idx = max(0, i - context_window)
            end_idx = min(len(segments), i + context_window + 1)
            window_text = " ".join(s["text"] for s in segments[start_idx:end_idx]).lower()

            if all(kw in window_text for kw in keywords):
                context_text = " ".join(s["text"] for s in segments[start_idx:end_idx])
                # Offset timestamp 5 seconds earlier for context
                adjusted_start = max(0, seg["start"] - 5)
                results.append({
                    "video_id": vid,
                    "video_title": title,
                    "timestamp": seconds_to_timestamp(adjusted_start),
                    "yt_param": seconds_to_yt_param(adjusted_start),
                    "url": f"https://youtube.com/watch?v={vid}&t={seconds_to_yt_param(adjusted_start)}",
                    "context": context_text,
                    "score": sum(window_text.count(kw) for kw in keywords),
                    "start": seg["start"],
                })

    # Deduplicate: best match per 60-second window per video
    deduped = []
    seen = set()
    results.sort(key=lambda r: r["score"], reverse=True)
    for r in results:
        bucket = (r["video_id"], int(r["start"]) // 60)
        if bucket not in seen:
            seen.add(bucket)
            deduped.append(r)
        if len(deduped) >= max_results:
            break

    return deduped


def ai_answer(query, segments):
    """Stage 2: send pre-filtered segments to Claude Haiku for synthesis."""
    if not config.ANTHROPIC_API_KEY:
        return {
            "answer": "AI answers are not available (API key not configured).",
            "citations": segments[:5],
        }

    # Format segments for the prompt
    formatted = []
    for s in segments:
        formatted.append(
            f'[Video: "{s["video_title"]}" | ID: {s["video_id"]} | Timestamp: {s["timestamp"]}]\n'
            f'"{s["context"]}"'
        )
    segments_text = "\n\n".join(formatted)

    prompt = f"""You are SunoSmart, an expert assistant for Suno AI music creation.
Answer the user's question using ONLY the transcript excerpts provided below.

For each piece of information in your answer, cite the source using this exact format:
[MM:SS] "Video Title" - https://youtube.com/watch?v=VIDEO_ID&t=MmSs

Make sure timestamps are 5-10 seconds before the actual answer starts so the user has context.

If the transcripts don't contain enough information to answer, say so honestly and suggest which video might be most relevant.

Keep your answer concise and practical. Users want actionable Suno tips.

=== TRANSCRIPT EXCERPTS ===
{segments_text}

=== USER QUESTION ===
{query}"""

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    answer_text = response.content[0].text

    return {
        "answer": answer_text,
        "citations": segments[:5],
    }


def search(query):
    """Full two-stage search: keyword filter then AI synthesis."""
    segments = keyword_search(query)

    if not segments:
        # Fallback: send video topic index for best-effort answer
        _ensure_cache()
        topic_index = "\n".join(
            f"- [{info['title']}](https://youtube.com/watch?v={info['video_id']})"
            for info in _video_index.values()
        )
        if config.ANTHROPIC_API_KEY:
            client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
            response = client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=512,
                messages=[{"role": "user", "content": (
                    f"You are SunoSmart. The user asked: \"{query}\"\n\n"
                    f"No exact transcript matches were found. Here are the videos in our knowledge base:\n{topic_index}\n\n"
                    f"Based on the video titles, suggest which video(s) might contain the answer. "
                    f"Be honest that you couldn't find an exact match.\n\n"
                    f"IMPORTANT: Always include clickable links using the full YouTube URLs provided above. "
                    f"Use markdown link format: [Video Title](https://youtube.com/watch?v=VIDEO_ID)"
                )}],
            )
            return {
                "answer": response.content[0].text,
                "citations": [],
                "no_exact_match": True,
            }
        return {
            "answer": "No results found for your query. Try different keywords.",
            "citations": [],
            "no_exact_match": True,
        }

    result = ai_answer(query, segments)
    result["no_exact_match"] = False
    return result
