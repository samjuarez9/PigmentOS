// app.js

document.addEventListener('DOMContentLoaded', () => {
    console.log('✅ JavaScript is loading and DOMContentLoaded fired!');

    // Configuration
    const IS_FILE_PROTOCOL = window.location.protocol === 'file:';
    const API_BASE_URL = IS_FILE_PROTOCOL ? 'http://localhost:8001' : '';
    const threatBox = document.getElementById('threat-box');
    const threatLevelSpan = document.getElementById('threat-level');
    const optionsBody = document.getElementById('options-body');
    const insiderList = document.getElementById('insider-list');
    const oddsList = document.getElementById('odds-list');
    const alertsList = document.getElementById('alerts-list');
    const priceTicker = document.getElementById('price-ticker');
    const gaugeValue = document.querySelector('.gauge-value');
    const gaugeLabel = document.querySelector('.gauge-label');
    const tickerSelect = document.getElementById('ticker-select');
    const chartHeader = document.querySelector('#live-price-action h2');

    // Global State
    let currentTicker = 'QQQ'; // Default to QQQ
    let tvWidget = null;

    // TradingView Widget Integration
    function createTradingViewWidget(ticker) {
        // Clear container first
        const container = document.getElementById('chart-container');
        if (container) container.innerHTML = '';

        new TradingView.widget({
            "autosize": true,
            "symbol": "NASDAQ:" + ticker,
            "interval": "5",
            "timezone": "Etc/UTC",
            "theme": "dark",
            "style": "1",
            "locale": "en",
            "enable_publishing": false,
            "backgroundColor": "#0C0C18", // Deep Cosmos Background
            "gridColor": "rgba(30, 144, 255, 0.1)", // Subtle Deep Sky Blue grid
            "hide_top_toolbar": false,
            "container_id": "chart-container" // Ensure this matches your HTML ID
        });

        // Mark chart as live
        updateStatus('status-chart', true);
    }

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
    const dropdownContainer = document.getElementById('ticker-dropdown');
    const dropdownSelected = document.getElementById('dropdown-selected');
    const dropdownOptions = document.getElementById('dropdown-options');
    const selectedTickerText = document.getElementById('selected-ticker-text');

    // Populate Dropdown Options
    if (dropdownOptions && WATCHLIST_TICKERS) {
        WATCHLIST_TICKERS.forEach(ticker => {
            const option = document.createElement('div');
            option.className = 'dropdown-option';
            option.textContent = ticker;
            option.dataset.value = ticker;

            option.addEventListener('click', () => {
                // Update selection
                if (selectedTickerText) {
                    selectedTickerText.textContent = ticker;
                }
                currentTicker = ticker;

                // Update Chart
                createTradingViewWidget(ticker);

                // Close dropdown
                if (dropdownContainer) {
                    dropdownContainer.classList.remove('open');
                }
            });

            dropdownOptions.appendChild(option);
        });
    }

    // Toggle Dropdown on Click
    if (dropdownSelected) {
        dropdownSelected.addEventListener('click', (e) => {
            e.stopPropagation();
            if (dropdownContainer) {
                dropdownContainer.classList.toggle('open');
            }
        });
    }

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (dropdownContainer && !dropdownContainer.contains(e.target)) {
            dropdownContainer.classList.remove('open');
        }
    });

    // Helper to clear container
    function clear(element) {
        element.innerHTML = '';
    }

    // Initialize TFI
    updateTFI(50, 'Neutral'); // Default neutral

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


    // Render Polymarket Odds
    function renderPolymarket(data) {
        console.log('renderPolymarket called with:', data);
        const container = document.getElementById('polymarket-container');
        if (!container) {
            console.error('polymarket-container not found!');
            return;
        }

        container.innerHTML = ''; // Clear previous

        data.forEach(market => {
            const item = document.createElement('div');
            item.className = 'polymarket-item';

            // Delta Logic
            let deltaBadge = '';
            if (market.delta && Math.abs(market.delta) >= 0.01) {
                const deltaPercent = Math.round(market.delta * 100);
                const isPositive = deltaPercent > 0;
                const deltaClass = isPositive ? 'delta-up' : 'delta-down';
                const sign = isPositive ? '+' : '';
                deltaBadge = `<span class="${deltaClass}">${sign}${deltaPercent}%</span>`;
                console.log('Delta badge created:', deltaBadge, 'for', market.event);
            }

            // Calculate width for laser gauge
            const prob1 = market.outcome_1_prob || 0;
            const prob2 = market.outcome_2_prob || 0;
            const total = prob1 + prob2 || 100; // Avoid divide by zero
            const width1 = (prob1 / total) * 100;
            const width2 = (prob2 / total) * 100;

            // Determine labels - STRICTLY YES/NO as requested
            const label1 = 'YES';
            const label2 = 'NO';

            item.innerHTML = `
                <div class="polymarket-top-row">
                    <a href="https://polymarket.com/event/${market.slug}" target="_blank" class="polymarket-event">${market.event}</a>
                    <div class="polymarket-odds">
                        <span class="polymarket-odds-text polymarket-odds-yes">${prob1}% ${label1}${deltaBadge}</span>
                        <span class="polymarket-odds-text polymarket-odds-no">${prob2}% ${label2}</span>
                    </div>
                </div>
                <div class="polymarket-laser-gauge">
                    <div class="polymarket-yes-segment" style="width: ${width1}%"></div>
                    <div class="polymarket-no-segment" style="width: ${width2}%"></div>
                </div>
            `;
            container.appendChild(item);
        });
        console.log('Rendered', data.length, 'Polymarket items');
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
            console.log('Polymarket response received:', responseData);

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
    let moversData = [];
    let showGainers = true;
    let moversInterval = null;

    async function fetchMoversData() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/movers`);
            if (!response.ok) throw new Error('Movers API Failed');
            moversData = await response.json();
            console.log('Movers Data:', moversData);
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
        const gainers = moversData.filter(m => m.type === 'gain');
        const losers = moversData.filter(m => m.type === 'loss');

        // Select set to display
        const currentSet = showGainers ? gainers : losers;
        const label = showGainers ? 'TOP GAINERS' : 'TOP LOSERS';
        const labelClass = showGainers ? 'mover-gain' : 'mover-loss';

        // Build HTML
        const itemsHtml = currentSet.map(m => {
            const colorClass = m.type === 'gain' ? 'mover-gain' : 'mover-loss';
            const arrow = m.type === 'gain' ? '▲' : '▼';
            const changeStr = m.change > 0 ? `+${m.change}%` : `${m.change}%`;
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

    // Start Slideshow
    function startMoversSlideshow() {
        fetchMoversData(); // Initial fetch

        // Update data every 60s
        setInterval(fetchMoversData, 60000);

        // Switch slides every 15s
        setInterval(updateMoversTape, 15000);
    }

    // FRED API & TFI Logic
    const FRED_API_KEY = "YOUR_FRED_API_KEY"; // Placeholder

    // News Feed Logic
    const newsFeedContainer = document.getElementById('news-items-list');
    const MAX_NEWS_ITEMS = 50;

    function createNewsItem(item) {
        const div = document.createElement('div');
        div.className = 'news-item news-item-slide-in';

        // Highlight Logic
        const upperTitle = item.title.toUpperCase();
        const upperTicker = (item.ticker || '').toUpperCase();

        if (upperTitle.includes('MAG 7') ||
            upperTitle.includes('TRUMP') ||
            upperTicker === 'TRUMP' ||
            upperTitle.includes('NVDA') || upperTitle.includes('NVIDIA') ||
            upperTitle.includes('TSLA') || upperTitle.includes('TESLA') ||
            upperTitle.includes('AAPL') || upperTitle.includes('APPLE') ||
            upperTitle.includes('MSFT') || upperTitle.includes('MICROSOFT') ||
            upperTitle.includes('META') || upperTitle.includes('FACEBOOK') ||
            upperTitle.includes('GOOGL') || upperTitle.includes('GOOGLE') ||
            upperTitle.includes('AMZN') || upperTitle.includes('AMAZON') ||
            upperTitle.includes('JOB') ||
            upperTitle.includes('LABOR') ||
            upperTitle.includes('JOBLESS') ||
            upperTitle.includes('EMPLOYMENT') ||
            upperTitle.includes('UNEMPLOYMENT') ||
            upperTitle.includes(' AI ') ||
            upperTitle.includes('ARTIFICIAL INTELLIGENCE')) {
            div.classList.add('news-highlight-mag7');
        }

        // Format Time
        const date = new Date(item.time * 1000);
        const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        // Source Color Logic
        let sourceColor = '#EAEAEA';
        const pub = item.publisher.toLowerCase();
        if (pub.includes('techcrunch')) sourceColor = '#00FF00';
        else if (pub.includes('verge')) sourceColor = '#EAEAEA';
        else if (pub.includes('cnbc')) sourceColor = '#00AACC';
        else if (pub.includes('reuters')) sourceColor = '#FF8800';
        else if (pub.includes('bloomberg')) sourceColor = '#0077FF';
        else if (pub.includes('breaking')) sourceColor = '#FF3333';

        div.innerHTML = `
            <div class="news-meta">
                <span class="news-source-tag" style="color: ${sourceColor}">${item.publisher}</span>
                <span class="news-time">${timeStr}</span>
            </div>
            <div class="news-headline"><a href="${item.link}" target="_blank" style="color: inherit; text-decoration: none;">${item.title}</a></div>
        `;

        return div;
    }

    async function fetchNews() {
        try {
            const response = await fetch(`${API_BASE_URL}/api/news`);
            if (!response.ok) throw new Error('News API Error');

            const newsItems = await response.json();

            // Empty news doesn't mean offline - API still responded successfully
            if (!newsItems || newsItems.length === 0) {
                updateStatus('status-news', true); // Still LIVE, just no items
                return;
            }

            // Clear current list if it's a full refresh (or handle merging)
            // For simplicity, let's clear and re-render if it's the first load, 
            // or intelligently prepend new items.
            // Since the API returns the full sorted list, we can just re-render 
            // or check for new IDs.

            // Let's use a Set to track seen links to avoid duplicates
            // We need to define seenNewsLinks outside this function scope if we want it to persist
            // But for now, let's just render the top 50.

            newsFeedContainer.innerHTML = '';

            newsItems.forEach((item, index) => {
                const newsEl = createNewsItem(item);
                // Only animate the first few on initial load, or all if they are new?
                // If we clear innerHTML, everything animates. 
                // To avoid massive animation storm, maybe only animate top 5.
                if (index > 5) newsEl.classList.remove('news-item-slide-in');

                newsFeedContainer.appendChild(newsEl);
            });

            // Set status to LIVE after successful render
            updateStatus('status-news', true);

        } catch (error) {
            console.error('News Fetch Error:', error);
            updateStatus('status-news', false);
        }
    }

    // Initial Fetch and Interval
    fetchNews();
    setInterval(fetchNews, 60000); // Refresh every 60 seconds

    async function fetchVIX() {
        try {
            // Fetch from our backend proxy (protects API key)
            const response = await fetch(`${API_BASE_URL}/api/vix`);

            if (!response.ok) throw new Error("VIX API Error");

            const data = await response.json();
            // FRED returns data.observations[0].value
            const vixValue = parseFloat(data.observations[0].value);

            const value = data.value || 50;
            const rating = data.rating || 'Neutral';

            updateTFI(value, rating);
            updateStatus('status-tfi', true);
        } catch (err) {
            console.warn('CNN Fear & Greed API Failed:', err);
            updateStatus('status-tfi', false);
        }
    }

    function updateTFI(value, rating) {
        console.log('updateTFI START - value:', value, 'rating:', rating);
        // Configuration
        const IS_FILE_PROTOCOL = window.location.protocol === 'file:';
        const API_BASE_URL = IS_FILE_PROTOCOL ? 'http://localhost:8001' : '';

        // DOM Elements
        // DOM Elements
        const timeDisplay = document.getElementById('time-display');
        // const tfiText = document.getElementById('tfi-text'); // REMOVED - element does not exist
        const tfiSegmentsContainer = document.getElementById('tfi-segments');
        const tfiContainer = document.querySelector('.tfi-container');

        console.log('tfiSegmentsContainer found:', !!tfiSegmentsContainer);
        console.log('tfiContainer found:', !!tfiContainer);

        if (!tfiSegmentsContainer) {
            console.error('TFI elements not found!');
            return;
        }

        // Update text
        const tfiScore = document.getElementById('tfi-score');
        const tfiRating = document.getElementById('tfi-rating');

        if (tfiScore && tfiRating) {
            tfiScore.textContent = Math.round(value);
            tfiRating.textContent = rating.toUpperCase();
            tfiRating.style.color = ""; // Reset color
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
            console.log('Added class: tfi-extreme-fear');
        } else if (value < 45) {
            tfiContainer.classList.add('tfi-red');
            console.log('Added class: tfi-red');
        } else if (value > 75) {
            tfiContainer.classList.add('tfi-extreme-greed');
            console.log('Added class: tfi-extreme-greed');
        } else if (value > 55) {
            tfiContainer.classList.add('tfi-green');
            console.log('Added class: tfi-green');
        } else {
            tfiContainer.classList.add('tfi-yellow');
            console.log('Added class: tfi-yellow');
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
        console.log('updateTFI COMPLETE - activeCount:', activeCount);
    }

    // Initialize TFI
    async function fetchCNNFearGreed() {
        try {
            console.log('Fetching CNN Fear & Greed...');
            const response = await fetch(`${API_BASE_URL}/api/cnn-fear-greed`);
            if (!response.ok) throw new Error('CNN Fear & Greed API Failed');

            const data = await response.json();
            console.log('CNN Fear & Greed data received:', data);
            console.log('Value:', data.value, 'Rating:', data.rating);
            updateTFI(data.value, data.rating);
            console.log('updateTFI called with:', data.value, data.rating);
            updateStatus('status-tfi', true);
        } catch (error) {
            console.error('CNN Fear & Greed API Failed:', error);
            updateStatus('status-tfi', false);
        }
    }
    fetchCNNFearGreed();
    setInterval(fetchCNNFearGreed, 300000); // Refresh every 5 minutes (was 12 hours)

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
            console.log(`Whale API returned ${json.data.length} trades`);

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

            console.log(`Mapped to ${trades.length} trade objects`, trades[0]);
            return trades;
        } catch (err) {
            console.warn("Whale API Failed:", err);
            updateStatus('status-whales', false); // Status: DOWN
            return []; // Return empty array on error
        }
    }

    // REMOVED: generateMockWhaleData() - Strict Real Data Policy

    // Check if US market is open (9:30 AM - 4:00 PM ET, Mon-Fri)
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
        // Get current time in ET
        const now = new Date();
        const etTimeStr = now.toLocaleString("en-US", { timeZone: "America/New_York" });
        const etTime = new Date(etTimeStr);

        const hours = etTime.getHours();
        const minutes = etTime.getMinutes();
        const seconds = etTime.getSeconds();
        const currentMinutes = hours * 60 + minutes;

        const marketOpenMinutes = 9 * 60 + 30; // 9:30 AM
        const marketCloseMinutes = 16 * 60; // 4:00 PM

        return {
            isPreMarket: currentMinutes < marketOpenMinutes,
            isMarketHours: currentMinutes >= marketOpenMinutes && currentMinutes < marketCloseMinutes,
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
            console.log(`⏰ Market opens in ${Math.round(msUntilOpen / 1000 / 60)} minutes. Scheduling auto-refresh...`);

            // Set precise timeout for market open
            marketOpenTimeout = setTimeout(() => {
                console.log('🔔 MARKET OPEN - Transitioning to live feed');
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

        // Handle empty data
        if (!hasData) {
            // Clear existing items
            flowFeedContainer.innerHTML = '';

            if (isSystemHealthy) {
                const marketState = getMarketState();

                if (marketState.isPreMarket) {
                    // PRE-MARKET: Show pulsing radar rings
                    flowFeedContainer.innerHTML = `
                        <div class="whale-pre-market-container">
                            <div class="radar-container">
                                <div class="radar-ring radar-ring-1"></div>
                                <div class="radar-ring radar-ring-2"></div>
                                <div class="radar-ring radar-ring-3"></div>
                                <div class="radar-center"></div>
                            </div>
                            <div class="status-message">
                                <span style="color: #888; font-size: 11px; font-family: var(--font-mono);">STATUS: PRE-MARKET. Monitoring for block orders...</span>
                            </div>
                        </div>
                    `;
                } else {
                    // MARKET HOURS or AFTER HOURS: Show waiting message
                    const waitingDiv = document.createElement('div');
                    waitingDiv.className = 'placeholder-item';
                    waitingDiv.textContent = 'Waiting for trade...';
                    flowFeedContainer.appendChild(waitingDiv);
                }
            }
            // If system is unhealthy (stale), the OFFLINE indicator already shows, so leave empty
            return;
        }

        // Map to internal format
        const trades = data.map(item => ({
            ticker: item.baseSymbol || item.symbol,
            strike: item.strikePrice,
            type: item.putCall === 'C' ? 'CALL' : 'PUT',
            expiry: item.expirationDate,
            premium: item.premium || "DELAYED",
            volume: item.volume,
            direction: item.putCall === 'C' ? 'BULL' : 'BEAR',
            isWhale: true,
            isCritical: false,
            vol_oi: item.vol_oi,
            moneyness: item.moneyness,
            is_mega_whale: item.is_mega_whale || false,
            notional_value: item.notional_value || 0,
            delta: item.delta,
            iv: item.iv
        }));

        renderWhaleFeed(trades);
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
            pendingWhales = [...trades, ...pendingWhales]; // Newest first
            // Limit buffer
            if (pendingWhales.length > 50) pendingWhales = pendingWhales.slice(0, 50);
            return;
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
            const id = `${flow.ticker}_${flow.strike}_${flow.type}_${flow.expiry}_${flow.volume}`;
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
        if (seenTrades.size > 1000) {
            seenTrades.clear(); // Simple clear, or we could be smarter
        }
    }

    // Helper: Create flow element (New Grid Layout)
    function createFlowElement(flow, tradeId) {
        const row = document.createElement('div');
        row.className = 'whale-row new-row';

        // Check if trade is NEW (within 10 minutes)
        const firstSeenTime = tradeFirstSeen.get(tradeId);
        const isNew = firstSeenTime && (Date.now() - firstSeenTime < NEW_BADGE_DURATION);

        // 1. Ticker Column with NEW badge
        const colTicker = document.createElement('div');
        colTicker.className = 'col-ticker';

        if (isNew) {
            // Add NEW badge before ticker
            const newBadge = document.createElement('span');
            newBadge.className = 'whale-new-badge';
            newBadge.textContent = 'NEW';
            colTicker.appendChild(newBadge);
            colTicker.appendChild(document.createTextNode(' '));
        }

        const tickerSpan = document.createElement('span');
        tickerSpan.textContent = flow.ticker;
        colTicker.appendChild(tickerSpan);

        // 2. Premium Column
        const colPremium = document.createElement('div');
        colPremium.className = 'col-premium';
        colPremium.textContent = flow.premium;

        // 3. Strike/Type Column
        const colStrike = document.createElement('div');
        colStrike.className = 'col-strike';
        // flow.type is 'CALL' or 'PUT'
        const isCall = flow.type === 'CALL';
        const typeClass = isCall ? 'type-c' : 'type-p';
        const typeLabel = isCall ? 'C' : 'P';
        colStrike.innerHTML = `<span class="${typeClass}">${flow.strike}${typeLabel}</span>`;

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

    // === PCR Chart - Real TradingView Widget ===
    // === PCR Chart - Real TradingView Widget ===
    // === PCR Chart - Real TradingView Widget ===
    function initPCRChart() {
        const container = document.getElementById('pcr-chart-container');
        if (!container) return;

        container.innerHTML = ''; // Clear previous

        // Check if TradingView is loaded
        if (typeof TradingView === 'undefined') {
            console.log('TradingView not loaded yet, retrying...');
            setTimeout(initPCRChart, 1000);
            return;
        }

        // Create TradingView widget for P/C Ratio with 5min interval and baseline
        new TradingView.widget({
            "autosize": true,
            "symbol": "USI:PCCE",  // CBOE Equity Put/Call Ratio
            "interval": "5",  // 5-minute candles for visual movement
            "timezone": "America/New_York",
            "theme": "dark",
            "style": "10", // Baseline chart type
            "locale": "en",
            "toolbar_bg": "#f1f3f6",
            "enable_publishing": false,
            "hide_top_toolbar": false,
            "hide_legend": true,
            "save_image": false,
            "container_id": "pcr-chart-container",
            "studies": [],
            "overrides": {
                "mainSeriesProperties.style": 10, // Baseline style
                "mainSeriesProperties.showPriceLine": false,
                // Baseline configuration
                "mainSeriesProperties.baselineStyle.baseLevelPercentage": 50,
                "mainSeriesProperties.baselineStyle.topFillColor1": "rgba(0, 255, 65, 0.28)",
                "mainSeriesProperties.baselineStyle.topFillColor2": "rgba(0, 255, 65, 0.05)",
                "mainSeriesProperties.baselineStyle.bottomFillColor1": "rgba(255, 0, 0, 0.28)",
                "mainSeriesProperties.baselineStyle.bottomFillColor2": "rgba(255, 0, 0, 0.05)",
                "mainSeriesProperties.baselineStyle.topLineColor": "#00FF41",
                "mainSeriesProperties.baselineStyle.bottomLineColor": "#FF0000",
                "mainSeriesProperties.baselineStyle.topLineWidth": 2,
                "mainSeriesProperties.baselineStyle.bottomLineWidth": 2,
                "mainSeriesProperties.baselineStyle.baselineColor": "rgba(200, 200, 200, 0.4)",
                "mainSeriesProperties.baselineStyle.baselineWidth": 1,
                "paneProperties.background": "#000000",
                "paneProperties.vertGridProperties.color": "#1a1a1a",
                "paneProperties.horzGridProperties.color": "#1a1a1a",
                "scalesProperties.textColor": "#666666"
            }
        });

        updateStatus('status-pcr', true);
    }


    // === News Feed Logic ===
    let seenNews = new Set();

    function renderNews(newsItems) {
        const container = document.getElementById('news-items-list');
        if (!container) return;

        // container.innerHTML = ''; // Don't clear, we append now

        // Filter for Last 24 Hours (86400 seconds)
        const now = new Date().getTime() / 1000;
        const last24Hours = now - 86400;

        const todaysNews = newsItems.filter(item => item.time >= last24Hours);

        // Filter out seen items
        const newItems = todaysNews.filter(item => {
            const id = item.link || item.title;
            if (seenNews.has(id)) return false;
            seenNews.add(id);
            return true;
        });

        if (newItems.length === 0) {
            // No new items
            return;
        }

        // Sort new items by time (Oldest -> Newest) so when we prepend them one by one,
        // the newest ends up at the very top.
        newItems.sort((a, b) => a.time - b.time);

        newItems.forEach(item => {
            // Determine Sentiment Class for Ticker
            let tickerClass = 'stream-ticker';
            if (item.sentiment === 'BULLISH') tickerClass += ' bullish';
            if (item.sentiment === 'BEARISH') tickerClass += ' bearish';

            // Create Link Element (Row is the link)
            const row = document.createElement('a');
            let rowClass = 'stream-row news-slide-in'; // Add animation class

            // Apply pulsing border if it's a related ticker (and not just generic 'MKT' or 'ALERT')
            // Logic: Check for Mag 7 or Trump (Tickers OR Full Names)
            const mag7Tickers = ["NVDA", "TSLA", "AAPL", "MSFT", "META", "GOOGL", "AMZN"];
            const mag7Names = ["nvidia", "tesla", "apple", "microsoft", "meta", "google", "amazon", "alphabet"];

            const titleLower = item.title ? item.title.toLowerCase() : "";

            const isMag7Ticker = mag7Tickers.includes(item.ticker);
            const isMag7Name = mag7Names.some(name => titleLower.includes(name));
            const isMag7 = isMag7Ticker || isMag7Name;

            const isTrump = item.ticker === "TRUMP" || titleLower.includes("trump");

            if (isMag7 || isTrump) {
                rowClass += ' watchlist-alert';
            }

            row.className = rowClass;
            row.href = item.link;
            row.target = "_blank";

            // Format Time
            const date = new Date(item.time * 1000);
            const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

            // Ticker Display (Use Ticker if avail, else 'MKT')
            const tickerText = item.ticker ? item.ticker : 'MKT';

            // Source Display (Shorten if needed)
            let source = item.publisher || 'WIRE';
            if (source.includes('Investing.com')) source = 'INV';
            if (source.includes('CNBC')) source = 'CNBC';
            if (source.includes('Breaking News')) source = 'BRK';

            row.innerHTML = `
                <span class="stream-time">${timeStr}</span>
                <span class="stream-source">${source}</span>
                <span class="${tickerClass}">${tickerText}</span>
                <span class="stream-headline">${item.title}</span>
            `;

            // Prepend to container
            container.insertBefore(row, container.firstChild);
        });

        // Prune list to 50 items
        while (container.children.length > 50) {
            container.removeChild(container.lastChild);
        }
    }

    // === UTILITY: Safe Execution Wrapper ===
    function safeExecute(widgetName, fn) {
        try {
            fn();
        } catch (error) {
            console.error(`[CRITICAL] ${widgetName} Crashed:`, error);
            // Optional: Update UI to show "OFFLINE" for this specific widget?
        }
    }

    // Initial Fetch & Interval
    safeExecute('News Feed', fetchNews);
    setInterval(() => safeExecute('News Feed Update', fetchNews), 300000); // Every 5 minutes

    safeExecute('PCR Chart', initPCRChart);

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
