/* SunoSmart — Search and Suggest AJAX handlers */

const URL_PREFIX = document.body.dataset.urlPrefix || '';
const searchForm = document.getElementById('searchForm');
const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const searchResults = document.getElementById('searchResults');
const suggestForm = document.getElementById('suggestForm');
const suggestInput = document.getElementById('suggestInput');
const suggestMsg = document.getElementById('suggestMsg');

// --- Search ---

searchForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = searchInput.value.trim();
    if (!query || query.length < 2) return;

    searchBtn.disabled = true;
    searchResults.innerHTML = `
        <div class="result-loading">
            <div class="spinner"></div>
            <div>Searching the knowledge base...</div>
        </div>`;

    try {
        const res = await fetch(URL_PREFIX + '/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query }),
        });
        const data = await res.json();
        if (data.error) {
            searchResults.innerHTML = `<div class="result-answer" style="color:var(--red)">${data.error}</div>`;
            return;
        }
        renderResults(data);
    } catch (err) {
        searchResults.innerHTML = `<div class="result-answer" style="color:var(--red)">Something went wrong. Please try again.</div>`;
    } finally {
        searchBtn.disabled = false;
    }
});

function renderResults(data) {
    // Parse the raw answer text — find citations and bare URLs, escape everything else
    const raw = data.answer;
    const citationRe = /\[(\d+:\d+)\]\s*"([^"]+)"\s*-?\s*(https:\/\/youtube\.com\/watch\?v=[^\s]+)/g;
    const bareUrlRe = /(https:\/\/youtube\.com\/watch\?v=[^\s]+)/g;

    // First pass: collect all citation spans so we can skip them in the bare-URL pass
    const citationSpans = [];
    let m;
    while ((m = citationRe.exec(raw)) !== null) {
        citationSpans.push({ start: m.index, end: m.index + m[0].length,
            ts: m[1], title: m[2], url: m[3] });
    }

    // Build HTML by walking through the text
    let html = '';
    let pos = 0;

    function addText(text) {
        // Within a text segment, linkify bare YouTube URLs that aren't already part of a citation
        let last = 0;
        let um;
        const localRe = new RegExp(bareUrlRe.source, 'g');
        while ((um = localRe.exec(text)) !== null) {
            html += escapeHtml(text.substring(last, um.index));
            html += `<a href="${um[1]}" target="_blank" rel="noopener" class="yt-link">${escapeHtml(um[1])}</a>`;
            last = um.index + um[0].length;
        }
        html += escapeHtml(text.substring(last));
    }

    for (const span of citationSpans) {
        // Add any text before this citation
        if (span.start > pos) addText(raw.substring(pos, span.start));
        // Add the citation as a clickable link
        html += `<a href="${span.url}" target="_blank" rel="noopener" class="yt-link citation-link">&#9654; [${escapeHtml(span.ts)}] ${escapeHtml(span.title)}</a>`;
        pos = span.end;
    }
    // Add remaining text
    if (pos < raw.length) addText(raw.substring(pos));

    // Convert newlines to paragraphs
    html = html.split('\n').filter(l => l.trim()).map(l => `<p>${l}</p>`).join('');

    let result = `<div class="result-answer">${html}`;

    // Citation cards at the bottom
    if (data.citations && data.citations.length > 0) {
        result += `<div class="result-citations"><h4>Sources</h4>`;
        for (const c of data.citations) {
            result += `
            <a href="${c.url}" target="_blank" rel="noopener" class="citation-card">
                <span class="timestamp">&#9654; ${escapeHtml(c.timestamp)}</span>
                <span class="video-title">${escapeHtml(c.video_title)}</span>
                <div class="context">${escapeHtml((c.context || '').substring(0, 200))}</div>
            </a>`;
        }
        result += `</div>`;
    }

    result += `</div>`;
    searchResults.innerHTML = result;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// --- Suggest ---

suggestForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = suggestInput.value.trim();
    if (!url) return;

    suggestMsg.textContent = 'Submitting...';
    suggestMsg.className = 'suggest-msg';

    try {
        const res = await fetch(URL_PREFIX + '/suggest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url }),
        });
        const data = await res.json();
        if (data.error) {
            suggestMsg.textContent = data.error;
            suggestMsg.className = 'suggest-msg error';
        } else {
            suggestMsg.textContent = data.message;
            suggestMsg.className = 'suggest-msg success';
            suggestInput.value = '';
        }
    } catch (err) {
        suggestMsg.textContent = 'Something went wrong. Please try again.';
        suggestMsg.className = 'suggest-msg error';
    }
});
