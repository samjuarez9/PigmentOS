import os

# Render sets the PORT environment variable
port = os.environ.get("PORT", "10000")
bind = f"0.0.0.0:{port}"

# CRITICAL: Use gevent worker to match gevent.monkey.patch_all() in run.py
# gthread + gevent monkey patching causes Python 3.13 threading KeyError
worker_class = "gevent"
workers = 2  # 2 workers for better concurrency
timeout = 120  # Increase timeout to 2 minutes for heavy hydration

def post_worker_init(worker):
    """
    Start background worker thread AFTER Gunicorn forks.
    This ensures the thread exists in the worker process, not the master.
    """
    try:
        from run import start_background_worker
        start_background_worker()
        print(f"✅ Background worker started in process {worker.pid}", flush=True)
    except Exception as e:
        print(f"⚠️ Background worker failed to start: {e}", flush=True)
        # Don't crash the entire worker - it can still serve requests

