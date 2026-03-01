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
    const raw = data.answer;

    // All link patterns matched on RAW text (before HTML escaping)
    const linkPatterns = [
        // [MM:SS] "Title" - URL
        { re: /\[(\d+:\d+)\]\s*"([^"]+)"\s*-?\s*(https:\/\/youtube\.com\/watch\?v=[^\s)]+)/g,
          render: (m) => `<a href="${m[3]}" target="_blank" rel="noopener" class="yt-link citation-link">&#9654; [${escapeHtml(m[1])}] ${escapeHtml(m[2])}</a>` },
        // Markdown links [text](url)
        { re: /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
          render: (m) => `<a href="${m[2]}" target="_blank" rel="noopener" class="yt-link">${escapeHtml(m[1])}</a>` },
        // Bare YouTube URLs
        { re: /(https:\/\/youtube\.com\/watch\?v=[^\s)]+)/g,
          render: (m) => `<a href="${m[1]}" target="_blank" rel="noopener" class="yt-link">${escapeHtml(m[1])}</a>` },
    ];

    function processLine(line) {
        // Find all link matches across all patterns, pick the earliest non-overlapping ones
        const matches = [];
        for (const pat of linkPatterns) {
            pat.re.lastIndex = 0;
            let m;
            while ((m = pat.re.exec(line)) !== null) {
                matches.push({ start: m.index, end: m.index + m[0].length, html: pat.render(m) });
            }
        }
        // Sort by position, remove overlaps
        matches.sort((a, b) => a.start - b.start);
        const kept = [];
        for (const m of matches) {
            if (kept.length === 0 || m.start >= kept[kept.length - 1].end) kept.push(m);
        }
        // Build output: escaped text + link HTML
        let out = '';
        let pos = 0;
        for (const m of kept) {
            if (m.start > pos) out += escapeHtml(line.substring(pos, m.start));
            out += m.html;
            pos = m.end;
        }
        if (pos < line.length) out += escapeHtml(line.substring(pos));

        // Markdown bold
        out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        return out;
    }

    const lines = raw.split('\n');
    let html = '';
    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        // Markdown headers
        const h1 = trimmed.match(/^#\s+(.*)$/);
        const h2 = trimmed.match(/^##\s+(.*)$/);
        const h3 = trimmed.match(/^#{3,}\s+(.*)$/);
        if (h3) { html += `<p><strong>${processLine(h3[1])}</strong></p>`; }
        else if (h2) { html += `<h4>${processLine(h2[1])}</h4>`; }
        else if (h1) { html += `<h3>${processLine(h1[1])}</h3>`; }
        else { html += `<p>${processLine(trimmed)}</p>`; }
    }

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
