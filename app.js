
// app.js

document.addEventListener('DOMContentLoaded', () => {
    console.log('✅ JavaScript is loading and DOMContentLoaded fired!');

    // === GLOBAL CONFIGURATION ===
    const IS_FILE_PROTOCOL = window.location.protocol === 'file:';
    const API_BASE_URL = IS_FILE_PROTOCOL ? 'http://localhost:8001' : '';

    // === CHECK FOR SPRING ANIMATION ===
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('anim') === 'spring') {
        document.querySelector('.terminal-container').classList.add('spring-entrance');
    }

    // === CYBER WATCHDOG (Connection Monitor) ===& Status Grid ===
    function updateSystemStatus() {
        const start = Date.now();

        // 1. Check Latency (Ping)
        fetch(`${API_BASE_URL}/api/ping`)
            .then(response => {
                if (response.ok) {
                    const latency = Date.now() - start;
                    const latencyEl = document.getElementById('latency-value');
                    const dotEl = document.querySelector('.status-dot');

                    if (latencyEl) {
                        latencyEl.textContent = `${latency} ms`;
                        if (latency < 100) latencyEl.style.color = 'var(--primary-color)';
                        else if (latency < 300) latencyEl.style.color = 'var(--warning-color)';
                        else latencyEl.style.color = '#ff3333';
                    }

                    if (dotEl) {
                        dotEl.classList.remove('pulse-red');
                        dotEl.classList.add('pulse-green');
                    }
                } else {
                    throw new Error('Network response was not ok');
                }
            })
            .catch(() => {
                const dotEl = document.querySelector('.status-dot');
                if (dotEl) {
                    dotEl.classList.remove('pulse-green');
                    dotEl.classList.add('pulse-red');
                }
            });

        // 2. Check Service Status
        fetch(`${API_BASE_URL}/api/status`)
            .then(res => res.json())
            .then(data => {
                const statusPoly = document.getElementById('status-poly');
                const statusYfin = document.getElementById('status-yfin');
                const statusRss = document.getElementById('status-rss');
                const statusGamma = document.getElementById('status-gamma');
                const impactDisplay = document.getElementById('impact-display');
                const statusText = document.getElementById('system-status-text');

                let affectedServices = [];

                // Helper to update status item
                const updateItem = (el, statusKey, name) => {
                    if (!el) return;
                    const service = data[statusKey];
                    if (service && service.status === 'OFFLINE') {
                        el.classList.add('offline');
                        affectedServices.push(name);
                    } else {
                        el.classList.remove('offline');
                    }
                };

                updateItem(statusPoly, 'POLY', 'POLYMARKET');
                updateItem(statusYfin, 'YFIN', 'YAHOO FIN');
                updateItem(statusRss, 'RSS', 'INTEL FEED');
                updateItem(statusGamma, 'GAMMA', 'GAMMA WALL');
                updateItem(statusGamma, 'HEATMAP', 'MARKET MAP'); // Map Heatmap to Gamma/YFIN visually or add new item? 
                // Note: Heatmap uses YFIN data mostly, so YFIN status covers it, but we track it separately in backend.
                // For now, we only visualize the 4 main ones in the grid.

                // Update Impact Text
                if (impactDisplay && statusText) {
                    if (affectedServices.length > 0) {
                        statusText.textContent = `FAILURE: ${affectedServices[0]}`;
                        statusText.classList.add('critical');
                        statusText.style.color = '#FF3333';
                    } else {
                        statusText.textContent = 'OPTIMAL';
                        statusText.classList.remove('critical');
                        statusText.style.color = '#00FF41';
                    }
                }
            })
            .catch(err => console.error("Status Fetch Error:", err));
    }

    function startWatchdog() {
        updateSystemStatus(); // Initial check
        setInterval(updateSystemStatus, 5000); // Check every 5 seconds
    }

    // Market Status Button Updater
    function updateMarketStatusBtn() {
        const btn = document.getElementById('market-status-btn');
        if (!btn) return;

        const state = getMarketState();

        // Remove all state classes
        btn.classList.remove('after-market', 'pre-market', 'market-open');

        if (state.isWeekend) {
            btn.textContent = 'WEEKEND';
            btn.classList.add('after-market'); // Orange for weekend
        } else if (state.isMarketHours) {
            btn.textContent = 'OPEN';
            btn.classList.add('market-open');
        } else if (state.isPreMarket) {
            btn.textContent = 'PRE MARKET';
            btn.classList.add('pre-market');
        } else {
            btn.textContent = 'AFTER MARKET';
            btn.classList.add('after-market');
        }
    }

    // Start the Watchdog
    startWatchdog();

    // Start Market Status Updater
    updateMarketStatusBtn();
    setInterval(updateMarketStatusBtn, 30000); // Update every 30 seconds

    // Configuration
    const threatBox = document.getElementById('threat-box');
    const threatLevelSpan = document.getElementById('threat-level');
    const optionsBody = document.getElementById('options-body');
    const insiderList = document.getElementById('insider-list');
    const oddsList = document.getElementById('odds-list');
    const alertsList = document.getElementById('alerts-list');
    const priceTicker = document.getElementById('price-ticker');
    const gaugeValue = document.querySelector('.gauge-value');
    // === Local Storage Persistence ===
    // Load saved ticker or default to 'QQQ'
    const savedTicker = localStorage.getItem('pigment_current_ticker');
    let currentTicker = savedTicker || 'QQQ';

    // Initialize Ticker Dropdown
    // Logic moved to line 192 to consolidate
    if (currentTicker) {
        createTradingViewWidget(currentTicker);
    }
    const gaugeLabel = document.querySelector('.gauge-label');
    const chartHeader = document.querySelector('#live-price-action h2');

    // Global State
    // let currentTicker = 'QQQ'; // Default to QQQ // This line is now handled by the localStorage logic above
    let tvWidget = null;

    // TradingView Widget Integration
    function createTradingViewWidget(ticker) {
        try {
            // Clear container first
            const container = document.getElementById('chart-container');
            if (!container) return;
            container.innerHTML = '';

            // Ensure container has dimensions
            if (container.clientHeight === 0) {
                container.style.height = '400px'; // Force height if missing
            }

            new TradingView.widget({
                "autosize": true,
                "symbol": "NASDAQ:" + ticker,
                "interval": "15",
                "timezone": "Etc/UTC",
                "theme": "dark",
                "style": "1", // Candle style
                "locale": "en",
                "enable_publishing": false,
                "hide_top_toolbar": true,
                "studies": [
                    "MASimple@tv-basicstudies",    // Simple Moving Average
                    "RSI@tv-basicstudies",         // RSI (14-period) - Overbought/Oversold
                    "BB@tv-basicstudies"           // Bollinger Bands (20,2) - Volatility
                ],
                "container_id": "chart-container"
            });

            // MOBILE FIX: Force resize after load to prevent squished graph
            if (window.innerWidth <= 768) {
                setTimeout(() => {
                    const iframe = container.querySelector('iframe');
                    if (iframe) {
                        iframe.style.height = '300px';
                        iframe.style.minHeight = '300px';
                    }
                }, 1000);
            }

            // Mark chart as live
            updateStatus('status-chart', true);
        } catch (e) {
            console.error("TradingView Widget Error:", e);
            updateStatus('status-chart', false);
        }
    }

    // ... (Watchlist code remains same) ...

    // News Feed Logic moved to consolidated function below

    // Watchlist Tickers for Dropdown (Expanded w/ FinTwit Favorites)
    const WATCHLIST_TICKERS = [
        // Mag 7 & Tech Giants
        'NVDA', 'TSLA', 'AAPL', 'MSFT', 'META', 'GOOGL', 'AMZN',

        // Indices & ETFs
        'QQQ', 'SPY', 'DIA', 'IWM', 'VIX', 'ARKK', 'TQQQ', 'SQQQ',

        // Semiconductors & AI Hardware
        'AMD', 'INTC', 'MU', 'QCOM', 'AVGO', 'TSM', 'ARM', 'SMCI',

        // AI & Cloud
        'PLTR', 'SNOW', 'CRM', 'ORCL', 'DDOG', 'NET', 'ZS', 'CRWD',

        // FinTwit Memes & High Volume
        'GME', 'AMC', 'BBBY', 'SOFI', 'HOOD', 'COIN', 'MSTR',

        // EVs & Future Mobility
        'RIVN', 'LCID', 'NIO', 'RKLB', 'F', 'GM',

        // FinTech & Payments
        'SQ', 'PYPL', 'V', 'MA', 'AFRM',

        // Entertainment & Consumer
        'NFLX', 'DIS', 'SPOT', 'UBER', 'ABNB', 'NKE', 'SBUX', 'LULU',

        // Finance & Industrial
        'JPM', 'GS', 'BA', 'CAT', 'GE',

        // High Beta / Momentum
        'UPST', 'SHOP', 'ROKU', 'SNAP', 'PINS', 'DASH'
    ];

    // Custom Dropdown Logic
    // Populate Ticker Select
    const tickerSelect = document.getElementById('ticker-select');
    if (tickerSelect && WATCHLIST_TICKERS) {
        WATCHLIST_TICKERS.forEach(ticker => {
            const option = document.createElement('option');
            option.value = ticker;
            option.textContent = ticker;
            if (ticker === currentTicker) option.selected = true;
            tickerSelect.appendChild(option);
        });

        tickerSelect.addEventListener('change', (e) => {
            currentTicker = e.target.value;
            localStorage.setItem('pigment_current_ticker', currentTicker);
            createTradingViewWidget(currentTicker);

            // Update Insider Ticker if needed
            // (Assuming insider widget logic is separate or needs update)
        });
    }

    // Helper to clear container
    function clear(element) {
        element.innerHTML = '';
    }

    // Initialize TFI
    updateTFI(50, 'Neutral', null); // Default neutral

    // Render Institutional Edge (Options) - Filtered
    function renderOptions(options) {
        clear(optionsBody);
        const filteredOptions = options.filter(opt => opt.ticker === currentTicker);

        if (filteredOptions.length === 0) {
            optionsBody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:#555;">NO DATA FOR ' + currentTicker + '</td></tr>';
            return;
        }

        filteredOptions.forEach(opt => {
            const tr = document.createElement('tr');
            const volumeClass = opt.volume > 500 ? 'highlight-pink' : '';

            tr.innerHTML = `
    <td>${opt.ticker}</td>
                <td>${opt.side}</td>
                <td class="${volumeClass}">${opt.volume}</td>
                <td>${opt.price}</td>
`;
            optionsBody.appendChild(tr);
        });
    }

    // Render Insider Activity - Filtered
    function renderInsider(insiders) {
        clear(insiderList);
        const filteredInsiders = insiders.filter(ins => ins.ticker === currentTicker);

        if (filteredInsiders.length === 0) {
            insiderList.innerHTML = '<div class="placeholder-item">No recent insider activity for ' + currentTicker + '</div>';
            return;
        }
        filteredInsiders.forEach(ins => {
            const div = document.createElement('div');
            div.className = 'list-item';
            div.innerHTML = `
    <span>${ins.ticker} ${ins.person}</span>
        <span style="color: ${ins.type === 'BUY' ? '#00FFFF' : '#FF00FF'}">${ins.type} ${ins.value}</span>
`;
            insiderList.appendChild(div);
        });
    }

    // Polymarket Data
    // Fetched from API


    // Polymarket Position Tracking (for flash animations)
    let previousPolyPositions = new Map(); // Tracks {slug: position_index}
    let previousPolyProbs = new Map(); // Tracks {slug: probability} for odds flash

    // Render Polymarket Odds
    function renderPolymarket(data) {

        const container = document.getElementById('polymarket-container');
        if (!container) {
            console.error('polymarket-container not found!');
            return;
        }

        container.innerHTML = ''; // Clear previous

        // Track current positions to detect moves
        const currentPositions = new Map();

        data.forEach((market, index) => {
            const item = document.createElement('div');
            item.className = 'polymarket-item';

            // Calculate width for confidence gauge
            const prob1 = market.outcome_1_prob || 0;
            const width1 = prob1; // Direct percentage

            // Determine label - Dynamic from Backend
            let label1 = market.outcome_1_label || 'YES';
            let label2 = market.outcome_2_label || 'NO';

            // Detect multi-choice markets and adjust labels
            const multiChoicePatterns = [
                /^Which company/i,
                /^Who will/i,
                /^What price/i,
                /^Which /i,
                /^Who /i
            ];

            const isMultiChoice = multiChoicePatterns.some(pattern => pattern.test(market.event)) &&
                label2.toLowerCase() === 'no';

            // If multi-choice, replace "No" with "Others"
            if (isMultiChoice) {
                label2 = 'Others';
            }

            // Add multi-choice indicator to event text
            let eventText = market.event;
            if (isMultiChoice) {
                eventText += ' ⋯';
            }

            // Truncate long labels
            if (label1.length > 12) label1 = label1.substring(0, 12) + '..';

            // Delta Badge (Percent Change)
            let deltaBadge = '';
            if (market.delta !== 0) {
                const deltaPercent = Math.abs(market.delta * 100).toFixed(0); // e.g. 15
                const arrow = market.delta > 0 ? '↗' : '↘';
                const colorClass = market.delta > 0 ? 'delta-up' : 'delta-down';
                deltaBadge = `<span class="${colorClass}">${arrow} ${deltaPercent}%</span>`;
            }

            // Resolution Indicator (If >98%)
            let resolvingBadge = '';
            if (market.outcome_1_prob >= 98 || market.outcome_2_prob >= 98) {
                resolvingBadge = `<span class="polymarket-resolving-badge">RESOLVING ⏳</span>`;
            }

            // Calculate width for split bar
            const width2 = 100 - width1;

            // **Position Tracking & Flash Animation**
            const slug = market.slug;
            const previousPosition = previousPolyPositions.get(slug);
            currentPositions.set(slug, index);

            // Detect if market is new or has moved position
            let shouldFlash = false;
            if (previousPosition === undefined) {
                // New market
                shouldFlash = true;
            } else if (previousPosition !== index) {
                // Position changed
                shouldFlash = true;
            }

            // **Probability Change Detection**
            const previousProb = previousPolyProbs.get(slug);
            let probFlashClass = '';
            if (previousProb !== undefined && previousProb !== prob1) {
                // Probability changed - flash the odds
                probFlashClass = prob1 > previousProb ? 'prob-flash-up' : 'prob-flash-down';
            }

            // Apply flash animation class
            if (shouldFlash) {
                item.classList.add('flash-row');
                // Remove animation class after it completes (1 second)
                setTimeout(() => {
                    item.classList.remove('flash-row');
                }, 1000);
            }

            item.innerHTML = `
                <div class="polymarket-header">
                    <a href="https://polymarket.com/event/${market.slug}" target="_blank" class="polymarket-event">${eventText}</a>
                    ${resolvingBadge}
                </div>
                <div class="polymarket-odds-row">
                    <div class="polymarket-odds">
                        <span class="polymarket-odds-text polymarket-odds-yes ${probFlashClass}">${prob1}% ${label1}${deltaBadge}</span>
                    </div>
                    <div class="poly-stats-mini">
                        <span>VOL: ${market.volume}</span>
                        <span class="separator">•</span>
                        <span>LIQ: ${market.liquidity}</span>
                    </div>
                </div>
                <div class="polymarket-bar-row">
                    <div class="polymarket-laser-gauge single-gauge">
                        <div class="polymarket-yes-segment" style="width: ${width1}%"></div>
                        <div class="polymarket-no-segment" style="width: ${width2}%"></div>
                    </div>
                </div>
            `;
            container.appendChild(item);

            // Track probability for next comparison
            previousPolyProbs.set(slug, prob1);
        });

        // Update position tracking for next render
        previousPolyPositions = currentPositions;

    }

    // Polymarket Fetcher
    async function fetchPolymarketData() {
        try {
            // Trigger glitch animation
            if (oddsList) {
                oddsList.classList.add('polymarket-glitch');
                setTimeout(() => oddsList.classList.remove('polymarket-glitch'), 300);
            }

            const response = await fetch(`${API_BASE_URL}/api/polymarket`);
            if (!response.ok) {
                console.error('Polymarket API Error:', response.status);
                updateStatus('status-polymarket', false);
                return;
            }

            const responseData = await response.json();


            const { data, is_mock } = responseData;

            if (!data || data.length === 0) {
                console.warn('Polymarket returned empty data');
                updateStatus('status-polymarket', false);
                return;
            }

            // Show OFFLINE if using mock data
            if (is_mock) {
                console.warn('⚠️ Polymarket using DEMO DATA (API blocked)');
                updateStatus('status-polymarket', false);
                // Add demo indicator to widget
                const polymarketWidget = document.getElementById('polymarket-odds');
                if (polymarketWidget) {
                    let demoIndicator = polymarketWidget.querySelector('.demo-indicator');
                    if (!demoIndicator) {
                        demoIndicator = document.createElement('div');
                        demoIndicator.className = 'demo-indicator';
                        demoIndicator.textContent = '⚠️ DEMO DATA';
                        polymarketWidget.querySelector('.widget-header').appendChild(demoIndicator);
                    }
                }
            } else {
                updateStatus('status-polymarket', true); // Status: LIVE (real data)
                // Remove demo indicator if it exists
                const demoIndicator = document.querySelector('.demo-indicator');
                if (demoIndicator) demoIndicator.remove();
            }

            renderPolymarket(data);

        } catch (error) {
            console.error('Polymarket Fetch Error:', error);
            updateStatus('status-polymarket', false); // Status: DOWN
        }
    }

    // Start Polymarket refresh interval
    fetchPolymarketData(); // Initial render
    setInterval(fetchPolymarketData, 30000); // Refresh every 30 seconds

    // Initialize Chart
    createTradingViewWidget(currentTicker);

    // Render Odds (Legacy - kept for compatibility)
    function renderOdds(odds) {
        // Now handled by fetchPolymarketData
    }

    // Render Alert Stream
    function renderAlerts(alerts) {
        clear(alertsList);
        alerts.forEach(alert => {
            const div = document.createElement('div');

            // Base classes for the alert item
            let classes = ['alert-item'];
            if (alert.isNew) {
                classes.push('new');
            }

            // Mega Whale styling (>$3M) - Assuming 'alert' object has these properties
            if (alert.is_mega_whale) {
                classes.push('mega-whale-alert');
                if (alert.type === 'CALL') {
                    classes.push('mega-whale-bull');
                } else {
                    classes.push('mega-whale-bear');
                }
            }
            // Regular whale styling (>$2M)
            else if (alert.notionalValue > 2000000) { // Assuming 'alert' object has notionalValue
                classes.push('whale-alert');
                if (alert.type === 'CALL') {
                    classes.push('whale-alert-bull');
                } else {
                    classes.push('whale-alert-bear'); // Corrected class name for consistency
                }
            }

            div.className = classes.join(' ');
            div.innerHTML = `
    <span style="color: #00FFFF; font-size: 10px; margin-right: 5px;">[${alert.time}]</span>
        ${alert.message}
`;
            alertsList.appendChild(div);
        });
    }

    // Market Movers Tape Data (20 Items: 10 Gainers + 10 Losers)
    function generateMoversData() {
        const movers = [
            // Top Gainers (Green)
            { symbol: "NVDA", change: 12.4, type: "gain" },
            { symbol: "AMD", change: 8.7, type: "gain" },
            { symbol: "MARA", change: 15.2, type: "gain" },
            { symbol: "COIN", change: 9.8, type: "gain" },
            { symbol: "MSTR", change: 11.3, type: "gain" },
            { symbol: "PARA", change: 7.5, type: "gain" },
            { symbol: "SMCI", change: 14.1, type: "gain" },
            { symbol: "AVGO", change: 6.9, type: "gain" },
            { symbol: "RIOT", change: 10.2, type: "gain" },
            { symbol: "PLTR", change: 8.3, type: "gain" },

            // Top Losers (Red)
            { symbol: "INTC", change: -5.4, type: "loss" },
            { symbol: "TSLA", change: -7.2, type: "loss" },
            { symbol: "AAPL", change: -3.1, type: "loss" },
            { symbol: "GOOG", change: -4.6, type: "loss" },
            { symbol: "AMZN", change: -6.8, type: "loss" },
            { symbol: "META", change: -5.9, type: "loss" },
            { symbol: "NFLX", change: -4.3, type: "loss" },
            { symbol: "UBER", change: -7.5, type: "loss" },
            { symbol: "PYPL", change: -6.1, type: "loss" },
            { symbol: "SQ", change: -5.7, type: "loss" }
        ];
        return movers;
    }

    // === MARKET MOVERS TAPE (Slideshow Logic) ===
    let moversData = generateMoversData(); // Initialize with static data for immediate display
    let showGainers = true;
    let moversInterval = null;

    async function fetchMoversData() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/movers`);
            if (!response.ok) throw new Error('Movers API Failed');
            moversData = await response.json();

            updateMoversTape();
        } catch (err) {
            console.warn('Movers API Error:', err);
            // Fallback to mock data if API fails
            moversData = generateMoversData();
            updateMoversTape();
        }
    }

    function updateMoversTape() {
        const priceTicker = document.getElementById('price-ticker');
        if (!priceTicker) return;

        // Filter data
        const gainers = moversData.filter(m => m.type === 'gain').sort((a, b) => b.change - a.change); // Sort highest to lowest
        const losers = moversData.filter(m => m.type === 'loss').sort((a, b) => a.change - b.change); // Sort lowest to highest (most negative first)

        // Select set to display - LIMIT TO 5 ITEMS MAX
        const currentSet = (showGainers ? gainers : losers).slice(0, 5);
        const label = showGainers ? 'TOP GAINERS' : 'TOP LOSERS';
        const labelClass = showGainers ? 'mover-gain' : 'mover-loss';

        // Build HTML
        const itemsHtml = currentSet.map(m => {
            const colorClass = m.type === 'gain' ? 'mover-gain' : 'mover-loss';
            const arrow = m.type === 'gain' ? '▲' : '▼';
            const changeStr = m.change > 0 ? `+ ${m.change}% ` : `${m.change}% `;
            return `<span class="mover-item ${colorClass}">
            <span class="mover-symbol">${m.symbol}</span>
            <span class="mover-separator">//</span>
            <span class="mover-change">${arrow} ${changeStr}</span>
        </span>`;
        }).join(' ');

        const contentHtml = `
    <div class="ticker-content ticker-fade-in">
        <span class="mover-label ${labelClass}">[ ${label} ]</span>
            ${itemsHtml}
        </div>
    `;

        // Fade Out -> Update -> Fade In
        const oldContent = priceTicker.querySelector('.ticker-content');
        if (oldContent) {
            oldContent.classList.remove('ticker-fade-in');
            oldContent.classList.add('ticker-fade-out');

            setTimeout(() => {
                priceTicker.innerHTML = contentHtml;
            }, 500); // Wait for fade out (0.5s)
        } else {
            priceTicker.innerHTML = contentHtml;
        }

        // Toggle for next update
        showGainers = !showGainers;
    }

    function selectTicker(ticker) {
        if (ticker === currentTicker) return;

        currentTicker = ticker;
        localStorage.setItem('pigment_current_ticker', currentTicker);

        // Update Dropdown
        const tickerSelect = document.getElementById('ticker-select'); // If using native select
        if (tickerSelect) tickerSelect.value = currentTicker;

        const selectedText = document.getElementById('selected-ticker-text'); // Custom dropdown
        if (selectedText) selectedText.textContent = currentTicker;

        // Update Chart
        createTradingViewWidget(currentTicker);

        // Update Active State in Ticker
        const items = document.querySelectorAll('.clickable-ticker');
        items.forEach(item => {
            if (item.textContent.trim() === ticker) {
                item.classList.add('active-ticker');
            } else {
                item.classList.remove('active-ticker');
            }
        });
    }

    // Start Slideshow
    function startMoversSlideshow() {
        updateMoversTape(); // Show initial static data immediately
        fetchMoversData(); // Initial fetch (will update with real data when ready)

        // Update data every 60s
        setInterval(fetchMoversData, 60000);

        // Switch slides every 15s
        setInterval(updateMoversTape, 15000);
    }

    // FRED API & TFI Logic
    const FRED_API_KEY = "YOUR_FRED_API_KEY"; // Placeholder";

    // Consolidated News Fetcher
    async function fetchNews(retryCount = 0) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/news`);
            if (!response.ok) throw new Error('News API Error');

            const result = await response.json();

            // Check if backend is still loading
            if (result.loading && retryCount < 3) {

                setTimeout(() => fetchNews(retryCount + 1), 2000);
                return;
            }

            const newsItems = result.data || result;


            if (!newsItems || newsItems.length === 0) {
                console.warn("📰 News Feed Empty");
                updateStatus('status-news', true);
                renderNews([]);
                return;
            }

            renderNews(newsItems);
            updateStatus('status-news', true);

        } catch (error) {
            console.error('News Fetch Error:', error);
            updateStatus('status-news', false);
        }
    }

    // === MARKET MAP (TREEMAP) LOGIC ===
    let currentSectorView = 'ALL';
    const SECTOR_VIEWS = ['ALL', 'INDICES', 'TECH', 'CONSUMER', 'CRYPTO'];

    let heatmapHasLoaded = false;

    async function fetchHeatmapData(retryCount = 0) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/heatmap`);
            if (!response.ok) throw new Error('Heatmap API Error');

            const result = await response.json();

            // Check if backend is still loading
            if (result.loading && retryCount < 3) {

                setTimeout(() => fetchHeatmapData(retryCount + 1), 2000);
                return;
            }

            const data = result.data || result;
            renderMarketMap(data, heatmapHasLoaded); // Pass isUpdate flag
            heatmapHasLoaded = true; // Subsequent calls are updates
            updateStatus('status-sectors', true);

            const headerTitle = document.querySelector('#market-map .widget-title');
            if (headerTitle) {
                const existingBadge = headerTitle.querySelector('.market-state-badge');
                if (existingBadge) existingBadge.remove();
            }
        } catch (error) {
            console.error('Heatmap Fetch Error:', error);
            updateStatus('status-sectors', false);
            renderHeatmapError();
        }
    }

    function renderHeatmapError() {
        const grid = document.getElementById('heatmap-grid');
        if (!grid) return;

        grid.innerHTML = `
            <div class="heatmap-error">
                <div class="error-icon">⚠️</div>
                <div class="error-text">MARKET DATA OFFLINE</div>
                <div class="error-sub">RETRYING...</div>
            </div>
        `;
    }

    function renderMarketMap(data, isUpdate = false) {
        const grid = document.getElementById('heatmap-grid');
        if (!grid) return;

        grid.innerHTML = ''; // Clear loading/previous

        // Filter Data based on View
        let filteredData = data;
        if (currentSectorView !== 'ALL') {
            filteredData = data.filter(item => item.sector === currentSectorView);
        }

        // Sort by size priority for better packing
        const sizePriority = { 'mega': 4, 'large': 3, 'medium': 2, 'small': 1 };
        filteredData.sort((a, b) => sizePriority[b.size] - sizePriority[a.size]);

        filteredData.forEach((item, index) => {
            const div = document.createElement('div');

            // Color intensity based on magnitude of change
            const absChange = Math.abs(item.change);
            let intensityClass = 'intensity-1'; // Default low
            if (absChange >= 3) intensityClass = 'intensity-4'; // Strong move
            else if (absChange >= 2) intensityClass = 'intensity-3';
            else if (absChange >= 1) intensityClass = 'intensity-2';

            let colorClass = 'neutral';
            if (item.change > 0) colorClass = 'positive';
            if (item.change < 0) colorClass = 'negative';

            // Add size class
            const sizeClass = `size-${item.size || 'small'}`;

            // Flash class for updates
            const flashClass = isUpdate ? 'heatmap-flash' : '';

            div.className = `heatmap-item ${colorClass} ${sizeClass} ${intensityClass} ${flashClass}`;

            // Tooltip with more details
            const priceStr = item.price ? `$${item.price.toFixed(2)}` : '';
            div.title = `${item.symbol}: ${item.change > 0 ? '+' : ''}${item.change}% ${priceStr}`;

            div.innerHTML = `
                <span class="sector-symbol">${item.symbol}</span>
                <span class="sector-change">${item.change > 0 ? '+' : ''}${item.change}%</span>
            `;

            // Stagger flash animation
            if (isUpdate) {
                div.style.animationDelay = `${index * 50}ms`;
            }

            grid.appendChild(div);
        });

        // Update timestamp
        updateHeatmapTimestamp();
    }

    // Update heatmap timestamp
    function updateHeatmapTimestamp() {
        const statusContainer = document.getElementById('status-sectors');
        if (!statusContainer) return;

        // Check if timestamp span exists, if not create it
        let tsSpan = statusContainer.querySelector('.heatmap-ts');
        if (!tsSpan) {
            tsSpan = document.createElement('span');
            tsSpan.className = 'heatmap-ts';
            statusContainer.appendChild(tsSpan);
        }

        const now = new Date();
        const timeStr = now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
        tsSpan.textContent = `${timeStr}`;
    }

    // Sector Scroll Button Logic
    const sectorBtn = document.getElementById('sector-scroll-btn');
    const sectorBtnText = document.getElementById('sector-scroll-text');

    if (sectorBtn) {
        sectorBtn.addEventListener('click', () => {
            // Cycle to next view
            const currentIndex = SECTOR_VIEWS.indexOf(currentSectorView);
            const nextIndex = (currentIndex + 1) % SECTOR_VIEWS.length;
            currentSectorView = SECTOR_VIEWS[nextIndex];

            // Update Button Text
            if (sectorBtnText) {
                sectorBtnText.textContent = `VIEW: ${currentSectorView}`;
            }

            // Re-render (trigger fetch to get data again - in real app we'd cache data)
            fetchHeatmapData();
        });
    }

    // fetchVIX removed (replaced by CNN Fear & Greed)

    function updateTFI(value, rating, source) {

        // DOM Elements
        const tfiSegmentsContainer = document.getElementById('tfi-segments');
        const tfiContainer = document.querySelector('.tfi-container');

        if (!tfiSegmentsContainer) {
            console.error('TFI elements not found!');
            return;
        }

        // Update score and rating
        const tfiScore = document.getElementById('tfi-score');
        const tfiRating = document.getElementById('tfi-rating');
        const tfiVixRef = document.getElementById('tfi-vix-ref');

        if (tfiScore && tfiRating) {
            tfiScore.textContent = Math.round(value);
            tfiRating.textContent = rating.toUpperCase();
            tfiRating.style.color = ""; // Reset color
        }

        // Update source reference (was VIX, now shows Crypto F&G)
        if (tfiVixRef && source) {
            tfiVixRef.textContent = `₿ ${source}`;
        }

        // Clear previous classes
        tfiContainer.classList.remove('tfi-green', 'tfi-yellow', 'tfi-red', 'tfi-extreme-fear', 'tfi-extreme-greed');

        // Determine Color Theme & Dynamic Effects
        // < 25: Extreme Fear (Blood Pulse)
        // 25 - 45: Fear (Red)
        // 45 - 55: Neutral (Yellow)
        // 55 - 75: Greed (Green)
        // > 75: Extreme Greed (Money Surge)

        if (value < 25) {
            tfiContainer.classList.add('tfi-extreme-fear');

        } else if (value < 45) {
            tfiContainer.classList.add('tfi-red');

        } else if (value > 75) {
            tfiContainer.classList.add('tfi-extreme-greed');

        } else if (value > 55) {
            tfiContainer.classList.add('tfi-green');

        } else {
            tfiContainer.classList.add('tfi-yellow');

        }

        // Clear segments
        tfiSegmentsContainer.innerHTML = '';

        // Calculate active segments (0 to 10)
        const totalSegments = 10;
        const activeCount = Math.round(value / 10);

        // Generate Segments
        for (let i = 0; i < totalSegments; i++) {
            const seg = document.createElement('div');
            seg.className = 'tfi-seg';
            if (i < activeCount) {
                seg.classList.add('active');
            }
            tfiSegmentsContainer.appendChild(seg);
        }

    }

    // Initialize TFI
    async function fetchCNNFearGreed() {
        try {

            const response = await fetch(`${API_BASE_URL}/api/cnn-fear-greed`);
            if (!response.ok) throw new Error('CNN Fear & Greed API Failed');

            const data = await response.json();

            updateTFI(data.value, data.rating, data.source);

            updateStatus('status-tfi', true);
        } catch (error) {
            console.error('CNN Fear & Greed API Failed:', error);
            updateStatus('status-tfi', false);
        }
    }
    fetchCNNFearGreed();
    setInterval(fetchCNNFearGreed, 300000); // Refresh every 5 minutes (was 12 hours)

    // Initialize Market Map
    fetchHeatmapData();
    setInterval(fetchHeatmapData, 300000); // Refresh every 5 minutes

    // Helper: Update API Status Indicator
    function updateStatus(elementId, isLive) {
        const container = document.getElementById(elementId);
        if (container) {
            const textSpan = container.querySelector('.status-text');
            if (isLive) {
                container.classList.add('status-live');
                if (textSpan) textSpan.textContent = "LIVE";
            } else {
                container.classList.remove('status-live');
                if (textSpan) textSpan.textContent = "OFFLINE";
            }
        }
    }

    // UW Flow Feed Logic (High Value)
    const flowFeedContainer = document.getElementById('flow-feed-container');
    let isFlowPaused = false;

    // Pause on Hover
    if (flowFeedContainer) {
        flowFeedContainer.addEventListener('mouseenter', () => { isFlowPaused = true; });
        flowFeedContainer.addEventListener('mouseleave', () => { isFlowPaused = false; });
    }

    // Intel Feed Auto-Scroll Logic - Moved to startNewsTicker for sync
    // const newsFeedContainer = document.getElementById('news-feed-container');
    // ... logic moved ...

    // Real Whale Data Fetcher (Barchart Backend) - STRICT REAL DATA ONLY
    // Real Whale Data Fetcher (Barchart Backend) - STRICT REAL DATA ONLY
    async function fetchRealWhaleData() {
        try {
            // Call our Python API backend
            const response = await fetch(`${API_BASE_URL}/api/whales`);
            if (!response.ok) throw new Error('API request failed');

            const json = await response.json();

            // Check if we got valid data
            if (!json.data || json.data.length === 0) {
                console.warn("Scraper returned no data");
                updateStatus('status-whales', false); // Status: DOWN
                return [];
            }

            updateStatus('status-whales', true); // Status: LIVE


            const trades = json.data.map(item => ({
                ticker: item.baseSymbol || item.symbol,
                strike: item.strikePrice,
                type: item.putCall === 'C' ? 'CALL' : 'PUT',
                expiry: item.expirationDate, // Format: YYYY-MM-DD
                premium: item.premium || "DELAYED",
                volume: item.volume,
                direction: item.putCall === 'C' ? 'BULL' : 'BEAR',
                isWhale: true, // Assume notable if on this list
                isCritical: false, // Cannot determine without premium
                // New Fields
                vol_oi: item.vol_oi,
                moneyness: item.moneyness,
                is_mega_whale: item.is_mega_whale || false,
                notional_value: item.notional_value || 0
            }));


            return trades;
        } catch (err) {
            console.warn("Whale API Failed:", err);
            updateStatus('status-whales', false); // Status: DOWN
            return []; // Return empty array on error
        }
    }

    // REMOVED: generateMockWhaleData() - Strict Real Data Policy

    // Check if US market is open (9:30 AM - 4:00 PM ET, Mon-Fri)
    function updateClock() {
        const now = new Date();
        const timeString = now.toLocaleTimeString('en-US', { hour12: false });
        const dateString = now.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });

        document.getElementById('clock').textContent = timeString;
        document.getElementById('date').textContent = dateString.toUpperCase();

        updateMarketSessions(now);
    }

    // === GLOBAL MARKET SESSIONS LOGIC ===
    // === GLOBAL MARKET SESSIONS LOGIC ===
    function updateMarketSessions(now) {
        // Market Hours in UTC (approximate)
        // NY: 14:30 - 21:00 UTC
        // LON: 08:00 - 16:30 UTC
        // TOK: 00:00 - 06:00 UTC
        // SYD: 23:00 - 05:00 UTC

        const utcHour = now.getUTCHours();
        const utcMin = now.getUTCMinutes();
        const currentTime = utcHour + (utcMin / 60);

        const markets = [
            { id: 'session-ny', start: 14.5, end: 21.0 },
            { id: 'session-lon', start: 8.0, end: 16.5 },
            { id: 'session-tok', start: 0.0, end: 6.0 },
            { id: 'session-syd', start: 23.0, end: 5.0 }
        ];

        const PREMARKET_DURATION = 1.5; // 90 minutes

        markets.forEach(m => {
            const el = document.getElementById(m.id);
            if (!el) return;

            let status = 'closed'; // closed, premarket, open
            let progress = 0;

            // Helper to normalize time to 0-24
            const norm = (t) => (t + 24) % 24;

            // Calculate Start/End/PreStart handling midnight wrap
            // We'll check if current time is within [start, end] for OPEN
            // Or within [start - 1.5, start] for PREMARKET

            // Check OPEN
            let isOpen = false;
            if (m.start < m.end) {
                isOpen = currentTime >= m.start && currentTime < m.end;
            } else {
                // Wraps midnight (e.g. 23 to 5)
                isOpen = currentTime >= m.start || currentTime < m.end;
            }

            if (isOpen) {
                status = 'open';
                // Calculate Progress (0-100%)
                let duration = m.start < m.end ? (m.end - m.start) : (24 - m.start + m.end);
                let elapsed = currentTime >= m.start ? (currentTime - m.start) : (24 - m.start + currentTime);
                progress = (elapsed / duration) * 100;
            } else {
                // Check PREMARKET
                // Pre-start is start - 1.5h
                // We need to handle wrapping manually for comparison
                let preStart = norm(m.start - PREMARKET_DURATION);
                let isPre = false;

                if (preStart < m.start) {
                    // Normal case (e.g. 8.0 -> 6.5 to 8.0)
                    isPre = currentTime >= preStart && currentTime < m.start;
                } else {
                    // Wraps midnight (e.g. 0.0 -> 22.5 to 0.0)
                    isPre = currentTime >= preStart || currentTime < m.start;
                }

                if (isPre) {
                    status = 'premarket';
                    // Calculate Progress (0-100% of premarket phase)
                    let elapsed = currentTime >= preStart ? (currentTime - preStart) : (24 - preStart + currentTime);
                    progress = (elapsed / PREMARKET_DURATION) * 100;
                }
            }

            // Update UI
            const bar = el.querySelector('.session-bar');

            // Reset Classes
            el.classList.remove('open', 'premarket');

            if (status === 'open') {
                el.classList.add('open');
                bar.style.width = `${progress}%`;
            } else if (status === 'premarket') {
                el.classList.add('premarket');
                bar.style.width = `${progress}%`;
            } else {
                bar.style.width = '0%';
            }
        });
    }

    setInterval(updateClock, 1000);
    updateClock();

    function isMarketOpen() {
        const now = new Date();
        const et = new Date(now.toLocaleString("en-US", { timeZone: "America/New_York" }));
        const day = et.getDay(); // 0=Sun, 6=Sat
        const hour = et.getHours();
        const minute = et.getMinutes();

        // Weekend
        if (day === 0 || day === 6) return false;

        // Weekday: Before 9:30 AM or after 4:00 PM
        if (hour < 9 || hour >= 16) return false;
        if (hour === 9 && minute < 30) return false;

        return true;
    }

    // Track seen items in memory
    let seenTrades = new Set();
    let previousSnapshotTradeIds = new Set();
    let tradeFirstSeen = new Map();
    // let seenItems = new Set(); // Deprecated
    const MAX_FEED_AGE_MS = 20 * 60 * 1000; // 20 minutes

    // SSE Stream Setup
    function initWhaleStream() {
        const evtSource = new EventSource(`${API_BASE_URL}/api/whales/stream`);

        evtSource.onmessage = function (event) {
            const response = JSON.parse(event.data);
            handleWhaleData(response);
        };

        evtSource.onerror = function (err) {
            console.warn("🐳 SSE Stream Error:", err);
            updateStatus('status-whales', false);
            // Retry connection after 5s if closed
            if (evtSource.readyState === EventSource.CLOSED) {
                setTimeout(initWhaleStream, 5000);
            }
        };
    }

    // === MARKET STATE DETECTION (ET Timezone) ===
    let marketOpenTimeout = null;

    function getMarketState() {
        // Get current time in ET using robust Intl API
        const now = new Date();

        const options = {
            timeZone: "America/New_York",
            hour12: false,
            year: 'numeric',
            month: 'numeric',
            day: 'numeric',
            hour: 'numeric',
            minute: 'numeric',
            second: 'numeric'
        };

        const formatter = new Intl.DateTimeFormat("en-US", options);
        const parts = formatter.formatToParts(now);

        const getPart = (type) => {
            const part = parts.find(p => p.type === type);
            return part ? parseInt(part.value) : 0;
        };

        const year = getPart('year');
        const month = getPart('month') - 1; // 0-indexed for Date
        const dayOfMonth = getPart('day');
        const hours = getPart('hour');
        const minutes = getPart('minute');
        const seconds = getPart('second');

        // Create Date object representing ET time
        const etTime = new Date(year, month, dayOfMonth, hours, minutes, seconds);
        const day = etTime.getDay(); // 0=Sun, 6=Sat

        const currentMinutes = hours * 60 + minutes;

        const marketOpenMinutes = 9 * 60 + 30; // 9:30 AM
        const marketCloseMinutes = 16 * 60; // 4:00 PM

        const isWeekend = day === 0 || day === 6;

        return {
            isWeekend,
            isPreMarket: currentMinutes < marketOpenMinutes,
            isMarketHours: !isWeekend && currentMinutes >= marketOpenMinutes && currentMinutes < marketCloseMinutes,
            isAfterHours: currentMinutes >= marketCloseMinutes,
            currentET: etTime,
            hours,
            minutes,
            seconds
        };
    }

    function calculateMsUntilMarketOpen() {
        const state = getMarketState();

        if (!state.isPreMarket) {
            return 0; // Already open or after hours
        }

        // Calculate exact ms until 9:30:00 AM ET today
        const now = state.currentET;
        const marketOpen = new Date(now);
        marketOpen.setHours(9, 30, 0, 0); // 9:30:00.000 AM

        const msUntilOpen = marketOpen - now;
        return Math.max(0, msUntilOpen);
    }

    function scheduleMarketOpenTransition() {
        // Clear any existing timeout
        if (marketOpenTimeout) {
            clearTimeout(marketOpenTimeout);
            marketOpenTimeout = null;
        }

        const msUntilOpen = calculateMsUntilMarketOpen();

        if (msUntilOpen > 0) {


            // Set precise timeout for market open
            marketOpenTimeout = setTimeout(() => {

                // Force a refresh to fetch new trades
                if (window.initWhaleStream) {
                    window.initWhaleStream();
                }
            }, msUntilOpen);
        }
    }

    // Schedule market open transition on page load
    scheduleMarketOpenTransition();

    function handleWhaleData(response) {
        const { data, stale } = response;

        // Determine system health
        const isSystemHealthy = !stale;
        const hasData = data && data.length > 0;

        // Get market state early
        const marketState = getMarketState();

        // PRE-MARKET / WEEKEND: Clear all caches and show radar
        if (marketState.isPreMarket || marketState.isWeekend) {
            // Clear all tracking caches
            seenTrades.clear();
            tradeFirstSeen.clear();
            previousSnapshotTradeIds.clear();

            const flowFeedContainer = document.getElementById('flow-feed-container');
            if (flowFeedContainer) {
                const statusText = marketState.isWeekend ? "WEEKEND" : "PRE-MARKET";
                flowFeedContainer.innerHTML = `
                    <div class="whale-pre-market-container">
                        <div class="radar-container">
                            <div class="radar-ring radar-ring-1"></div>
                            <div class="radar-ring radar-ring-2"></div>
                            <div class="radar-ring radar-ring-3"></div>
                            <div class="radar-center"></div>
                        </div>
                        <div class="status-message">
                            <span style="color: #888; font-size: 11px; font-family: var(--font-mono);">STATUS: ${statusText}. Monitoring for block orders...</span>
                        </div>
                    </div>
                `;
            }
            updateStatus('status-whales', isSystemHealthy);
            return; // Exit early - don't process any data during pre-market
        }

        // Update Status: Only show OFFLINE if system is actually down (stale)
        updateStatus('status-whales', isSystemHealthy);

        // Show/Hide Stale Banner (only if system is down)
        const banner = document.getElementById('whale-stale-banner');
        if (banner) {
            if (stale) {
                banner.textContent = "⚠️ Live feed disconnected - System OFFLINE";
                banner.classList.remove('hidden');
            } else {
                banner.classList.add('hidden');
            }
        }

        const flowFeedContainer = document.getElementById('flow-feed-container');
        if (!flowFeedContainer) return;

        // Handle empty data (only reached during market hours / after hours)
        if (!hasData) {

            // Clear existing items
            flowFeedContainer.innerHTML = '';

            if (isSystemHealthy) {
                // MARKET HOURS or AFTER HOURS: Show waiting message
                const waitingDiv = document.createElement('div');
                waitingDiv.className = 'placeholder-item';
                waitingDiv.textContent = 'Waiting for trade...';
                flowFeedContainer.appendChild(waitingDiv);
            }
            return;
        }

        // Map to internal format
        const nowTs = Date.now() / 1000; // Current time for "entered feed" timestamp
        const trades = data.map(item => {
            // Generate trade ID to check if we've seen it before
            const ticker = item.baseSymbol || item.symbol;
            const strike = item.strikePrice;
            const type = item.putCall === 'C' ? 'CALL' : 'PUT';
            const expiry = item.expirationDate;
            const volume = item.volume;
            const tradeId = `${ticker}_${strike}_${type}_${expiry}_${volume} `;

            // Use existing enteredAt if we've seen this trade, otherwise use now
            let enteredAtTime = nowTs;
            if (tradeFirstSeen.has(tradeId)) {
                enteredAtTime = tradeFirstSeen.get(tradeId) / 1000; // Convert ms to seconds
            } else {
                tradeFirstSeen.set(tradeId, Date.now()); // Store in ms for consistency
            }

            return {
                ticker,
                strike,
                type,
                expiry,
                premium: item.premium || "DELAYED",
                volume,
                direction: item.putCall === 'C' ? 'BULL' : 'BEAR',
                isWhale: true,
                isCritical: false,
                vol_oi: item.vol_oi,
                moneyness: item.moneyness,
                is_mega_whale: item.is_mega_whale || false,
                notional_value: item.notional_value || 0,
                timestamp: item.timestamp || 0,
                enteredAt: enteredAtTime, // Preserve original entry time
                delta: item.delta,
                iv: item.iv
            };
        });

        // Hover Pause Logic
        if (isFeedHovered) {
            // Queue them up
            pendingWhales = [...trades, ...pendingWhales];
            // Limit buffer
            if (pendingWhales.length > 50) pendingWhales = pendingWhales.slice(0, 50);
        } else {
            // Render immediately
            renderWhaleFeed(trades);
        }
    }

    // === Hover Pause Logic ===
    let isFeedHovered = false;
    let pendingWhales = [];

    const feedContainer = document.getElementById('flow-feed-container');
    if (feedContainer) {
        feedContainer.addEventListener('mouseenter', () => {
            isFeedHovered = true;
        });

        feedContainer.addEventListener('mouseleave', () => {
            isFeedHovered = false;
            // Process pending
            if (pendingWhales.length > 0) {
                renderWhaleFeed(pendingWhales);
                pendingWhales = [];
            }
        });
    }

    function renderWhaleFeed(trades) {
        const flowFeedContainer = document.getElementById('flow-feed-container');
        if (!flowFeedContainer) return;

        // Clear "waiting" message
        const waitingMsg = flowFeedContainer.querySelector('.no-data-message');
        if (waitingMsg) waitingMsg.remove();
        const placeholder = flowFeedContainer.querySelector('.placeholder-item');
        if (placeholder) placeholder.remove();

        const currentSnapshotTradeIds = new Set();
        const tradesToRender = []; // Collect trades to render after processing

        [...trades].reverse().forEach(flow => {
            // Unique ID using MAPPED properties
            const id = `${flow.ticker}_${flow.strike}_${flow.type}_${flow.expiry}_${flow.volume} `;
            currentSnapshotTradeIds.add(id); // Add to current snapshot for next comparison

            // Deduplicate against all seen trades in this session
            if (seenTrades.has(id)) {
                return;
            }
            seenTrades.add(id);

            // Determine if this trade is "NEW" based on the previous snapshot
            const isNew = !previousSnapshotTradeIds.has(id);

            tradesToRender.push({ flow, id, isNew });
        });

        // Update previous snapshot for the next incoming data
        previousSnapshotTradeIds = currentSnapshotTradeIds;

        // Now render the collected trades
        tradesToRender.forEach(({ flow, id, isNew }) => {
            const div = createFlowElement(flow, id, isNew);
            // div.setAttribute('data-id', id); // Track ID for badge cleanup
            div.dataset.tradeId = id;

            // Prepend new items (Slide In Animation handled by CSS)
            flowFeedContainer.insertBefore(div, flowFeedContainer.firstChild);

            // Limit to 50 items to prevent DOM bloat
            if (flowFeedContainer.children.length > 50) {
                flowFeedContainer.lastChild.remove();
            }
        });

        // Optional: Prune seenTrades set to keep memory low (if needed)
        // Removed aggressive clearing to prevent "flash" of re-rendering
        if (seenTrades.size > 50000) {
            seenTrades.clear();
        }
    }

    // === GAMMA WALL LOGIC ===
    // Define globally so renderGammaChart can access it
    let gammaChartBars = document.getElementById('gamma-chart-bars');
    let currentGammaTicker = 'SPY';

    // Initialize Gamma Wall
    function initGammaWall() {
        const gammaSelector = document.getElementById('gamma-ticker-select');
        if (gammaSelector) {
            gammaSelector.value = currentGammaTicker;
            gammaSelector.addEventListener('change', (e) => {
                currentGammaTicker = e.target.value;
                fetchGammaWall(currentGammaTicker);
            });
        }

        // Initial Fetch
        fetchGammaWall(currentGammaTicker);

        // Refresh every 5 minutes
        setInterval(() => fetchGammaWall(currentGammaTicker), 300000);
    }

    async function fetchGammaWall(ticker = 'SPY') {
        // Check localStorage cache first (TTL 2 minutes)
        try {
            // Only show loader on INITIAL load (no existing rows)
            const hasExistingData = gammaChartBars && gammaChartBars.querySelector('.gamma-row');
            if (gammaChartBars && !hasExistingData) {
                gammaChartBars.innerHTML = `
                <div class="intel-loader">
                    <div class="intel-row">> TARGET: ${ticker}</div>
                    <div class="intel-row">> STATUS: ACQUIRING DATA<span class="blink-cursor">█</span></div>
                </div>
            `;
            }

            const cached = getGammaCache(ticker);
            if (cached) {
                renderGammaChart(cached);
                updateStatus('status-gamma-wall', true); // Show LIVE even from cache
                return;
            }

            const res = await fetch(`/api/gamma?symbol=${ticker}`);
            const data = await res.json();

            if (data.error) {
                console.error("Gamma Error:", data.error);
                if (gammaChartBars) {
                    gammaChartBars.innerHTML = `
                    <div class="intel-loader" style="color: #FF3333;">
                        <div class="intel-row">> TARGET: ${ticker}</div>
                        <div class="intel-row">> STATUS: CONNECTION FAILED</div>
                        <div class="intel-row">> ERROR: ${data.error}</div>
                    </div>
                `;
                }
                return;
            }

            // Cache Success
            setGammaCache(ticker, data);

            renderGammaChart(data);
            updateStatus('status-gamma-wall', true); // Show LIVE status
        } catch (e) {
            console.error("Gamma Fetch Failed:", e);
            if (gammaChartBars) {
                gammaChartBars.innerHTML = `
                <div class="intel-loader" style="color: #FF3333;">
                    <div class="intel-row">> TARGET: ${ticker}</div>
                    <div class="intel-row">> STATUS: SYSTEM FAILURE</div>
                </div>
            `;
            }
        }
    }

    function renderGammaChart(data) {
        if (!gammaChartBars) {
            gammaChartBars = document.getElementById('gamma-chart-bars');
        }
        if (!gammaChartBars) return;

        // Clear loading message ONLY (don't clear existing rows)
        const loader = gammaChartBars.querySelector('.intel-loader');
        if (loader) loader.remove();

        // Create Tooltip
        let tooltip = document.getElementById('gamma-tooltip');
        if (!tooltip) {
            tooltip = document.createElement('div');
            tooltip.id = 'gamma-tooltip';
            tooltip.className = 'gamma-tooltip';
            tooltip.style.opacity = '0';
            document.body.appendChild(tooltip);
        }

        // Spot Price Line Removed per user request

        // Update Header
        const title = document.querySelector('.gamma-title');
        if (title) {
            let html = `GAMMA WALL`;
            if (data.is_weekend_data) {
                html += ` <span class="weekend-badge">FRI DATA</span>`;
            }
            title.innerHTML = html;
        }

        let maxVol = 0;
        let totalCallVol = 0;
        let totalPutVol = 0;
        data.strikes.forEach(s => {
            if (s.call_vol > maxVol) maxVol = s.call_vol;
            if (s.put_vol > maxVol) maxVol = s.put_vol;
            totalCallVol += s.call_vol || 0;
            totalPutVol += s.put_vol || 0;
        });
        if (maxVol === 0) maxVol = 1;

        // Helper: Format volume (42000 → "42K")
        const formatVol = (vol) => {
            if (vol >= 1000) return (vol / 1000).toFixed(1).replace('.0', '') + 'K';
            return vol.toString();
        };

        // === DOMINANCE BADGE ===
        const totalVolumeAll = totalCallVol + totalPutVol;
        let dominanceBadgeHtml = '';
        if (totalVolumeAll > 0) {
            const callPct = (totalCallVol / totalVolumeAll) * 100;
            const putPct = (totalPutVol / totalVolumeAll) * 100;
            const diff = Math.abs(callPct - putPct);

            if (diff >= 10) {
                if (callPct > putPct) {
                    dominanceBadgeHtml = `<span class="dominance-badge bullish">📈 CALLS +${Math.round(diff)}%</span>`;
                } else {
                    dominanceBadgeHtml = `<span class="dominance-badge bearish">📉 PUTS +${Math.round(diff)}%</span>`;
                }
            } else {
                dominanceBadgeHtml = `<span class="dominance-badge neutral">⚖️ BALANCED</span>`;
            }
        }

        // Update Header with dominance badge
        const gammaHeader = document.querySelector('#gamma-wall .widget-header h2');
        if (gammaHeader) {
            let html = `GAMMA WALL`;
            if (data.is_weekend_data) {
                html += ` <span class="weekend-badge">FRI DATA</span>`;
            }
            html += dominanceBadgeHtml;
            gammaHeader.innerHTML = html;
        }


        const existingRows = new Map();
        Array.from(gammaChartBars.children).forEach(row => {
            const strike = parseFloat(row.dataset.strike);
            if (!isNaN(strike)) existingRows.set(strike, row);
        });

        // Sort High -> Low
        data.strikes.sort((a, b) => b.strike - a.strike);

        // Find ATM Strike for Blue Highlight
        let closestStrike = null;
        let minDiff = Infinity;
        data.strikes.forEach(s => {
            const diff = Math.abs(s.strike - data.current_price);
            if (diff < minDiff) {
                minDiff = diff;
                closestStrike = s.strike;
            }
        });

        // Store current price for tooltip calculations
        window.lastGammaPrice = data.current_price;

        // === FIND THE SINGLE MOST UNUSUAL WALL ===
        // Find the strike with the highest total volume relative to average
        let totalVol = 0;
        data.strikes.forEach(s => {
            totalVol += (s.call_vol || 0) + (s.put_vol || 0);
        });
        const avgVol = data.strikes.length > 0 ? totalVol / data.strikes.length : 0;

        let mostUnusualStrike = null;
        let highestVolRatio = 0;

        data.strikes.forEach(s => {
            const strikeTotal = (s.call_vol || 0) + (s.put_vol || 0);
            const ratio = avgVol > 0 ? strikeTotal / avgVol : 0;
            // Must be at least 2x average to qualify
            if (ratio >= 2.0 && ratio > highestVolRatio) {
                highestVolRatio = ratio;
                mostUnusualStrike = s.strike;
            }
        });

        data.strikes.forEach(strikeData => {
            let row = existingRows.get(strikeData.strike);
            const putWidth = (strikeData.put_vol / maxVol) * 100;
            const callWidth = (strikeData.call_vol / maxVol) * 100;

            // Is this the "Zero Gamma" (ATM) row?
            const isZeroGamma = strikeData.strike === closestStrike;

            // Is this THE most unusual wall?
            const isMostUnusual = strikeData.strike === mostUnusualStrike;

            if (row) {
                // Update
                const putBar = row.querySelector('.gamma-bar-put');
                const callBar = row.querySelector('.gamma-bar-call');

                if (putBar) putBar.style.width = `${putWidth}%`;
                if (callBar) callBar.style.width = `${callWidth}%`;

                // Apply Blue Style
                if (isZeroGamma) {
                    row.classList.add('zero-gamma-row');
                    // Add label if not exists
                    if (!row.querySelector('.zero-gamma-label')) {
                        const label = document.createElement('div');
                        label.className = 'zero-gamma-label';
                        label.textContent = "FLIP";
                        row.appendChild(label);
                    }
                } else {
                    row.classList.remove('zero-gamma-row');
                    const label = row.querySelector('.zero-gamma-label');
                    if (label) label.remove();
                }

                // === Apply Most Unusual Wall Styling ===
                if (isMostUnusual) {
                    row.classList.add('most-unusual-wall');
                } else {
                    row.classList.remove('most-unusual-wall');
                }

                existingRows.delete(strikeData.strike);
            } else {
                // Create New
                row = document.createElement('div');
                row.className = 'gamma-row';
                row.dataset.strike = strikeData.strike;
                if (isZeroGamma) {
                    row.classList.add('zero-gamma-row');
                    const label = document.createElement('div');
                    label.className = 'zero-gamma-label';
                    label.textContent = "FLIP";
                    row.appendChild(label);
                }

                // === Apply Most Unusual Wall Styling (New Rows) ===
                if (isMostUnusual) {
                    row.classList.add('most-unusual-wall');
                }

                // Format volume labels (only show if bar is significant - at least 5% width)
                const putVolLabel = putWidth >= 5 ? `<span class="gamma-vol-label put-label">${formatVol(strikeData.put_vol)}</span>` : '';
                const callVolLabel = callWidth >= 5 ? `<span class="gamma-vol-label call-label">${formatVol(strikeData.call_vol)}</span>` : '';

                row.innerHTML = `
                    <div class="gamma-put-side">
                        ${putVolLabel}
                        <div class="gamma-bar-put" style="width: ${putWidth}%"></div>
                    </div>
                    <div class="gamma-strike">${strikeData.strike.toFixed(1)}</div>
                    <div class="gamma-call-side">
                        <div class="gamma-bar-call" style="width: ${callWidth}%"></div>
                        ${callVolLabel}
                    </div>
                `;

                // Re-attach event listeners (simplified)
                const putBar = row.querySelector('.gamma-bar-put');
                const callBar = row.querySelector('.gamma-bar-call');
                putBar.onmouseenter = (e) => showTooltip(e, strikeData, 'PUT', tooltip);
                putBar.onmousemove = (e) => moveTooltip(e, tooltip);
                putBar.onmouseleave = () => hideTooltip(tooltip);
                callBar.onmouseenter = (e) => showTooltip(e, strikeData, 'CALL', tooltip);
                callBar.onmousemove = (e) => moveTooltip(e, tooltip);
                callBar.onmouseleave = () => hideTooltip(tooltip);

                gammaChartBars.appendChild(row);
            }
        });

        existingRows.forEach((row) => row.remove());

        // Auto-scroll on first load
        if (!gammaChartBars.dataset.scrolled) {
            setTimeout(() => {
                const currentRow = document.querySelector('.zero-gamma-row');
                if (currentRow) {
                    currentRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    gammaChartBars.dataset.scrolled = "true";
                }
            }, 500);
        }
    }

    function showTooltip(e, data, type, tooltip) {
        const vol = type === 'CALL' ? data.call_vol : data.put_vol;
        const oi = type === 'CALL' ? data.call_oi : data.put_oi;
        const color = type === 'CALL' ? 'var(--bullish-color)' : 'var(--bearish-color)';

        // Estimate notional value: volume × 100 shares × ~$3 avg premium (conservative)
        // This is a rough estimate since we don't have actual premium data
        const avgPremium = Math.abs(data.strike - (window.lastGammaPrice || data.strike)) * 0.3 + 2;
        const notional = vol * 100 * avgPremium;

        // Format as currency
        const formatMoney = (val) => {
            if (val >= 1000000) return '$' + (val / 1000000).toFixed(1) + 'M';
            if (val >= 1000) return '$' + (val / 1000).toFixed(0) + 'K';
            return '$' + val.toFixed(0);
        };

        tooltip.className = `gamma-tooltip ${type === 'CALL' ? 'call-tooltip' : 'put-tooltip'}`;
        tooltip.innerHTML = `
            <div class="tooltip-header" style="color: ${color}">
                <span>${type}</span>
                <span>$${data.strike}</span>
            </div>
            <div class="tooltip-row">
                <span class="tooltip-label">💸 EST. FLOW:</span>
                <span class="tooltip-value">${formatMoney(notional)}</span>
            </div>
            <div class="tooltip-row">
                <span class="tooltip-label">OPEN INT:</span>
                <span class="tooltip-value">${oi ? oi.toLocaleString() : 'N/A'}</span>
            </div>
        `;

        tooltip.style.opacity = '1';
        moveTooltip(e, tooltip);
    }

    function moveTooltip(e, tooltip) {
        const x = e.clientX + 15;
        const y = e.clientY + 15;
        tooltip.style.left = `${x}px`;
        tooltip.style.top = `${y}px`;
    }

    function hideTooltip(tooltip) {
        tooltip.style.opacity = '0';
    }

    // Helper: Create flow element (New Grid Layout)
    function createFlowElement(flow, tradeId, isNew) {
        const row = document.createElement('div');
        row.className = 'whale-row';

        // Only add animation class if it's actually new
        if (isNew) {
            row.classList.add('new-row');
        }

        // Add MEGA pulse animation ONLY for >$40M elite trades
        if (flow.notional_value && flow.notional_value >= 40000000) {
            row.classList.add('mega-row');
        }

        // Add direction class for hover glow
        const isCall = flow.type === 'CALL';
        row.classList.add(isCall ? 'call-row' : 'put-row');

        // 1. Ticker Column
        const colTicker = document.createElement('div');
        colTicker.className = 'col-ticker';

        const tickerSpan = document.createElement('span');
        tickerSpan.textContent = flow.ticker;
        colTicker.appendChild(tickerSpan);

        // Time-ago badge - only show "now" for first 3 seconds, then fade out
        const feedTimestamp = flow.enteredAt || flow.timestamp;
        if (feedTimestamp) {
            const secsAgo = Math.floor(Date.now() / 1000 - feedTimestamp);

            // Only show "now" badge for trades that just entered (within 3 seconds)
            if (secsAgo < 3) {
                const timeAgoSpan = document.createElement('span');
                timeAgoSpan.className = 'time-ago time-ago-now';
                timeAgoSpan.textContent = 'now';
                colTicker.appendChild(timeAgoSpan);

                // Fade out after 3 seconds
                const fadeDelay = Math.max(0, 3 - secsAgo) * 1000;
                setTimeout(() => {
                    timeAgoSpan.classList.add('fade-out');
                    setTimeout(() => timeAgoSpan.remove(), 500);
                }, fadeDelay);
            }
            // No badge shown for older trades (cleaner look)
        }

        // Common Variables for Type (isCall already declared above)
        const typeClass = isCall ? 'type-c' : 'type-p';
        const typeLabel = isCall ? 'C' : 'P';

        // 2. Premium Column
        const colPremium = document.createElement('div');
        colPremium.className = 'col-premium';
        colPremium.classList.add(typeClass);
        colPremium.textContent = flow.premium;

        // 3. Strike/Type Column
        const colStrike = document.createElement('div');
        colStrike.className = 'col-strike';

        // Format Date (e.g. "2025-12-12" -> "12/12")
        const dateStr = flow.expiry ? flow.expiry.slice(5) : '';

        colStrike.innerHTML = `
        <span class="${typeClass}">${flow.strike}${typeLabel}</span>
        <span class="expiry-date">${dateStr}</span>
    `;

        // 4. Tag Column (MEGA / FRESH / BULL / BEAR / HEDGE / ITM / OTM)
        const colTag = document.createElement('div');
        colTag.className = 'col-tag';

        // Hedge Logic: Index Puts are likely hedges
        const isIndex = ['SPY', 'QQQ', 'IWM', 'DIA', 'VIX'].includes(flow.ticker);
        const isHedge = isIndex && !isCall; // Index Put = Hedge

        // Priority 1: MEGA
        if (flow.is_mega_whale) {
            colTag.textContent = 'MEGA';
            colTag.classList.add('tag-mega');
        }
        // Priority 2: HEDGE (Index Puts)
        else if (isHedge) {
            colTag.textContent = 'HEDGE';
            colTag.classList.add('tag-hedge');
        }
        // Priority 3: FRESH (High Volume relative to OI)
        else if (flow.vol_oi > 5) {
            colTag.textContent = 'FRESH';
            colTag.classList.add('tag-fresh');
        }
        // Priority 4: Standard Direction
        else if (isCall) {
            colTag.textContent = 'BULL';
            colTag.classList.add('tag-bull');
        } else {
            colTag.textContent = 'BEAR';
            colTag.classList.add('tag-bear');
        }

        // Secondary Tag: ITM / OTM (Append if space allows or as a small badge)
        // We will append a small span for ITM/OTM if available
        if (flow.moneyness) {
            const moneySpan = document.createElement('span');
            moneySpan.textContent = flow.moneyness;
            moneySpan.className = flow.moneyness === 'ITM' ? 'tag-itm' : 'tag-otm';
            // Insert before the main tag
            colTag.insertBefore(moneySpan, colTag.firstChild);
        }

        row.appendChild(colTicker);
        row.appendChild(colPremium);
        row.appendChild(colStrike);
        row.appendChild(colTag);

        return row;
    }

    // Start SSE Stream
    initWhaleStream();

    // Periodic cleanup: Remove NEW badges after 10 minutes
    setInterval(() => {
        const now = Date.now();
        document.querySelectorAll('[data-trade-id]').forEach(row => {
            const tradeId = row.dataset.tradeId;
            const firstSeen = tradeFirstSeen.get(tradeId);

            if (firstSeen && (now - firstSeen >= NEW_BADGE_DURATION)) {
                // Remove the NEW badge if it exists
                const badge = row.querySelector('.whale-new-badge');
                if (badge) {
                    badge.remove();
                }
            }
        });
    }, 30000); // Check every 30 seconds

    // Dynamic Alert Stream Logic
    const MOCK_ALERTS = [
        { source: "@OSINT_CYBER", time: "JUST NOW", text: "⚡ NVDA large block of calls detected. $2.5M premium.", isCritical: true },
        { source: "@WHALE_WATCH", time: "1m ago", text: "🕵️ TSLA insider selling reported. 50k shares.", isCritical: false },
        { source: "@MARKET_FLOW", time: "3m ago", text: "🐳 SPY dark pool print: $450M at 445.20.", isCritical: true },
        { source: "@FED_WIRE", time: "5m ago", text: "🏛️ Powell speech scheduled for Friday 2PM EST.", isCritical: false },
        { source: "@CRYPTO_ALERT", time: "8m ago", text: "⚡ BTC breaks resistance at 65k. Volume spiking.", isCritical: true },
        { source: "@OPTIONS_FLOW", time: "10m ago", text: "⚡ AMD put sweep. Bearish sentiment increasing.", isCritical: false },
        { source: "@INSIDER_INTEL", time: "12m ago", text: "🕵️ META CFO files form 4. Sold 10k shares.", isCritical: false },
        { source: "@GOV_WATCH", time: "15m ago", text: "🏛️ SEC announces new oversight rules for crypto.", isCritical: true },
        { source: "@MOMENTUM", time: "18m ago", text: "⚡ AAPL breaking multi-year highs.", isCritical: true },
    ];

    // PCR Chart Logic Removed (Replaced by Gamma Wall)
    let isNewsHovered = false;
    let lastTopNewsSignature = ''; // Track the newest item

    function renderNews(newsItems) {
        const track = document.getElementById('news-track');
        if (!track) return;

        // Filter for Last 24 Hours (86400 seconds)
        const now = new Date().getTime() / 1000;
        const last24Hours = now - 86400;

        const validNews = newsItems.filter(item => item.time >= last24Hours);


        if (validNews.length === 0) {
            track.innerHTML = '<div class="news-item placeholder"><div class="news-headline" style="color: #666;">NO RECENT NEWS FOUND</div></div>';
            return;
        }

        // Sort Newest First
        validNews.sort((a, b) => b.time - a.time);

        // Check if the top news item has changed
        const topItem = validNews[0];
        const topItemSignature = topItem ? `${topItem.ticker || ''}_${topItem.time}_${topItem.title} ` : '';

        let shouldSnap = false;
        if (topItemSignature && topItemSignature !== lastTopNewsSignature) {

            shouldSnap = true;
            lastTopNewsSignature = topItemSignature;
        }

        // Clear Track
        track.innerHTML = '';

        // Helper to create card
        const createCard = (item) => {
            const div = document.createElement('div');
            div.className = 'news-item';

            // Highlight Logic
            const highlightRegex = /\b(MAG 7|TRUMP|AI|OPENAI|ARTIFICIAL INTELLIGENCE|FED|RATE|INFLATION|JOB|LABOR|UNEMPLOYMENT|CPI|PPI|FOMC|POWELL|QQQ|SPY|VIX|NVIDIA|NVDA|TESLA|TSLA|APPLE|AAPL|MICROSOFT|MSFT|META|GOOGLE|GOOG|GOOGL|AMAZON|AMZN|AMD|PLTR|COIN|MSTR|GME|AMC|HOOD|SOFI|UPST)\b/i;
            const upperTitle = item.title.toUpperCase();
            const upperTicker = (item.ticker || '').toUpperCase();

            if (highlightRegex.test(upperTitle) || upperTicker === 'TRUMP') {
                div.classList.add('news-highlight-mag7');
            }

            // Format Time
            const date = new Date(item.time * 1000);
            const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

            // Source Color Logic
            let sourceColor = '#EAEAEA';
            const pub = (item.publisher || '').toLowerCase();
            if (pub.includes('techcrunch')) sourceColor = '#00FF00';
            else if (pub.includes('verge')) sourceColor = '#EAEAEA';
            else if (pub.includes('cnbc')) sourceColor = '#00AACC';
            else if (pub.includes('reuters')) sourceColor = '#FF8800';
            else if (pub.includes('bloomberg')) sourceColor = '#0077FF';
            else if (pub.includes('breaking')) sourceColor = '#FF3333';
            else if (pub.includes('investing')) sourceColor = '#FFA500';
            else if (pub.includes('yahoo')) sourceColor = '#720e9e';

            // Logo Logic (Minimalistic)
            let logoHtml = '';
            if (item.domain) {
                const logoUrl = `https://www.google.com/s2/favicons?domain=${item.domain}&sz=64`;
                logoHtml = `<img src="${logoUrl}" class="news-source-logo" alt="${item.publisher}" onerror="this.style.display='none'">`;
            }

            div.innerHTML = `
    <div class="news-meta">
                    ${logoHtml}
                    <span class="news-source-tag" style="color: ${sourceColor}">${item.publisher || 'WIRE'}</span>
                    <span class="news-time">${timeStr}</span>
                </div>
    <div class="news-headline"><a href="${item.link}" target="_blank" style="color: inherit; text-decoration: none;">${item.title}</a></div>
`;
            return div;
        };

        // Render Original Set
        validNews.forEach(item => {
            track.appendChild(createCard(item));
        });

        // Render Duplicate Set (for seamless loop)
        validNews.forEach(item => {
            const clone = createCard(item);
            clone.setAttribute('aria-hidden', 'true'); // Accessibility
            track.appendChild(clone);
        });

        // Start the JS Ticker
        startNewsTicker(shouldSnap);
    }

    function startNewsTicker(forceSnap = false) {
        const container = document.getElementById('news-items-list');
        const track = document.getElementById('news-track');
        if (!container || !track) return;

        // Reset state
        if (window.newsAnimationFrame) cancelAnimationFrame(window.newsAnimationFrame);

        // Event Listeners for Pause
        // Event Listeners for Pause (Targeting the whole widget for better UX)
        const newsFeedContainer = document.getElementById('news-feed-container');
        const targetForHover = newsFeedContainer || container;

        const updateAutoScrollBtn = (paused) => {
            const btn = document.getElementById('auto-scroll-indicator');
            const txt = document.getElementById('auto-scroll-text');
            if (btn && txt) {
                if (paused) {
                    btn.classList.remove('style-success');
                    btn.classList.add('style-warning');
                    txt.textContent = 'HOVER PAUSE';
                } else {
                    btn.classList.remove('style-warning');
                    btn.classList.add('style-success');
                    txt.textContent = 'AUTO-SCROLL';
                }
            }
        };

        targetForHover.onmouseenter = () => {
            isNewsHovered = true;
            updateAutoScrollBtn(true);
        };
        targetForHover.onmouseleave = () => {
            isNewsHovered = false;
            updateAutoScrollBtn(false);
        };
        targetForHover.ontouchstart = () => {
            isNewsHovered = true;
            updateAutoScrollBtn(true);
        };
        targetForHover.ontouchend = () => {
            isNewsHovered = false;
            updateAutoScrollBtn(false);
        };

        let scrollPos = container.scrollLeft;

        // Force Snap Logic
        if (forceSnap) {
            scrollPos = 0;
            container.scrollLeft = 0;
        }

        const speed = 0.5; // Pixels per frame (Adjust for speed)

        function animate() {
            if (!isNewsHovered) {
                scrollPos += speed;

                // Seamless Loop Logic
                // Since we duplicated content, the track width is 2x the content width.
                // When we scroll past half the track width, we reset to 0.
                // However, 'scrollWidth' includes the hidden overflow.
                // We need to know the width of the *original* content set.
                // Approximation: Total width / 2

                const maxScroll = track.scrollWidth / 2;

                // Robust Loop: If we reach OR EXCEED the midpoint, snap back to 0
                if (scrollPos >= maxScroll) {
                    scrollPos = 0;
                }

                container.scrollLeft = scrollPos;
            } else {
                // If hovered, update scrollPos to current manual scroll position so it doesn't jump when resuming
                scrollPos = container.scrollLeft;
            }

            window.newsAnimationFrame = requestAnimationFrame(animate);
        }

        window.newsAnimationFrame = requestAnimationFrame(animate);
    }

    // === UTILITY: Safe Execution Wrapper ===
    function safeExecute(widgetName, fn) {
        try {
            fn();
        } catch (error) {
            console.error(`[CRITICAL] ${widgetName} Crashed: `, error);
            // Optional: Update UI to show "OFFLINE" for this specific widget?
        }
    }

    // === UTILITY: Debounce Function ===
    function debounce(func, delay) {
        let timeout;
        return function (...args) {
            const context = this;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), delay);
        };
    }

    // === UTILITY: Simple Cache Function ===
    function cache(func, ttl = 300000) { // Default TTL 5 minutes (300,000 ms)
        const cacheStore = new Map();
        return async function (...args) {
            const key = JSON.stringify(args);
            const now = Date.now();
            // Simple in-memory cache not used for Gamma, we keep localStorage helpers below

            if (cacheStore.has(key)) {
                const { value, timestamp } = cacheStore.get(key);
                if (now - timestamp < ttl) {
                    // console.log(`Cache hit for key: ${key}`);
                    return value;
                } else {
                    // console.log(`Cache expired for key: ${key}`);
                    cacheStore.delete(key); // Invalidate expired cache
                }
            }

            // console.log(`Cache miss for key: ${key}, fetching...`);
            const result = await func.apply(this, args);
            cacheStore.set(key, { value: result, timestamp: now });
            return result;
        };
    }

    // Helper: LocalStorage cache for Gamma Wall (TTL 2 minutes)
    const GAMMA_CACHE_TTL = 2 * 60 * 1000;
    function getGammaCache(ticker) {
        const key = `gamma_cache_${ticker}`;
        const raw = localStorage.getItem(key);
        if (!raw) return null;
        try {
            const parsed = JSON.parse(raw);
            if (Date.now() - parsed.timestamp < GAMMA_CACHE_TTL) {
                return parsed.data;
            }
            localStorage.removeItem(key);
            return null;
        } catch {
            return null;
        }
    }
    function setGammaCache(ticker, data) {
        const key = `gamma_cache_${ticker}`;
        const payload = { timestamp: Date.now(), data };
        localStorage.setItem(key, JSON.stringify(payload));
    }



    // Initial Fetch & Interval
    safeExecute('News Feed', fetchNews);
    setInterval(() => safeExecute('News Feed Update', fetchNews), 60000); // Every 1 minute

    safeExecute('Gamma Wall', initGammaWall);

    // Initialize TradingView Widget
    safeExecute('TradingView Main', () => createTradingViewWidget(currentTicker));

    // Set initial selector value
    if (tickerSelect) {
        tickerSelect.value = currentTicker;
    }

    // Start Data Stream (Mock for other widgets)
    if (window.mockDataService) {
        // Mock Data Service handles its own try/catch internally usually, but we can wrap the callback if needed
        // For now, assuming mockDataService is robust enough or we leave it as is since it drives multiple things
        window.mockDataService.startDataStream((data) => {
            // ...
        });
    } else {
        console.error("Mock Data Service not found!");
    }

    // Start Movers Tape (Real Data)
    safeExecute('Ticker Tape', startMoversSlideshow);

    // TFI Macro Update Loop (30 Minutes)
    // fetchVIX(); // Initial Render - DISABLED, using CNN Fear & Greed instead
    // setInterval(fetchVIX, 30 * 60 * 1000); // 30 Minutes - DISABLED
});
