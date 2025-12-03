import os

# Render sets the PORT environment variable
port = os.environ.get("PORT", "10000")
bind = f"0.0.0.0:{port}"

def post_worker_init(worker):
    """
    Start background worker thread AFTER Gunicorn forks.
    This ensures the thread exists in the worker process, not the master.
    """
    from run import start_background_worker
    start_background_worker()
    print(f"✅ Background worker started in process {worker.pid}", flush=True)
