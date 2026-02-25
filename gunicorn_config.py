import os

# Signal to run.py that we're running under gunicorn (enable gevent patching)
os.environ['GUNICORN_WORKER'] = '1'

# Render sets the PORT environment variable
port = os.environ.get("PORT", "10000")
bind = f"0.0.0.0:{port}"

# CRITICAL: Use gevent worker to match gevent.monkey.patch_all() in run.py
# gthread + gevent monkey patching causes Python 3.13 threading KeyError
worker_class = "gevent"
workers = 4  # 4 workers for Pro plan - better concurrency
timeout = 300  # Increase timeout to 5 minutes for heavy hydration

# NOTE (2026-01-28): Investigated WORKER TIMEOUT (pid:65) and 195+ second response times.
# Root cause: yfinance + gevent can cause thread deadlocks during hydration.
# Applied fixes: Increased workers 2→4, added 10s startup delay in run_fixed.py.
# Future consideration: Replace yfinance with Polygon/Finnhub for all endpoints if issue recurs.

def post_fork(server, worker):
    """
    Start background worker AFTER Gunicorn forks (gevent compatible).
    post_worker_init doesn't work with gevent workers - must use post_fork.
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    try:
        from run import start_background_worker
        start_background_worker()
        print(f"✅ Background worker started in process {worker.pid}", flush=True)
    except Exception as e:
        print(f"⚠️ Background worker failed to start: {e}", flush=True)
        import traceback
        traceback.print_exc()

