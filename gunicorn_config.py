import os

# Render sets the PORT environment variable
port = os.environ.get("PORT", "10000")
bind = f"0.0.0.0:{port}"
workers = 2  # 2 workers for better concurrency (requires 2GB+ RAM)
timeout = 120  # Increase timeout to 2 minutes for heavy hydration

def post_worker_init(worker):
    """
    Start background worker thread AFTER Gunicorn forks.
    This ensures the thread exists in the worker process, not the master.
    """
    from run import start_background_worker
    start_background_worker()
    print(f"✅ Background worker started in process {worker.pid}", flush=True)
