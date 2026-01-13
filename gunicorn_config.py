import os

# Signal to run.py that we're running under gunicorn (enable gevent patching)
os.environ['GUNICORN_WORKER'] = '1'

# Render sets the PORT environment variable
port = os.environ.get("PORT", "10000")
bind = f"0.0.0.0:{port}"

# CRITICAL: Use gevent worker to match gevent.monkey.patch_all() in run.py
# gthread + gevent monkey patching causes Python 3.13 threading KeyError
worker_class = "gevent"
workers = 2  # 2 workers for better concurrency
timeout = 120  # Increase timeout to 2 minutes for heavy hydration

def post_fork(server, worker):
    """
    Start background worker AFTER Gunicorn forks (gevent compatible).
    post_worker_init doesn't work with gevent workers - must use post_fork.
    """
    try:
        from run import start_background_worker
        start_background_worker()
        print(f"✅ Background worker started in process {worker.pid}", flush=True)
    except Exception as e:
        print(f"⚠️ Background worker failed to start: {e}", flush=True)
        import traceback
        traceback.print_exc()

