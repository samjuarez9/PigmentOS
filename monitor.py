import time
import sys
import subprocess
import os

def get_file_mtime(path):
    try:
        return os.stat(path).st_mtime
    except OSError:
        return 0

def start_server():
    print("🚀 Starting Server...")
    # Use sys.executable to ensure we use the same python interpreter
    return subprocess.Popen([sys.executable, "run.py"])

def main():
    print("👀 Watching run.py for changes... (Ctrl+C to stop)")
    
    server_process = start_server()
    last_mtime = get_file_mtime("run.py")

    try:
        while True:
            time.sleep(1) # Check every second
            current_mtime = get_file_mtime("run.py")
            
            if current_mtime != last_mtime:
                print("\n🔄 Change detected! Restarting server...")
                server_process.terminate()
                server_process.wait() # Ensure it's dead
                server_process = start_server()
                last_mtime = current_mtime
                
    except KeyboardInterrupt:
        print("\n🛑 Stopping monitor.")
        server_process.terminate()

if __name__ == "__main__":
    if not os.path.exists("run.py"):
        print("❌ Error: run.py not found in this directory.")
    else:
        main()
