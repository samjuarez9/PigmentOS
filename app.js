
// app.js

document.addEventListener('DOMContentLoaded', () => {
    console.log('✅ JavaScript is loading and DOMContentLoaded fired!');

    // === GLOBAL CONFIGURATION ===
    const IS_FILE_PROTOCOL = window.location.protocol === 'file:';
    const isLocal = window.location.hostname === 'localhost' ||
        window.location.hostname === '127.0.0.1' ||
        IS_FILE_PROTOCOL;
    const API_BASE_URL = isLocal ? 'http://localhost:8001' : 'https://pigmentos.onrender.com';
    console.log('🚀 PigmentOS Config:', { API_BASE_URL, hostname: window.location.hostname, isLocal });

    // === ANALYTICS HELPER ===
    function trackEvent(eventName, params = {}) {
        if (window.pigmentAnalytics && window.pigmentAnalytics.logEvent) {
            // console.log(`[Analytics] Tracking: ${eventName}`, params);
            window.pigmentAnalytics.logEvent(window.pigmentAnalytics.analytics, eventName, params);
        }
    }

    function setUserProperty(properties = {}) {
        if (window.pigmentAnalytics && window.pigmentAnalytics.setUserProperties) {
            window.pigmentAnalytics.setUserProperties(window.pigmentAnalytics.analytics, properties);
        }
    }

    // === GLOBAL STATE ===
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
                        latencyEl.textContent = `${latency}ms`;

                        // Sample latency (track every ~10th check to avoid spam)
                        if (Math.random() < 0.1) {
                            trackEvent('performance_metric', { metric: 'api_latency', value: latency });
                        }
                        if (latency < 100) latencyEl.style.color = 'var(--primary-color)';
                        else if (latency < 300) latencyEl.style.color = 'var(--warning-color)';
                        else latencyEl.style.color = '#ff3333';
                    }

                    // Update WiFi signal bars based on latency
                    const wifiSignal = document.getElementById('wifi-bars');
                    if (wifiSignal) {
                        wifiSignal.classList.remove('weak', 'fair', 'good', 'excellent', 'disconnected');
                        if (latency < 100) wifiSignal.classList.add('excellent');
                        else if (latency < 200) wifiSignal.classList.add('good');
                        else if (latency < 400) wifiSignal.classList.add('fair');
                        else wifiSignal.classList.add('weak');
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
                "symbol": ticker,
                "interval": "15",
                "timezone": "Etc/UTC",
                "theme": "dark",
                "style": "1", // Candle style
                "locale": "en",
                "enable_publishing": false,
                "hide_top_toolbar": true,
                "studies": [
                    "MASimple@tv-basicstudies",    // Simple Moving Average
                    "RSI@tv-basicstudies"          // RSI (14-period) - Overbought/Oversold
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

    const WATCHLIST_TICKERS = [
        // Magnificent 7
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA',

        // Indices & ETFs
        'SPY', 'QQQ', 'IWM',

        // Semiconductors & AI Hardware
        'AMD', 'INTC', 'MU', 'AVGO', 'TSM', 'ARM', 'SMCI',

        // AI & Cloud
        'PLTR', 'ORCL', 'CRWD',

        // FinTwit Memes & High Volume
        'GME', 'AMC',

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

    // === TFI DAMAGE ANIMATION STATE (must be before updateTFI call) ===
    let previousTFIScore = null;

    function spawnDamageNumber(delta, container) {
        const ghost = document.createElement('div');
        ghost.className = 'tfi-damage-number';
        ghost.textContent = `-${delta}`;

        // Color based on severity
        if (delta >= 10) {
            ghost.style.color = '#FF0000'; // Bright red for big drops
        } else if (delta >= 5) {
            ghost.style.color = '#FF6600'; // Orange for medium drops
        } else {
            ghost.style.color = '#FFCC00'; // Yellow for small drops
        }

        container.appendChild(ghost);

        // Shake the container
        container.classList.add('shake');
        setTimeout(() => container.classList.remove('shake'), 200);

        // Remove ghost after animation
        setTimeout(() => ghost.remove(), 900);
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
                label2 && typeof label2 === 'string' && label2.toLowerCase() === 'no';

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
    // fetchPolymarketData(); // Initial render - MOVED TO STAGGERED INIT
    setInterval(fetchPolymarketData, 30000); // Refresh every 30 seconds

    // Initialize Chart
    // createTradingViewWidget(currentTicker); // MOVED TO STAGGERED INIT

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
        const gainers = moversData.filter(m => m.type === 'gain').sort((a, b) => b.change - a.change);
        const losers = moversData.filter(m => m.type === 'loss').sort((a, b) => a.change - b.change);

        // Select set to display - LIMIT TO 6 ITEMS MAX for compact view
        const currentSet = (showGainers ? gainers : losers).slice(0, 6);
        const label = showGainers ? '🔥 HOT' : '❄️ COLD';
        const labelClass = showGainers ? 'mover-hot' : 'mover-cold';
        console.log(`[DEBUG] Movers Tape Update - Label: ${label}, Class: ${labelClass}`);

        // Build HTML with cascading delays and "tease" on last item
        const itemsHtml = currentSet.map((m, index) => {
            const colorClass = m.type === 'gain' ? 'mover-hot' : 'mover-cold';
            const changeStr = m.change > 0 ? `+${m.change}%` : `${m.change}%`;

            // THE TEASE LOGIC: Last item waits 1200ms, others cascade 100ms apart
            const isLastItem = index === currentSet.length - 1;
            const delay = isLastItem ? 1200 : (index + 1) * 100;

            return `<span class="mover-item reel-item" style="animation-delay: ${delay}ms">
                <span class="mover-symbol">${m.symbol}</span>
                <span class="mover-change ${colorClass}">${changeStr}</span>
            </span>`;
        }).join('');

        // Build with viewport and track for arcade reel animation
        // Label is INSIDE the track so it animates together with tickers
        const newTrackHtml = `
            <div class="ticker-viewport">
                <div class="ticker-track reel-in">
                    <span class="mover-label ${labelClass}">${label}</span>
                    <div class="mover-items">${itemsHtml}</div>
                </div>
            </div>
        `;

        // Arcade Reel Animation: Out -> In
        const existingTrack = priceTicker.querySelector('.ticker-track');
        if (existingTrack) {
            // Animate out (fast drop)
            existingTrack.classList.remove('reel-in');
            existingTrack.classList.add('reel-out');

            setTimeout(() => {
                priceTicker.innerHTML = newTrackHtml;
            }, 250); // Match reelOut duration (fast)
        } else {
            priceTicker.innerHTML = newTrackHtml;
        }

        // Toggle for next update
        showGainers = !showGainers;
    }

    function selectTicker(ticker) {
        if (ticker === currentTicker) return;

        currentTicker = ticker;
        localStorage.setItem('pigment_current_ticker', currentTicker);

        trackEvent('chart_ticker_change', { ticker: currentTicker });

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

        // Switch slides every 20s (increased for reading time)
        setInterval(updateMoversTape, 20000);
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

    // Helper: LocalStorage cache for Heatmap (TTL 15 minutes)
    const HEATMAP_CACHE_TTL = 15 * 60 * 1000;
    function getHeatmapCache() {
        const raw = localStorage.getItem('heatmap_cache');
        if (!raw) return null;
        try {
            const parsed = JSON.parse(raw);
            if (Date.now() - parsed.timestamp < HEATMAP_CACHE_TTL) return parsed.data;
            return null;
        } catch { return null; }
    }
    function setHeatmapCache(data) {
        localStorage.setItem('heatmap_cache', JSON.stringify({ timestamp: Date.now(), data }));
    }

    async function fetchHeatmapData(retryCount = 0) {
        // 1. Check Cache & Render Immediately (only on first load)
        if (!heatmapHasLoaded) {
            const cached = getHeatmapCache();
            if (cached) {
                renderMarketMap(cached, false);
                heatmapHasLoaded = true;
                updateStatus('status-sectors', true);
            }
        }

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

            // 2. Update Cache & Re-render
            setHeatmapCache(data);
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
            // Only show error if we have no data at all
            if (!heatmapHasLoaded && !getHeatmapCache()) {
                updateStatus('status-sectors', false);
                renderHeatmapError();
            }
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

            trackEvent('market_map_view_change', { view: currentSectorView });

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

        // === DAMAGE ANIMATION ON SCORE DROP ===
        const roundedValue = Math.round(value);
        if (previousTFIScore !== null && roundedValue < previousTFIScore) {
            const delta = previousTFIScore - roundedValue;
            spawnDamageNumber(delta, tfiContainer);
        }
        previousTFIScore = roundedValue;

        // Update score and rating
        const tfiScore = document.getElementById('tfi-score');
        const tfiRating = document.getElementById('tfi-rating');
        const tfiVixRef = document.getElementById('tfi-vix-ref');

        if (tfiScore && tfiRating) {
            tfiScore.textContent = roundedValue;
            tfiRating.textContent = rating.toUpperCase();
            tfiRating.style.color = ""; // Reset color
        }

        // Update source reference
        if (tfiVixRef && source) {
            tfiVixRef.textContent = source;
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
    // Helper: LocalStorage cache for TFI (TTL 1 hour)
    const TFI_CACHE_TTL = 60 * 60 * 1000;
    function getTFICache() {
        const raw = localStorage.getItem('tfi_cache');
        if (!raw) return null;
        try {
            const parsed = JSON.parse(raw);
            if (Date.now() - parsed.timestamp < TFI_CACHE_TTL) return parsed.data;
            return null;
        } catch { return null; }
    }
    function setTFICache(data) {
        localStorage.setItem('tfi_cache', JSON.stringify({ timestamp: Date.now(), data }));
    }

    async function fetchCNNFearGreed() {
        // 1. Check Cache & Render Immediately
        const cached = getTFICache();
        if (cached) {
            updateTFI(cached.value, cached.rating, cached.source);
            updateStatus('status-tfi', true);
        }

        try {
            const response = await fetch(`${API_BASE_URL}/api/cnn-fear-greed`);
            if (!response.ok) throw new Error('CNN Fear & Greed API Failed');

            const data = await response.json();

            // 2. Update Cache & Re-render
            setTFICache(data);
            updateTFI(data.value, data.rating, data.source);

            updateStatus('status-tfi', true);
        } catch (error) {
            console.error('CNN Fear & Greed API Failed:', error);
            if (!cached) updateStatus('status-tfi', false); // Only show offline if no cache
        }
    }
    // fetchCNNFearGreed(); // MOVED TO STAGGERED INIT
    setInterval(fetchCNNFearGreed, 300000); // Refresh every 5 minutes (was 12 hours)

    // Initialize Market Map
    // fetchHeatmapData(); // MOVED TO STAGGERED INIT
    setInterval(fetchHeatmapData, 300000); // Refresh every 5 minutes

    // Helper: Update API Status Indicator
    function updateStatus(elementId, isLive) {
        const container = document.getElementById(elementId);
        if (container) {
            const textSpan = container.querySelector('.status-text');
            const dotSpan = container.querySelector('.status-dot');

            if (isLive) {
                container.classList.add('status-live');
                if (textSpan) textSpan.textContent = "LIVE";
                if (dotSpan) dotSpan.style.display = ""; // Reset to CSS default (inline-block via class)
            } else {
                container.classList.remove('status-live');
                if (textSpan) textSpan.textContent = "OFFLINE";
                if (dotSpan) dotSpan.style.display = "none"; // Explicitly hide
            }
        }
    }

    // UW Flow Feed Logic (High Value)
    const flowFeedContainer = document.getElementById('flow-feed-container');
    let isFlowPaused = false;

    // Pause on Hover & Analytics
    if (flowFeedContainer) {
        flowFeedContainer.addEventListener('mouseenter', () => { isFlowPaused = true; });
        flowFeedContainer.addEventListener('mouseleave', () => { isFlowPaused = false; });

        // Track Scroll
        let lastScrollTime = 0;
        flowFeedContainer.addEventListener('scroll', () => {
            const now = Date.now();
            if (now - lastScrollTime > 2000) { // Debounce 2s
                trackEvent('whale_feed_interaction', { action: 'scroll' });
                lastScrollTime = now;
            }
        });

        // Track Clicks on Rows
        flowFeedContainer.addEventListener('click', (e) => {
            const row = e.target.closest('.whale-row');
            if (row) {
                trackEvent('whale_feed_interaction', { action: 'click', ticker: row.querySelector('.ticker-cell')?.textContent });
            }
        });
    }

    // Whale title click -> Expanded page (DISABLED - Not ready for production)

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
    const NEW_BADGE_DURATION = 10 * 60 * 1000; // 10 minutes

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

        // === PRE-MARKET / AFTER HOURS / WEEKEND MODE: Show radar scanning animation ===
        const existingTrades = document.querySelectorAll('.whale-row');
        if ((marketState.isPreMarket || marketState.isAfterHours || marketState.isWeekend) && existingTrades.length === 0) {
            // Clear all tracking caches for fresh start at market open
            seenTrades.clear();
            tradeFirstSeen.clear();
            previousSnapshotTradeIds.clear();

            const flowFeedContainer = document.getElementById('flow-feed-container');
            if (flowFeedContainer) {
                let statusText = "STATUS: PRE-MARKET. Monitoring for block orders...";
                if (marketState.isWeekend) statusText = "STATUS: WEEKEND. Monitoring for block orders...";
                else if (marketState.isAfterHours) statusText = "STATUS: AFTER HOURS. Monitoring for block orders...";

                flowFeedContainer.innerHTML = `
                    <div class="whale-pre-market-container">
                        <div class="radar-container">
                            <div class="radar-ring radar-ring-1"></div>
                            <div class="radar-ring radar-ring-2"></div>
                            <div class="radar-ring radar-ring-3"></div>
                            <div class="radar-center"></div>
                        </div>
                        <div class="status-message">
                            <span style="color: #888; font-size: 11px; font-family: var(--font-mono);">
                                ${statusText}
                            </span>
                        </div>
                    </div>
                `;
            }
            updateStatus('status-whales', isSystemHealthy);
            return; // Exit early
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
        // IMPORTANT: Don't clear existing trades! Just wait for more data.
        if (!hasData) {
            // If there are already trades displayed, just keep them and wait for more
            const existingTrades = flowFeedContainer.querySelectorAll('.whale-row');
            if (existingTrades.length > 0) {
                return; // Keep existing trades, don't clear
            }

            // Only show waiting message if truly empty (first load)
            if (isSystemHealthy) {
                const waitingDiv = document.createElement('div');
                waitingDiv.className = 'placeholder-item';
                waitingDiv.textContent = 'Waiting for trade...';
                flowFeedContainer.innerHTML = ''; // Clear only if no existing trades
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
                iv: item.iv,
                side: item.side, // Fix: Pass the aggressor side (BUY/SELL)
                bid: item.bid,
                ask: item.ask
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

        // === THROTTLED RENDERING ===
        // Instead of rendering all at once, drip them in one-by-one with delay
        const RENDER_DELAY_MS = 200; // 200ms between each trade
        const MAX_BATCH_SIZE = 10; // Max trades to animate per cycle (prevents runaway)

        const batchToRender = tradesToRender.slice(0, MAX_BATCH_SIZE);

        batchToRender.forEach(({ flow, id, isNew }, index) => {
            setTimeout(() => {
                const div = createFlowElement(flow, id, isNew);
                div.dataset.tradeId = id;

                // Prepend new items (Slide In Animation handled by CSS)
                flowFeedContainer.insertBefore(div, flowFeedContainer.firstChild);

                // Limit to 50 items to prevent DOM bloat
                if (flowFeedContainer.children.length > 50) {
                    flowFeedContainer.lastChild.remove();
                }
            }, index * RENDER_DELAY_MS);
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


    // Cache DOM references for performance (avoid re-querying every render)
    let gammaTooltip = null;
    let gammaTitle = null;
    let gammaHeader = null;

    // Initialize Gamma Wall
    function initGammaWall() {
        const gammaSelector = document.getElementById('gamma-ticker-select');
        if (gammaSelector) {
            gammaSelector.value = currentGammaTicker;
            gammaSelector.addEventListener('change', (e) => {
                currentGammaTicker = e.target.value;
                trackEvent('gamma_ticker_change', { ticker: currentGammaTicker });
                fetchGammaWall(currentGammaTicker);
            });
        }

        // Initial Fetch
        fetchGammaWall(currentGammaTicker);

        // Refresh data every 5 minutes
        setInterval(() => fetchGammaWall(currentGammaTicker), 300000);

        // Refresh PRICE every 60 seconds (Independent of full data refresh)
        setInterval(() => updateGammaPrice(), 60000);
    }

    async function updateGammaPrice() {
        if (!currentGammaTicker) return;

        try {
            const res = await fetch(`/api/price?symbol=${currentGammaTicker}`);
            if (res.ok) {
                const data = await res.json();
                if (data.price && window.currentGammaData) {
                    // Update the cached data object with new price
                    window.currentGammaData.current_price = data.price;
                    window.currentGammaData._price_source = data.source; // Debug info

                    // Re-render the chart with new price (updates ATM row and tooltips)
                    renderGammaChart(window.currentGammaData);
                    console.log(`[Gamma] Updated price for ${currentGammaTicker}: $${data.price} (${data.source})`);
                }
            }
        } catch (e) {
            console.error("Gamma Price Update Failed:", e);
        }
    }

    async function fetchGammaWall(ticker = 'SPY') {
        // Check localStorage cache first (TTL 2 minutes)
        try {
            // Add/Reset Loading Bar
            let loadingBar = document.querySelector('.gamma-loading-bar');
            if (!loadingBar) {
                loadingBar = document.createElement('div');
                loadingBar.className = 'gamma-loading-bar';
                const container = document.querySelector('.gamma-chart-wrapper');
                if (container) container.appendChild(loadingBar);
            }

            // Trigger animation
            requestAnimationFrame(() => {
                loadingBar.classList.add('loading');
            });

            // Only show full loader if NO data exists at all
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
                window.currentGammaData = cached; // Store for price updates
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
            window.currentGammaData = data; // Store for price updates

            // Reset Loading Bar
            const finishedLoadingBar = document.querySelector('.gamma-loading-bar');
            if (finishedLoadingBar) {
                finishedLoadingBar.classList.remove('loading');
                finishedLoadingBar.style.width = '100%'; // Ensure it looks complete
                setTimeout(() => {
                    finishedLoadingBar.style.width = '0%';
                }, 300);
            }

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

        // === PREMARKET EMPTY STATE ===
        // If we have no strikes but a valid response (premarket wait), show waiting message
        if (data.strikes.length === 0 && data.source === 'premarket_wait') {
            gammaChartBars.innerHTML = `
                <div class="gamma-waiting-container">
                    <div class="gamma-waiting-icon">⏳</div>
                    <div class="gamma-waiting-text">MARKET CLOSED</div>
                    <div class="gamma-waiting-sub">AWAITING OPEN (9:30 AM ET)</div>
                </div>
            `;

            // Update Header to show we are connected but waiting
            if (!gammaHeader) gammaHeader = document.querySelector('#gamma-wall .widget-header h2');
            if (gammaHeader) {
                gammaHeader.innerHTML = `GAMMA WALL <span class="today-badge-purple">PRE-MKT</span>`;
            }

            return;
        }

        // Create Tooltip once (cached)
        if (!gammaTooltip) {
            gammaTooltip = document.getElementById('gamma-tooltip');
            if (!gammaTooltip) {
                gammaTooltip = document.createElement('div');
                gammaTooltip.id = 'gamma-tooltip';
                gammaTooltip.className = 'gamma-tooltip';
                gammaTooltip.style.opacity = '0';
                document.body.appendChild(gammaTooltip);
            }
        }

        // Spot Price Line Logic
        // Remove existing line first
        const existingLine = gammaChartBars.querySelector('.gamma-spot-line');
        if (existingLine) existingLine.remove();

        // Calculate position
        // We need to find where the current price sits relative to the rendered rows
        // Rows are sorted High -> Low (Top -> Bottom)

        // Find the two strikes surrounding the price
        let upperStrike = null;
        let lowerStrike = null;
        let upperRow = null;
        let lowerRow = null;

        const renderedRows = Array.from(gammaChartBars.children).filter(el => el.classList.contains('gamma-row'));

        for (let i = 0; i < renderedRows.length; i++) {
            const row = renderedRows[i];
            const strike = parseFloat(row.dataset.strike);

            if (strike >= data.current_price) {
                upperStrike = strike;
                upperRow = row;
            } else {
                lowerStrike = strike;
                lowerRow = row;
                break; // Found the crossover point
            }
        }

        if (upperRow && lowerRow) {
            // Interpolate position
            const priceRange = upperStrike - lowerStrike;
            const priceDelta = upperStrike - data.current_price; // Distance from top strike
            const ratio = priceDelta / priceRange;

            // Get DOM positions
            const upperTop = upperRow.offsetTop;
            const lowerTop = lowerRow.offsetTop;
            const rowHeight = upperRow.offsetHeight; // Assuming uniform height

            // Calculate pixel position (relative to container)
            // Center of upper row to Center of lower row distance
            const centerDist = lowerTop - upperTop;

            // Start from center of upper row
            const startY = upperTop + (rowHeight / 2);
            const pixelOffset = centerDist * ratio;
            const finalTop = startY + pixelOffset;

            // Create Line
            const line = document.createElement('div');
            line.className = 'gamma-spot-line';
            line.style.top = `${finalTop}px`;

            const label = document.createElement('div');
            label.className = 'gamma-spot-label';
            label.textContent = data.current_price.toFixed(2);
            line.appendChild(label);

            gammaChartBars.appendChild(line);
        } else if (upperRow && !lowerRow) {
            // Price is below all visible strikes (at bottom)
            const line = document.createElement('div');
            line.className = 'gamma-spot-line';
            line.style.top = `${upperRow.offsetTop + upperRow.offsetHeight}px`;
            const label = document.createElement('div');
            label.className = 'gamma-spot-label';
            label.textContent = data.current_price.toFixed(2);
            line.appendChild(label);
            gammaChartBars.appendChild(line);
        } else if (!upperRow && lowerRow) {
            // Price is above all visible strikes (at top)
            const line = document.createElement('div');
            line.className = 'gamma-spot-line';
            line.style.top = `${lowerRow.offsetTop}px`;
            const label = document.createElement('div');
            label.className = 'gamma-spot-label';
            label.textContent = data.current_price.toFixed(2);
            line.appendChild(label);
            gammaChartBars.appendChild(line);
        }


        // Cache DOM references on first render
        if (!gammaTitle) gammaTitle = document.querySelector('.gamma-title');
        if (!gammaHeader) gammaHeader = document.querySelector('#gamma-wall .widget-header h2');

        // Update Header
        if (gammaTitle) {
            let html = `GAMMA WALL`;
            if (data.time_period === 'weekend') {
                html += ` <span class="monday-badge">MON</span>`;
            } else if (data.time_period === 'after_hours') {
                html += ` <span class="today-badge-green">TODAY</span>`;
            } else if (data.time_period === 'pre_market') {
                html += ` <span class="today-badge-purple">TODAY</span>`;
            } else if (data.time_period === 'overnight') {
                html += ` <span class="today-badge-dim">TODAY</span>`;
            }
            gammaTitle.innerHTML = html;
            gammaTitle.innerHTML = html;
        }

        // Update DTE Display (Tiny text in black header)
        const dteDisplay = document.getElementById('gamma-dte-display');
        if (dteDisplay && data._expiry_date) {
            const expiryParts = data._expiry_date.split('-');
            const expiryDate = new Date(expiryParts[0], expiryParts[1] - 1, expiryParts[2]);
            const today = new Date();
            today.setHours(0, 0, 0, 0);

            // Calculate difference in days
            const diffTime = expiryDate - today;
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

            let dteText = "";
            if (diffDays === 0) dteText = "0DTE";
            else if (diffDays === 1) dteText = "1DTE";
            else dteText = `${diffDays}DTE`;

            dteDisplay.textContent = dteText;
        } else if (dteDisplay) {
            dteDisplay.textContent = "";
        }

        let totalCallVol = 0;
        let totalPutVol = 0;
        let totalCallGex = 0;
        let totalPutGex = 0;
        data.strikes.forEach(s => {
            totalCallVol += s.call_vol || 0;
            totalPutVol += s.put_vol || 0;
            totalCallGex += s.call_gex || 0;
            totalPutGex += Math.abs(s.put_gex || 0);  // put_gex is stored negative, use absolute
        });

        // Helper: Format volume (42000 → "42K")
        const formatVol = (vol) => {
            if (vol >= 1000) return (vol / 1000).toFixed(1).replace('.0', '') + 'K';
            return vol.toString();
        };

        // === DOMINANCE BADGE (Based on VOLUME) ===
        // Switched to Volume as it's a clearer indicator of sentiment (Put/Call Ratio style)
        const totalVol = totalCallVol + totalPutVol;
        let dominanceBadgeHtml = '';
        if (totalVol > 0) {
            const callVolPct = (totalCallVol / totalVol) * 100;
            const putVolPct = (totalPutVol / totalVol) * 100;
            const diff = Math.abs(callVolPct - putVolPct);

            if (diff >= 10) {
                if (callVolPct > putVolPct) {
                    // Show Percent of Total (e.g. 60%) instead of Difference (20%)
                    dominanceBadgeHtml = `<span class="dominance-badge bullish">CALLS ${Math.round(callVolPct)}%</span>`;
                } else {
                    dominanceBadgeHtml = `<span class="dominance-badge bearish">PUTS ${Math.round(putVolPct)}%</span>`;
                }
            } else {
                dominanceBadgeHtml = `<span class="dominance-badge neutral">BALANCED</span>`;
            }
        }

        // Update Header with dominance badge (using cached gammaHeader)
        // Check if we are showing next trading day data (after 5 PM switch)
        const isNextTradingDay = data._is_next_trading_day || false;
        const dateLabel = data._date_label || "TODAY";

        if (gammaHeader) {
            let html = `GAMMA WALL`;

            if (isNextTradingDay) {
                // Show the specific date (e.g., "FRI DEC 20")
                html += ` <span class="today-badge-orange">${dateLabel}</span>`;
            } else if (data.time_period === 'weekend') {
                html += ` <span class="monday-badge">MON</span>`;
            } else if (data.time_period === 'after_hours') {
                html += ` <span class="today-badge-green">TODAY</span>`;
            } else if (data.time_period === 'pre_market') {
                html += ` <span class="today-badge-purple">TODAY</span>`;
            } else if (data.time_period === 'overnight') {
                html += ` <span class="today-badge-dim">TODAY</span>`;
            }
            html += dominanceBadgeHtml;
            gammaHeader.innerHTML = html;
        }

        // === GHOST MODE: Apply hollow frame styling when market is CLOSED ===
        // Linked to the same getMarketState() logic as the market status button
        const marketState = getMarketState();
        if (gammaChartBars) {
            if (!marketState.isMarketHours) {
                // Market closed (pre-market, after-hours, weekend) → Ghost bars
                gammaChartBars.classList.add('gamma-ghost-mode');
            } else {
                // Market open (9:30 AM - 4 PM weekdays) → Solid bars
                gammaChartBars.classList.remove('gamma-ghost-mode');
            }
        }


        const existingRows = new Map();
        Array.from(gammaChartBars.children).forEach(row => {
            const strike = parseFloat(row.dataset.strike);
            if (!isNaN(strike)) existingRows.set(strike, row);
        });

        // Filter strikes to ±10% of current price (ensures ATM is always visible)
        const spot = data.current_price;
        const range = 0.10; // 10%
        const filteredStrikes = data.strikes.filter(s =>
            s.strike >= spot * (1 - range) &&
            s.strike <= spot * (1 + range)
        );

        console.log('[Gamma] Spot:', spot.toFixed(2), '| Filter range:', (spot * 0.90).toFixed(0), '-', (spot * 1.10).toFixed(0));
        console.log('[Gamma] Total strikes:', data.strikes.length, '| After filter:', filteredStrikes.length);
        if (filteredStrikes.length > 0) {
            const strikes = filteredStrikes.map(s => s.strike).sort((a, b) => b - a);
            console.log('[Gamma] Filtered strikes:', strikes[0], '(high) to', strikes[strikes.length - 1], '(low)');
        }

        // Data is pre-sorted High → Low by server

        // Find ATM Strike (closest to current price) - used for reference only
        let closestStrike = null;
        let minDiff = Infinity;
        data.strikes.forEach(s => {
            const diff = Math.abs(s.strike - data.current_price);
            if (diff < minDiff) {
                minDiff = diff;
                closestStrike = s.strike;
            }
        });
        console.log('[Gamma] Current price:', data.current_price, '| ATM strike:', closestStrike, '| Diff:', minDiff.toFixed(2));

        // === TRUE GAMMA FLIP DETECTION ===
        // Find where Net GEX crosses from positive to negative (or vice versa)
        // This is the volatility inflection point where dealer behavior changes
        let gammaFlipStrike = null;
        for (let i = 0; i < data.strikes.length - 1; i++) {
            const current = data.strikes[i];
            const next = data.strikes[i + 1];
            const currentGex = current.net_gex || 0;
            const nextGex = next.net_gex || 0;

            // Check if GEX sign changes between adjacent strikes
            if ((currentGex >= 0 && nextGex < 0) || (currentGex < 0 && nextGex >= 0)) {
                // Pick the strike closer to zero GEX (the actual flip point)
                gammaFlipStrike = Math.abs(currentGex) < Math.abs(nextGex)
                    ? current.strike
                    : next.strike;
                break; // Only need the first flip point
            }
        }

        // Fallback: If no flip found (all positive or all negative), use ATM
        if (!gammaFlipStrike) {
            gammaFlipStrike = closestStrike;
        }

        // Store current price for tooltip calculations
        window.lastGammaPrice = data.current_price;

        // === FIND THE LARGEST WALLS (KEY LEVELS) ===
        let currentMaxVol = 0;
        let maxCallVol = 0;
        let maxPutVol = 0;

        // === SEPARATE MAGNET & TRIGGER TRACKING ===
        // Magnet (🧲): Max POSITIVE GEX - dealers long gamma, price stabilizes/pins here
        // Trigger (🚀): Max absolute NEGATIVE GEX - dealers short gamma, price accelerates/launches
        let magnetStrike = null;  // Max positive GEX (stabilizing)
        let maxPosGex = 0;
        let triggerStrike = null; // Max absolute negative GEX (volatile)
        let maxNegGex = 0;

        data.strikes.forEach(s => {
            if ((s.call_vol || 0) > maxCallVol) maxCallVol = s.call_vol;
            if ((s.put_vol || 0) > maxPutVol) maxPutVol = s.put_vol;

            const strikeMax = Math.max(s.call_vol || 0, s.put_vol || 0);
            if (strikeMax > currentMaxVol) currentMaxVol = strikeMax;

            // Track magnet (positive GEX) and trigger (negative GEX) separately
            const netGex = s.net_gex || 0;
            if (netGex > 0 && netGex > maxPosGex) {
                maxPosGex = netGex;
                magnetStrike = s.strike;
            } else if (netGex < 0 && Math.abs(netGex) > maxNegGex) {
                maxNegGex = Math.abs(netGex);
                triggerStrike = s.strike;
            }
        });

        // High Water Mark: Scale only grows (prevents jitter), but reset if max drops significantly
        if (!window.gammaGlobalMax || currentMaxVol > window.gammaGlobalMax) {
            window.gammaGlobalMax = currentMaxVol;
        }
        // Reset if current max is less than 50% of stored max (stale scaling)
        if (currentMaxVol < window.gammaGlobalMax * 0.5) {
            window.gammaGlobalMax = currentMaxVol;
        }
        // Reset on ticker change
        if (window.lastGammaTicker !== data.symbol) {
            window.gammaGlobalMax = currentMaxVol;
            window.lastGammaTicker = data.symbol;
            // Reset scroll flag so we scroll to ATM on ticker change
            if (gammaChartBars) gammaChartBars.dataset.scrolled = "";
        }
        // Reset on new trading day (handles users who don't refresh overnight)
        const today = new Date().toDateString();
        if (window.lastGammaDate !== today) {
            window.gammaGlobalMax = currentMaxVol;
            window.lastGammaDate = today;
        }

        const maxVol = window.gammaGlobalMax || 1;

        // Dynamic Row Height Calculation
        // Target container height ~500px. 
        // If few strikes, make rows taller (max 30px). If many, keep compact (min 14px).
        const containerHeight = 500;
        const rowHeight = Math.min(30, Math.max(14, Math.floor(containerHeight / filteredStrikes.length)));

        filteredStrikes.forEach(strikeData => {
            let row = existingRows.get(strikeData.strike);
            const putWidth = (strikeData.put_vol / maxVol) * 100;
            const callWidth = (strikeData.call_vol / maxVol) * 100;

            // Is this the TRUE Gamma Flip point (where Net GEX crosses zero)?
            const isGammaFlip = strikeData.strike === gammaFlipStrike;

            // Is this the ATM strike (closest to current price)?
            const isATM = strikeData.strike === closestStrike;

            // Is this the Largest Call Wall?
            const isMaxCall = (strikeData.call_vol || 0) === maxCallVol && maxCallVol > 0;

            // Is this the Largest Put Wall?
            const isMaxPut = (strikeData.put_vol || 0) === maxPutVol && maxPutVol > 0;

            // Is this the Magnet strike (max positive GEX - stabilizing)?
            const isMagnet = strikeData.strike === magnetStrike && maxPosGex > 0;

            // Is this the Trigger strike (max negative GEX - volatile)?
            const isTrigger = strikeData.strike === triggerStrike && maxNegGex > 0;

            if (row) {
                // Update Height
                row.style.height = `${rowHeight}px`;

                // Update
                const putBar = row.querySelector('.gamma-bar-put');
                const callBar = row.querySelector('.gamma-bar-call');

                if (putBar) putBar.style.width = `${putWidth}%`;
                if (callBar) callBar.style.width = `${callWidth}%`;

                // Apply ATM (Current Price) styling - Blue indicator
                if (isATM) {
                    row.classList.add('atm-row');
                } else {
                    row.classList.remove('atm-row');
                }

                // Apply Gamma Flip label (just text, no full row styling)
                if (isGammaFlip && !isATM) {
                    // Only add FLIP label, not the blue row styling
                    if (!row.querySelector('.zero-gamma-label')) {
                        const label = document.createElement('div');
                        label.className = 'zero-gamma-label';
                        label.textContent = "FLIP";
                        row.appendChild(label);
                    }
                } else if (!isGammaFlip) {
                    const label = row.querySelector('.zero-gamma-label');
                    if (label) label.remove();
                }

                // Update Magnet/Trigger emojis for max GEX strikes
                const strikeLabel = row.querySelector('.gamma-strike');
                if (strikeLabel) {
                    const magnetPrefix = '🧲 ';
                    const triggerPrefix = '🚀 ';
                    const currentText = strikeLabel.textContent;
                    const hasMagnet = currentText.startsWith(magnetPrefix);
                    const hasTrigger = currentText.startsWith(triggerPrefix);
                    const baseStrike = strikeData.strike.toFixed(1);

                    // Determine what prefix should be shown (priority: Magnet > Trigger)
                    let newPrefix = '';
                    let newClass = '';
                    if (isMagnet) {
                        newPrefix = magnetPrefix;
                        newClass = 'magnet-strike';
                    } else if (isTrigger) {
                        newPrefix = triggerPrefix;
                        newClass = 'trigger-strike';
                    }

                    // Update if changed
                    const hasAnyPrefix = hasMagnet || hasTrigger;
                    if (newPrefix && !currentText.startsWith(newPrefix)) {
                        strikeLabel.textContent = newPrefix + baseStrike;
                        strikeLabel.classList.remove('magnet-strike', 'trigger-strike', 'max-gex-strike');
                        strikeLabel.classList.add(newClass);
                    } else if (!newPrefix && hasAnyPrefix) {
                        strikeLabel.textContent = baseStrike;
                        strikeLabel.classList.remove('magnet-strike', 'trigger-strike', 'max-gex-strike');
                    }
                }

                // === Apply Max Wall Pulse ===
                // Update Max Wall styling
                if (isMaxPut) putBar.classList.add('gamma-max-wall');
                else putBar.classList.remove('gamma-max-wall');
                if (isMaxCall) callBar.classList.add('gamma-max-wall');
                else callBar.classList.remove('gamma-max-wall');

                // Re-append to maintain correct order (High → Low)
                gammaChartBars.appendChild(row);

                existingRows.delete(strikeData.strike);
            } else {
                // Create New
                row = document.createElement('div');
                row.className = 'gamma-row';
                row.dataset.strike = strikeData.strike;
                row.style.height = `${rowHeight}px`; // Apply Dynamic Height

                // Apply ATM (Current Price) styling - Blue indicator
                if (isATM) {
                    row.classList.add('atm-row');
                }

                // Apply Gamma Flip label (just text, no full row styling)
                if (isGammaFlip && !isATM) {
                    const label = document.createElement('div');
                    label.className = 'zero-gamma-label';
                    label.textContent = "FLIP";
                    row.appendChild(label);
                }

                // === Apply Max Wall Pulse (New Rows) ===
                const putClass = isMaxPut ? 'gamma-bar-put gamma-max-wall' : 'gamma-bar-put';
                const callClass = isMaxCall ? 'gamma-bar-call gamma-max-wall' : 'gamma-bar-call';

                const putVolLabel = putWidth >= 5 ? `<span class="gamma-vol-label put-label">${formatVol(strikeData.put_vol)}</span>` : '';
                const callVolLabel = callWidth >= 5 ? `<span class="gamma-vol-label call-label">${formatVol(strikeData.call_vol)}</span>` : '';

                // Add Magnet (🧲) or Trigger (🚀) emoji based on GEX polarity
                let strikeDisplay = strikeData.strike.toFixed(1);
                let strikeClass = 'gamma-strike';
                if (isMagnet) {
                    strikeDisplay = `🧲 ${strikeData.strike.toFixed(1)}`;
                    strikeClass = 'gamma-strike magnet-strike';
                } else if (isTrigger) {
                    strikeDisplay = `🚀 ${strikeData.strike.toFixed(1)}`;
                    strikeClass = 'gamma-strike trigger-strike';
                }

                row.innerHTML = `
                    <div class="gamma-put-side">
                        ${putVolLabel}
                        <div class="${putClass}" style="width: 0%"></div>
                    </div>
                    <div class="${strikeClass}">${strikeDisplay}</div>
                    <div class="gamma-call-side">
                        <div class="${callClass}" style="width: 0%"></div>
                        ${callVolLabel}
                    </div>
                `;

                // Re-attach event listeners (simplified)
                const putBar = row.querySelector('.gamma-bar-put');
                const callBar = row.querySelector('.gamma-bar-call');

                // Trigger growth animation
                requestAnimationFrame(() => {
                    requestAnimationFrame(() => {
                        putBar.style.width = `${putWidth}%`;
                        callBar.style.width = `${callWidth}%`;
                    });
                });

                putBar.onmouseenter = (e) => showTooltip(e, strikeData, 'PUT', gammaTooltip);
                putBar.onmousemove = (e) => moveTooltip(e, gammaTooltip);
                putBar.onmouseleave = () => hideTooltip(gammaTooltip);
                callBar.onmouseenter = (e) => showTooltip(e, strikeData, 'CALL', gammaTooltip);
                callBar.onmousemove = (e) => moveTooltip(e, gammaTooltip);
                callBar.onmouseleave = () => hideTooltip(gammaTooltip);

                // Mobile touch support - position relative to tapped element
                putBar.ontouchstart = (e) => {
                    e.preventDefault();
                    showTooltip(e, strikeData, 'PUT', gammaTooltip);
                    // Position tooltip relative to the tapped bar element
                    const rect = putBar.getBoundingClientRect();
                    positionTooltipNearElement(rect, gammaTooltip);
                };
                putBar.ontouchend = () => hideTooltip(gammaTooltip);

                callBar.ontouchstart = (e) => {
                    e.preventDefault();
                    showTooltip(e, strikeData, 'CALL', gammaTooltip);
                    // Position tooltip relative to the tapped bar element
                    const rect = callBar.getBoundingClientRect();
                    positionTooltipNearElement(rect, gammaTooltip);
                };
                callBar.ontouchend = () => hideTooltip(gammaTooltip);

                gammaChartBars.appendChild(row);
            }
        });

        existingRows.forEach((row) => row.remove());

        // Always scroll to center the ATM (current price) row
        // Use explicit scroll calculation with RETRY mechanism for reliability
        let attempts = 0;
        const centerATM = () => {
            const currentRow = gammaChartBars.querySelector('.atm-row');
            if (currentRow && gammaChartBars && gammaChartBars.scrollHeight > 0) {
                // Calculate scroll position to center the ATM row
                const containerHeight = gammaChartBars.clientHeight;
                const rowTop = currentRow.offsetTop;
                const rowHeight = currentRow.offsetHeight;

                // Center calculation: rowTop - (half container) + (half row)
                const scrollTarget = rowTop - (containerHeight / 2) + (rowHeight / 2);

                gammaChartBars.scrollTo({
                    top: Math.max(0, scrollTarget),
                    behavior: 'smooth'
                });
                console.log(`[Gamma] Centered ATM row at strike ${currentRow.dataset.strike} (pos: ${scrollTarget.toFixed(0)})`);
            } else if (attempts < 5) {
                // Retry if not ready yet (up to 5 times)
                attempts++;
                setTimeout(centerATM, 300); // Retry every 300ms
            }
        };

        // Start trying to center
        setTimeout(centerATM, 100);
    }

    function showTooltip(e, data, type, tooltip) {
        const vol = type === 'CALL' ? data.call_vol : data.put_vol;
        const oi = type === 'CALL' ? data.call_oi : data.put_oi;
        const netGex = data.net_gex || 0;  // Use net GEX (industry standard)
        const color = type === 'CALL' ? 'var(--bullish-color)' : 'var(--bearish-color)';

        // Use actual premium from Polygon API (or fallback to estimate)
        const premium = type === 'CALL' ? (data.call_premium || 0) : (data.put_premium || 0);
        const avgPremium = premium > 0 ? premium : (Math.abs(data.strike - (window.lastGammaPrice || data.strike)) * 0.3 + 2);
        const notional = vol * 100 * avgPremium;

        // Format as currency (supports K, M, B)
        const formatMoney = (val) => {
            if (Math.abs(val) >= 1000000000) return '$' + (val / 1000000000).toFixed(1) + 'B';
            if (Math.abs(val) >= 1000000) return '$' + (val / 1000000).toFixed(1) + 'M';
            if (Math.abs(val) >= 1000) return '$' + (val / 1000).toFixed(0) + 'K';
            return '$' + val.toFixed(0);
        };

        // Net GEX color: green for positive (bullish support), red for negative (bearish pressure)
        const gexColor = netGex >= 0 ? '#00d97e' : '#ff4757';
        const gexSign = netGex >= 0 ? '+' : '';
        const gexDisplay = netGex !== 0 ? `
            <div class="tooltip-row">
                <span class="tooltip-label">🧲 NET GEX:</span>
                <span class="tooltip-value" style="color: ${gexColor}">${gexSign}${formatMoney(netGex)}</span>
            </div>
        ` : '';

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
            ${gexDisplay}
        `;

        tooltip.style.opacity = '1';
        moveTooltip(e, tooltip);
    }

    function moveTooltip(e, tooltip) {
        // Support both mouse and touch events
        let clientX, clientY;

        if (e.touches && e.touches.length > 0) {
            // Touch event
            clientX = e.touches[0].clientX;
            clientY = e.touches[0].clientY;
        } else if (e.changedTouches && e.changedTouches.length > 0) {
            // Touch end event
            clientX = e.changedTouches[0].clientX;
            clientY = e.changedTouches[0].clientY;
        } else {
            // Mouse event
            clientX = e.clientX;
            clientY = e.clientY;
        }

        // Position tooltip near the tap/click, but keep it on screen
        const tooltipWidth = tooltip.offsetWidth || 200;
        const tooltipHeight = tooltip.offsetHeight || 150;
        const screenWidth = window.innerWidth;
        const screenHeight = window.innerHeight;

        // Default offset from cursor/tap
        let x = clientX + 15;
        let y = clientY + 15;

        // Keep tooltip on screen (right edge)
        if (x + tooltipWidth > screenWidth - 10) {
            x = clientX - tooltipWidth - 15;
        }

        // Keep tooltip on screen (bottom edge)
        if (y + tooltipHeight > screenHeight - 10) {
            y = clientY - tooltipHeight - 15;
        }

        // Ensure tooltip doesn't go off left or top edge
        x = Math.max(10, x);
        y = Math.max(10, y);

        tooltip.style.left = `${x}px`;
        tooltip.style.top = `${y}px`;
    }

    // Position tooltip near an element (for mobile touch)
    function positionTooltipNearElement(rect, tooltip) {
        const tooltipWidth = tooltip.offsetWidth || 200;
        const tooltipHeight = tooltip.offsetHeight || 150;
        const screenWidth = window.innerWidth;
        const screenHeight = window.innerHeight;

        // Position tooltip above the element, centered horizontally
        let x = rect.left + (rect.width / 2) - (tooltipWidth / 2);
        let y = rect.top - tooltipHeight - 10;

        // If tooltip would go off the top, position below instead
        if (y < 10) {
            y = rect.bottom + 10;
        }

        // Keep on screen horizontally
        x = Math.max(10, Math.min(x, screenWidth - tooltipWidth - 10));

        // Keep on screen vertically
        y = Math.max(10, Math.min(y, screenHeight - tooltipHeight - 10));

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

        // Add SWEEP/DUMP pulse animation for aggressive trades
        // Pulse only applies to trades that will be tagged as SWEEP or DUMP
        const bid = flow.bid || 0;
        const ask = flow.ask || 0;
        const tradePrice = flow.lastPrice || 0;
        const notional = flow.notional_value || 0;
        const MIN_PULSE_PREMIUM = 500000;
        const isPut = flow.type === 'PUT';
        const isSold = flow.side === 'SELL';

        const wouldBeSweep = ask > 0 && tradePrice >= ask && notional >= MIN_PULSE_PREMIUM;
        const wouldBeDump = bid > 0 && tradePrice <= bid && notional >= MIN_PULSE_PREMIUM && isSold;

        if (wouldBeSweep || wouldBeDump) {
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

        // === SIMPLIFIED TAG LOGIC (Using Backend Hybrid Logic) ===
        // SWEEP: Calculated in backend (Trade >= Ask AND Vol > OI)
        const isSweep = flow.is_sweep === true;

        // DUMP: Removed as per user request
        const isDump = false;

        // Combine MEGA with SWEEP/DUMP when both apply
        const isMega = flow.is_mega_whale;

        // Calculate DTE for LOTTO logic
        let daysToExpiry = 30; // Default
        if (flow.expiry) {
            const expiryDate = new Date(flow.expiry);
            const now = new Date();
            const diffTime = expiryDate - now;
            daysToExpiry = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        }

        // LOTTO: High risk, short term (Delta < 0.20, DTE <= 7)
        // Must be meaningful size (already filtered by feed > $500k usually, but good to check)
        const delta = flow.delta || 0;
        const isLotto = Math.abs(delta) < 0.20 && daysToExpiry <= 7;

        // Priority 1: MEGA SWEEP (Very high premium + aggressive buy)
        if (isMega && isSweep) {
            colTag.innerHTML = `<span class="tag tag-mega-sweep pulse-mega">MEGA SWEEP</span>`;
        }
        // Priority 2: MEGA (Very high premium, not aggressive)
        else if (isMega) {
            colTag.innerHTML = `<span class="tag tag-mega">MEGA WHALE</span>`;
        }
        // Priority 3: LOTTO (High Risk / Short Term)
        else if (isLotto) {
            colTag.innerHTML = `<span class="tag tag-lotto">LOTTO 🎰</span>`;
        }
        // Priority 4: SWEEP (Aggressive Buy at Ask)
        else if (isSweep) {
            colTag.innerHTML = `<span class="tag tag-sweep pulse-sweep">SWEEP</span>`;
        }
        // Priority 5: Standard Direction (BULL/BEAR)
        else if (isCall) {
            colTag.innerHTML = `<span class="tag tag-bull">BULL</span>`;
        } else {
            colTag.innerHTML = `<span class="tag tag-bear">BEAR</span>`;
        }

        // Secondary Tag: ITM / OTM (Append if space allows or as a small badge)
        // We will append a small span for ITM/OTM if available
        if (flow.moneyness) {
            const moneySpan = document.createElement('span');
            moneySpan.textContent = flow.moneyness;

            if (flow.moneyness === 'ATM') {
                moneySpan.className = 'tag-atm';
            } else {
                moneySpan.className = flow.moneyness === 'ITM' ? 'tag-itm' : 'tag-otm';
            }

            // Insert before the main tag
            colTag.insertBefore(moneySpan, colTag.firstChild);
        }

        // Delta Bar (Restored Production Style)
        // delta is already declared above for LOTTO logic
        const deltaPercent = Math.min(Math.abs(delta * 100), 100);
        // Format: .65 instead of 0.65
        const deltaLabel = Math.abs(delta).toFixed(2).replace(/^0+/, '');

        const deltaWrapper = document.createElement('div');
        deltaWrapper.className = 'delta-wrapper';
        deltaWrapper.innerHTML = `
            <span class="delta-label">${deltaLabel}</span>
            <div class="delta-bar-mini">
                <div class="delta-bar-fill" style="width: ${deltaPercent}%;"></div>
            </div>
        `;

        colTag.insertBefore(deltaWrapper, colTag.firstChild);

        row.appendChild(colTicker);
        row.appendChild(colPremium);
        row.appendChild(colStrike);
        row.appendChild(colTag);

        // Store trade data on element for saving
        row._tradeData = flow;

        // === LONG-PRESS TO SAVE ===
        let pressTimer = null;
        let pressStart = 0;

        const startPress = (e) => {
            pressStart = Date.now();
            row.classList.add('pressing');

            pressTimer = setTimeout(async () => {
                // Long-press triggered (500ms)
                row.classList.remove('pressing');
                row.classList.add('saving');

                try {
                    const response = await fetch(`${API_BASE_URL}/api/whales/save`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(flow)
                    });

                    if (response.ok) {
                        row.classList.add('saved');
                        // Show saved toast
                        showToast(`💾 Saved ${flow.ticker} to watchlist`);
                    } else {
                        row.classList.remove('saving');
                        showToast(`❌ Failed to save trade`);
                    }
                } catch (err) {
                    row.classList.remove('saving');
                    console.error('Save failed:', err);
                }
            }, 500);
        };

        const endPress = () => {
            if (pressTimer) {
                clearTimeout(pressTimer);
                pressTimer = null;
            }
            row.classList.remove('pressing');
        };

        // Mouse events
        row.addEventListener('mousedown', startPress);
        row.addEventListener('mouseup', endPress);
        row.addEventListener('mouseleave', endPress);

        // Touch events (mobile)
        row.addEventListener('touchstart', startPress, { passive: true });
        row.addEventListener('touchend', endPress);
        row.addEventListener('touchcancel', endPress);

        return row;
    }

    // Toast notification helper
    function showToast(message) {
        let toast = document.getElementById('whale-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'whale-toast';
            toast.style.cssText = 'position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); background: #222; color: #fff; padding: 10px 20px; border-radius: 8px; font-size: 13px; z-index: 9999; opacity: 0; transition: opacity 0.3s;';
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        toast.style.opacity = '1';
        setTimeout(() => { toast.style.opacity = '0'; }, 2000);
    }

    // Start SSE Stream
    initWhaleStream();

    // === IMMEDIATE MARKET STATE CHECK ON PAGE LOAD ===
    // Render weekend/pre-market animation immediately (SSE can take 60s on weekends)

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

        // Filter for Last 12 Hours (43200 seconds)
        const now = new Date().getTime() / 1000;
        const last12Hours = now - 43200;

        const validNews = newsItems.filter(item => item.time >= last12Hours);


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
            trackEvent('app_error', { source: widgetName, message: error.message });
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
    const GAMMA_CACHE_VERSION = 2;  // Increment when sorting/logic changes

    function getGammaCache(ticker) {
        const key = `gamma_cache_v${GAMMA_CACHE_VERSION}_${ticker}`;
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
        const key = `gamma_cache_v${GAMMA_CACHE_VERSION}_${ticker}`;
        const payload = { timestamp: Date.now(), data };
        localStorage.setItem(key, JSON.stringify(payload));
    }



    // === ANALYTICS TRACKING FOR STATIC ELEMENTS ===
    const xBtn = document.getElementById('x-link-btn');
    if (xBtn) {
        xBtn.addEventListener('click', () => trackEvent('social_click', { platform: 'X' }));
    }



    const signOutBtn = document.getElementById('sign-out-btn');
    if (signOutBtn) {
        signOutBtn.addEventListener('click', () => trackEvent('sign_out'));
    }

    // Initial Fetch & Interval
    // === STAGGERED INITIALIZATION (Optimized for Performance) ===
    // Prevents "thundering herd" of API calls on load

    // 1. Polymarket (Fast) - Immediate
    setTimeout(() => safeExecute('Polymarket Init', fetchPolymarketData), 0);

    // 2. Movers Tape (Fast) - +50ms
    setTimeout(() => safeExecute('Ticker Tape', startMoversSlideshow), 50);

    // 3. News Feed (Medium) - +100ms
    setTimeout(() => safeExecute('News Feed', fetchNews), 100);
    setInterval(() => safeExecute('News Feed Update', fetchNews), 60000); // Every 1 minute

    // 4. CNN Fear & Greed (Medium) - +150ms
    setTimeout(() => safeExecute('CNN Fear/Greed', fetchCNNFearGreed), 150);

    // 5. Market Map (Medium) - +200ms
    setTimeout(() => safeExecute('Market Map', fetchHeatmapData), 200);

    // 6. Gamma Wall (Medium) - +250ms
    setTimeout(() => safeExecute('Gamma Wall', initGammaWall), 250);

    // 7. TradingView Widget (Heavy) - +500ms
    setTimeout(() => safeExecute('TradingView Main', () => createTradingViewWidget(currentTicker)), 500);

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

    // TFI Macro Update Loop (30 Minutes)
    // fetchVIX(); // Initial Render - DISABLED, using CNN Fear & Greed instead
    // setInterval(fetchVIX, 30 * 60 * 1000); // 30 Minutes - DISABLED

    // === ECONOMIC EVENT CALENDAR LOGIC ===
    // =====================================================================
    // MANUAL EVENTS - Edit this array to add/remove economic events
    // Format: { title, time, type, stars (1-3), rawDate: "YYYY-MM-DD" }
    //
    // AUTOMATIC LOGIC:
    // - Events < 9 days away: "Critical" state (Red segments + Urgent Flash)
    // - Events > 9 days away: "Standard" state (Green/Yellow segments + Flow Animation)
    // - Events past 24 hours ago are automatically hidden
    // =====================================================================
    const CRITICAL_THRESHOLD_DAYS = 9; // Events closer than this get the urgent flash

    const MANUAL_EVENTS = [
        // === JANUARY 2026 ===
        { title: "OBBBA STIMULUS IMPLEMENTATION", time: "12:00 AM ET", type: "GOV", stars: 3, rawDate: "2026-01-01" },
        { title: "JOBS REPORT (DEC 2025)", time: "8:30 AM ET", type: "LABOR", stars: 3, rawDate: "2026-01-09" },
        { title: "US CPI (DEC 2025)", time: "8:30 AM ET", type: "INFLATION", stars: 3, rawDate: "2026-01-13" },
        { title: "US RETAIL SALES (ADVANCE)", time: "8:30 AM ET", type: "CONSUMER", stars: 3, rawDate: "2026-01-14" },
        { title: "BOJ MONETARY POLICY MEETING", time: "11:00 PM ET", type: "CB", stars: 2, rawDate: "2026-01-22" },
        { title: "FOMC RATE DECISION", time: "2:00 PM ET", type: "FED", stars: 3, rawDate: "2026-01-28" },
        { title: "BOC RATE ANNOUNCEMENT", time: "10:00 AM ET", type: "CB", stars: 2, rawDate: "2026-01-28" },
        { title: "Q4 BIG TECH EARNINGS BEGIN", time: "4:00 PM ET", type: "EARNINGS", stars: 3, rawDate: "2026-01-28" },
        // === FEBRUARY 2026 ===
        { title: "ECB MONETARY POLICY MEETING", time: "8:15 AM ET", type: "CB", stars: 2, rawDate: "2026-02-05" },
        { title: "BOE MPC DECISION", time: "7:00 AM ET", type: "CB", stars: 2, rawDate: "2026-02-05" },
        { title: "JOBS REPORT (JAN 2026)", time: "8:30 AM ET", type: "LABOR", stars: 3, rawDate: "2026-02-06" },
        { title: "CHINA LUNAR NEW YEAR", time: "12:00 AM ET", type: "HOLIDAY", stars: 2, rawDate: "2026-02-17" },
        { title: "SUPREME COURT TARIFF RULINGS", time: "10:00 AM ET", type: "GOV", stars: 3, rawDate: "2026-02-15" },
    ];

    const economicCalendar = {
        events: [],

        countdownInterval: null,

        init: function () {
            this.cacheDOM();
            this.bindEvents();
            this.loadManualEvents(); // Load static events
            this.checkCriticalEvents();

            // Expose to window for global access (e.g. from index.html)
            window.economicCalendar = this;
        },

        loadManualEvents: function () {
            // Convert rawDate strings to Date objects
            this.events = MANUAL_EVENTS.map(event => ({
                ...event,
                rawDate: new Date(event.rawDate + 'T12:00:00')
            }));
            this.render();
        },

        addTrialAlert: function (daysRemaining) {
            if (daysRemaining > 3) return;

            // Check if already added to avoid duplicates
            if (this.events.some(e => e.title === "TRIAL EXPIRING")) return;

            const alertEvent = {
                title: "TRIAL EXPIRING",
                time: `IN ${daysRemaining} DAYS`,
                type: "SYSTEM ALERT",
                status: "ACTIVE",
                critical: true,
                stars: 3,
                rawDate: new Date(Date.now() + (daysRemaining * 86400000))
            };

            // Prepend to events
            this.events.unshift(alertEvent);
            this.render();
            console.log(`⚠️ Trial alert added to Critical Events: ${daysRemaining} days left`);
        },

        cacheDOM: function () {
            this.modal = document.getElementById('economic-calendar-modal');
            this.closeBtn = document.getElementById('close-calendar-btn');
            this.listContainer = document.getElementById('economic-event-list');
            this.dateElement = document.getElementById('date');
            this.countdownElement = document.getElementById('boss-countdown');
        },

        bindEvents: function () {
            if (this.closeBtn) {
                this.closeBtn.addEventListener('click', () => this.closeModal());
            }

            // Close on ESC
            document.addEventListener('keydown', (e) => {
                if (this.modal && !this.modal.classList.contains('hidden') && e.key === 'Escape') {
                    this.closeModal();
                }
            });

            // Close on overlay click
            if (this.modal) {
                const overlay = this.modal.querySelector('.modal-overlay');
                if (overlay) {
                    overlay.addEventListener('click', () => this.closeModal());
                }
            }

            // Open on Date Click
            if (this.dateElement) {
                this.dateElement.addEventListener('click', () => this.openModal());
            }
        },

        // 5-segment progress bar: 45-day range, 9 days per segment
        // Bar FILLS from LEFT (green) to RIGHT (red) as event gets CLOSER
        renderProgressBar: function (eventDate) {
            const now = new Date();
            const msPerDay = 24 * 60 * 60 * 1000;
            const daysUntil = Math.max(0, Math.ceil((eventDate - now) / msPerDay));

            // Calculate active segments (5 segments, 9 days each = 45 days total)
            // Closer = more segments filled (left to right)
            // 45+ days = 0, 36-44 = 1, 27-35 = 3, 18-26 = 3, 9-17 = 4, 0-8 = 5 (all filled)
            let activeSegments;
            if (daysUntil >= 45) {
                activeSegments = 0;  // Far away, nothing filled
            } else if (daysUntil >= 36) {
                activeSegments = 1;  // Green only
            } else if (daysUntil >= 27) {
                activeSegments = 2;  // Green + Light green
            } else if (daysUntil >= 18) {
                activeSegments = 3;  // + Yellow
            } else if (daysUntil >= CRITICAL_THRESHOLD_DAYS) {
                activeSegments = 4;  // + Orange
            } else {
                activeSegments = 5;  // All filled including red (critical!)
            }

            const isCritical = daysUntil < CRITICAL_THRESHOLD_DAYS;
            const barClass = isCritical ? 'critical' : 'flow';
            const segments = [
                { color: 'seg-green', index: 0 },
                { color: 'seg-light-green', index: 1 },
                { color: 'seg-yellow', index: 2 },
                { color: 'seg-orange', index: 3 },
                { color: 'seg-red', index: 4 }
            ];

            // Fill segments from LEFT to RIGHT as event approaches
            const segmentsHtml = segments.map((seg, i) => {
                const isActive = i < activeSegments;
                return `<div class="progress-segment ${seg.color} ${isActive ? 'active' : ''}"></div>`;
            }).join('');

            return `<div class="pixel-progress-bar ${barClass}">${segmentsHtml}</div>`;
        },

        render: function () {
            if (!this.listContainer) return;

            const now = new Date();
            const activeEvents = this.events.filter(event => {
                const eventTime = event.rawDate.getTime();
                // Filter out events that have passed (even by 1ms)
                return (eventTime - now.getTime()) > 0;
            });

            if (activeEvents.length === 0) {
                this.listContainer.innerHTML = '<div class="placeholder-item">NO UPCOMING EVENTS DETECTED...</div>';
                return;
            }

            this.listContainer.innerHTML = activeEvents.map((event, index) => {
                const isBoss = event.type === 'BOSS ENCOUNTER';
                const isCleared = event.status === 'CLEARED';

                let rowClass = '';
                if (isCleared) rowClass = 'level-cleared';
                else if (isBoss) rowClass = 'boss-encounter';

                const icon = isCleared ? '✅' : (isBoss ? '⚠️' : '📅');

                // Generate Stars
                const starCount = event.stars || 1;
                let starsHtml = '';
                for (let i = 0; i < 3; i++) {
                    const starClass = i < starCount ? 'pixel-star active' : 'pixel-star inactive';
                    starsHtml += `<span class="${starClass}"></span>`;
                }

                return `
                    <div class="event-row ${rowClass}" id="event-row-${index}">
                        <div class="event-status-icon">${icon}</div>
                        <div class="event-details">
                            <div class="event-header">
                                <span class="event-title">${event.title}</span>
                                <span class="difficulty-stars">${starsHtml}</span>
                                <span class="event-timer" data-index="${index}" data-time="${event.rawDate.toISOString()}">T-MINUS --:--:--</span>
                            </div>
                            <div class="event-meta">
                                <span class="event-time">${event.time}</span>
                                <span class="event-separator">|</span>
                                <span class="event-type">${event.type}</span>
                            </div>
                            <div class="event-progress-container">
                                ${this.renderProgressBar(event.rawDate)}
                            </div>
                        </div>
                    </div>
                `;
            }).join('');

            // Start individual timers
            this.startEventTimers();
        },

        startEventTimers: function () {
            if (this.countdownInterval) clearInterval(this.countdownInterval);

            this.updateEventTimers(); // Immediate update
            this.countdownInterval = setInterval(() => {
                this.updateEventTimers();
            }, 1000);
        },

        updateEventTimers: function () {
            const timerElements = this.listContainer.querySelectorAll('.event-timer');
            const now = new Date();

            timerElements.forEach(el => {
                const targetTime = new Date(el.dataset.time);
                const diff = targetTime - now;
                const index = el.dataset.index;
                const row = document.getElementById(`event-row-${index}`);
                const progressBar = row ? row.querySelector('.event-progress-bar') : null;

                // Progress bar: assume 7-day window (100% = event time, 0% = 7 days before)
                const WINDOW_MS = 7 * 24 * 60 * 60 * 1000; // 7 days in ms
                let progressPercent = 0;
                if (diff <= 0) {
                    progressPercent = 100;
                } else if (diff < WINDOW_MS) {
                    progressPercent = ((WINDOW_MS - diff) / WINDOW_MS) * 100;
                }

                if (progressBar) {
                    progressBar.style.width = `${Math.min(100, Math.max(0, progressPercent))}%`;
                    // Color based on urgency
                    if (diff <= 0) {
                        progressBar.className = 'event-progress-bar active';
                    } else if (diff < 60 * 60 * 1000) {
                        progressBar.className = 'event-progress-bar critical';
                    } else if (diff < 24 * 60 * 60 * 1000) {
                        progressBar.className = 'event-progress-bar urgent';
                    } else {
                        progressBar.className = 'event-progress-bar';
                    }
                }

                if (diff <= 0) {
                    el.textContent = ">>> ACTIVE <<<";
                    el.classList.add('blink-text');
                    if (row) row.classList.add('urgent-pulse');
                } else {
                    // Calculate time components
                    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
                    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                    const seconds = Math.floor((diff % (1000 * 60)) / 1000);

                    const hStr = String(hours).padStart(2, '0');
                    const mStr = String(minutes).padStart(2, '0');
                    const sStr = String(seconds).padStart(2, '0');

                    // Dynamic Formatting
                    if (days > 0) {
                        el.textContent = `${days}d ${hStr}:${mStr}:${sStr}`;
                    } else {
                        el.textContent = `${hStr}:${mStr}:${sStr}`;
                    }

                    el.classList.remove('blink-text');

                    // Critical Alert (< 60s)
                    if (diff < 60 * 1000) {
                        el.classList.add('critical-timer');
                        el.classList.remove('urgent-timer');
                        if (row) {
                            row.classList.add('critical-pulse');
                            row.classList.remove('urgent-pulse');
                        }
                    }
                    // Urgency Check (< 60 mins)
                    else if (diff < 60 * 60 * 1000) {
                        el.classList.add('urgent-timer');
                        el.classList.remove('critical-timer');
                        if (row) {
                            row.classList.add('urgent-pulse');
                            row.classList.remove('critical-pulse');
                        }
                    } else {
                        el.classList.remove('urgent-timer', 'critical-timer');
                        if (row) row.classList.remove('urgent-pulse', 'critical-pulse');
                    }
                }
            });
        },

        openModal: function () {
            if (this.modal) this.modal.classList.remove('hidden');
        },

        closeModal: function () {
            if (this.modal) this.modal.classList.add('hidden');
        },

        checkCriticalEvents: function () {
            // Always make date clickable with pulsing border
            if (this.dateElement) {
                this.dateElement.classList.add('critical-event');
                this.dateElement.title = "CLICK FOR ECONOMIC CALENDAR";
            }
        }
    };

    // Initialize Calendar
    economicCalendar.init();

});
