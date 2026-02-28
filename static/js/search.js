/* SunoSmart — Search and Suggest AJAX handlers */

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
        const res = await fetch('/search', {
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
    // Convert markdown-style links in the answer to HTML
    let answer = escapeHtml(data.answer);
    // Convert [MM:SS] "Title" - URL patterns to clickable links
    answer = answer.replace(
        /\[(\d+:\d+)\]\s*(?:&quot;|")?([^"&]+?)(?:&quot;|")?\s*-?\s*(https:\/\/youtube\.com\/watch\?v=[^\s<]+)/g,
        '<a href="$3" target="_blank" rel="noopener">[$1] $2</a>'
    );
    // Convert bare YouTube URLs
    answer = answer.replace(
        /(https:\/\/youtube\.com\/watch\?v=[^\s<]+)/g,
        (match) => `<a href="${match}" target="_blank" rel="noopener">${match}</a>`
    );
    // Convert newlines to paragraphs
    answer = answer.split('\n').filter(l => l.trim()).map(l => `<p>${l}</p>`).join('');

    let html = `<div class="result-answer">${answer}`;

    if (data.citations && data.citations.length > 0) {
        html += `<div class="result-citations">
            <h4>Sources</h4>`;
        for (const c of data.citations) {
            html += `
            <a href="${escapeHtml(c.url)}" target="_blank" rel="noopener" class="citation-card" style="display:block;text-decoration:none">
                <span class="timestamp">${escapeHtml(c.timestamp)}</span>
                <span class="video-title">${escapeHtml(c.video_title)}</span>
                <div class="context">${escapeHtml((c.context || '').substring(0, 200))}</div>
            </a>`;
        }
        html += `</div>`;
    }

    html += `</div>`;
    searchResults.innerHTML = html;
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
        const res = await fetch('/suggest', {
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
