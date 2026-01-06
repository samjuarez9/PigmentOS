
// === LIBRARY VISUALIZATION ===
const libraryContainer = document.createElement('div');
libraryContainer.id = 'library-container';
libraryContainer.className = 'feed-panel';
libraryContainer.style.marginTop = '15px';
libraryContainer.style.display = 'none'; // Hidden by default
libraryContainer.innerHTML = `
            <div class="panel-header">
                <span class="panel-title">UPCOMING OPTIONS LIBRARY (30 DAYS)</span>
                <div class="library-controls">
                    <button class="view-btn active" data-view="heatmap">HEATMAP</button>
                    <button class="view-btn" data-view="calendar">CALENDAR</button>
                </div>
            </div>
            <div id="library-content" style="padding: 15px; min-height: 300px; position: relative;">
                <!-- Visualization goes here -->
            </div>
        `;

// Insert after feed panel
document.querySelector('.main-content').appendChild(libraryContainer);

// Styles for Library
const style = document.createElement('style');
style.textContent = `
            .library-controls {
                display: flex;
                gap: 10px;
            }
            .view-btn {
                background: transparent;
                border: 1px solid var(--border-color);
                color: #666;
                font-family: var(--font-pixel);
                font-size: 10px;
                padding: 4px 8px;
                cursor: pointer;
            }
            .view-btn.active {
                border-color: var(--accent-cyan);
                color: var(--accent-cyan);
                background: rgba(0, 255, 255, 0.1);
            }
            .heatmap-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(40px, 1fr));
                gap: 2px;
            }
            .heatmap-cell {
                aspect-ratio: 1;
                background: #1a1a1a;
                border-radius: 2px;
                position: relative;
                cursor: pointer;
            }
            .heatmap-cell:hover::after {
                content: attr(data-tooltip);
                position: absolute;
                bottom: 100%;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(0,0,0,0.9);
                border: 1px solid var(--border-color);
                padding: 5px;
                font-size: 10px;
                white-space: pre;
                z-index: 10;
                pointer-events: none;
            }
        `;
document.head.appendChild(style);

async function fetchLibraryData(ticker) {
    const content = document.getElementById('library-content');
    content.innerHTML = '<div class="loading-message"><div class="spinner"></div><div>Fetching Option Chain...</div></div>';
    libraryContainer.style.display = 'flex';

    try {
        const res = await fetch(`${API_BASE_URL}/api/library/options?symbol=${ticker}`);
        const json = await res.json();

        if (json.error) throw new Error(json.error);

        renderLibrary(json.data);
    } catch (e) {
        content.innerHTML = `<div style="color: var(--alert-red); text-align: center;">Error: ${e.message}</div>`;
    }
}

function renderLibrary(data) {
    const content = document.getElementById('library-content');
    content.innerHTML = '';

    // Simple Heatmap of OI by Expiry/Strike
    // Group by Expiry
    const expiries = Object.keys(data).sort();

    let html = '<div style="display: flex; flex-direction: column; gap: 10px; overflow-x: auto;">';

    expiries.forEach(date => {
        const strikes = data[date];
        // Sort by strike
        strikes.sort((a, b) => a.s - b.s);

        // Calculate max OI for this expiry to normalize color
        const maxOI = Math.max(...strikes.map(s => s.oi));

        html += `
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div style="width: 80px; font-size: 10px; color: #888;">${date}</div>
                        <div style="flex: 1; display: flex; gap: 2px; height: 20px;">
                `;

        strikes.forEach(s => {
            // Normalize OI 0-1
            const intensity = maxOI > 0 ? (s.oi / maxOI) : 0;
            // Color: Blue for Calls, Pink for Puts? 
            // Actually strikes have both. We should probably sum them or show dominant?
            // Let's just show Total OI intensity (White/Cyan)
            const color = `rgba(0, 255, 255, ${0.1 + (intensity * 0.9)})`;

            html += `
                        <div style="flex: 1; background: ${color};" 
                             title="Strike: ${s.s} | OI: ${s.oi} | Vol: ${s.v}">
                        </div>
                    `;
        });

        html += `</div></div>`;
    });

    html += '</div>';
    content.innerHTML = html;
}

// Hook into selection change
const originalHandler = tickerSelector.onchange; // Wait, we added event listener
// We need to add this call to the existing event listener
