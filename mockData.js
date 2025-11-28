// mockData.js

const mockData = {
    alerts: [],
    options: [],
    odds: [],
    insider: [],
    threatLevel: "NORMAL",
    prices: [],
    chartHistory: [], // Initial history
    chartUpdate: null // Latest candle update
};

const TICKERS = ['SPY', 'QQQ', 'NVDA', 'TSLA', 'AMD', 'MSFT', 'GOOGL', 'AMZN', 'META'];
const SIDES = ["CALL", "PUT"];
const NEWS_HEADLINES = [
    "large block buy detected",
    "volatility rising",
    "insider activity reported",
    "breaking resistance levels",
    "unusual options activity",
    "dark pool print detected",
    "sentiment shifting positive",
    "sentiment shifting negative",
    "earnings surprise expected",
    "regulatory news pending"
];

const INSIDERS = ["CEO", "CFO", "Director", "VP", "10% Owner"];
const THREAT_LEVELS = ["NORMAL", "ELEVATED", "CRITICAL"];

// Chart Data State
let lastClose = 100;
let lastTime = Math.floor(Date.now() / 1000) - 1000; // Start 1000 seconds ago for history

function getRandomInt(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

function getRandomItem(arr) {
    return arr[Math.floor(Math.random() * arr.length)];
}

function generateAlert() {
    const ticker = getRandomItem(TICKERS);
    const headline = getRandomItem(NEWS_HEADLINES);
    return {
        id: Date.now(),
        time: new Date().toLocaleTimeString(),
        message: `${ticker} ${headline}`,
        isNew: true
    };
}

function generateOptionTrade() {
    const ticker = getRandomItem(TICKERS);
    const side = getRandomItem(SIDES);
    const price = (Math.random() * 500).toFixed(2);
    const volume = getRandomInt(10, 1000);
    const expiration = new Date(Date.now() + getRandomInt(1, 30) * 24 * 60 * 60 * 1000).toLocaleDateString();

    return {
        ticker,
        side,
        price,
        volume,
        expiration
    };
}

function generateInsiderTrade() {
    const ticker = getRandomItem(TICKERS);
    const person = getRandomItem(INSIDERS);
    const type = Math.random() > 0.5 ? "BUY" : "SELL";
    const value = (Math.random() * 10 + 0.1).toFixed(1) + "M";
    return {
        ticker,
        person,
        type,
        value,
        date: new Date().toLocaleDateString()
    };
}

function generateOdds() {
    const events = [
        "Fed Rate Hike",
        "Recession 2025",
        "Bitcoin > 100k",
        "Oil > $100",
        "Gold ATH"
    ];

    return events.map(event => {
        const yes = getRandomInt(1, 99);
        return {
            event,
            yes,
            no: 100 - yes
        };
    });
}

function generateCandle(time) {
    const open = lastClose;
    const close = open + (Math.random() - 0.5) * 2;
    const high = Math.max(open, close) + Math.random();
    const low = Math.min(open, close) - Math.random();

    lastClose = close;

    return {
        time: time,
        open: parseFloat(open.toFixed(2)),
        high: parseFloat(high.toFixed(2)),
        low: parseFloat(low.toFixed(2)),
        close: parseFloat(close.toFixed(2))
    };
}

function updateData() {
    // Update Alerts
    if (Math.random() > 0.5) {
        const newAlert = generateAlert();
        mockData.alerts.unshift(newAlert);
        if (mockData.alerts.length > 10) mockData.alerts.pop();
    }

    // Update Options
    if (Math.random() > 0.3) {
        const newOption = generateOptionTrade();
        mockData.options.unshift(newOption);
        if (mockData.options.length > 10) mockData.options.pop();
    }

    // Update Insider
    if (Math.random() > 0.7) {
        const newInsider = generateInsiderTrade();
        mockData.insider.unshift(newInsider);
        if (mockData.insider.length > 5) mockData.insider.pop();
    }

    // Update Odds
    if (Math.random() > 0.8) {
        mockData.odds = generateOdds();
    }

    // Update Threat Level
    if (Math.random() > 0.95) {
        mockData.threatLevel = getRandomItem(THREAT_LEVELS);
    }

    // Update Prices
    mockData.prices = TICKERS.map(t => ({
        ticker: t,
        price: (Math.random() * 1000).toFixed(2),
        change: (Math.random() * 10 - 5).toFixed(2)
    }));

    // Update Chart Data (New Candle)
    lastTime += 1; // Increment time by 1 second
    mockData.chartUpdate = generateCandle(lastTime);
}

function startDataStream(callback) {
    // Initial population
    for (let i = 0; i < 10; i++) mockData.alerts.push(generateAlert());
    for (let i = 0; i < 10; i++) mockData.options.push(generateOptionTrade());
    for (let i = 0; i < 5; i++) mockData.insider.push(generateInsiderTrade());
    mockData.odds = generateOdds();

    // Generate Chart History (100 points)
    const history = [];
    for (let i = 0; i < 100; i++) {
        lastTime += 1;
        history.push(generateCandle(lastTime));
    }
    mockData.chartHistory = history;

    // Send initial data immediately
    callback(mockData);

    setInterval(() => {
        updateData();
        callback(mockData);
    }, 1000);
}

// Export for browser usage
window.mockDataService = {
    startDataStream
};
