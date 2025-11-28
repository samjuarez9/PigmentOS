# ❖ PIGMENT OS
**Real-time Financial Intelligence Terminal**

PigmentOS is a high-performance, dark-mode market dashboard designed for traders who need speed and clarity. It aggregates live data from multiple sources into a single "glass-morphic" HUD.

## 🚀 Features
-   **Unusual Whales Tracker**: Real-time options flow monitoring for big money bets.
-   **Polymarket Odds**: Live probability feeds for global events (Fed rates, Elections).
-   **Trader Fear Index (TFI)**: Custom sentiment gauge based on VIX and market momentum.
-   **Live Price Action**: Sub-second updates for major tickers (NVDA, SPY, BTC).
-   **Market Wire**: AI-filtered news feed prioritizing "Breaking" and "Macro" events.

## 🛠️ Tech Stack
-   **Frontend**: Vanilla JS + CSS3 (No frameworks, pure speed).
-   **Backend**: Python (Flask) + Gunicorn.
-   **Data**: Yahoo Finance, Polymarket API, RSS Feeds.

## 📦 Installation
1.  Clone the repo:
    ```bash
    git clone https://github.com/YOUR_USERNAME/pigment-os.git
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run the server:
    ```bash
    ./start.sh
    ```

## ☁️ Deployment
Ready for production on **Render** or **Railway**.
See `deployment_workflow.md` for details.
