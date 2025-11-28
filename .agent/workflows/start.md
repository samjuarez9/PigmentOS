---
description: How to start PigmentOS dashboard
---

# Starting PigmentOS

## Quick Start

From the PigmentOS directory, run:

```bash
// turbo
./start.sh
```

This script will:
1. ✓ Check if backend server is already running
2. ✓ Start the server if needed (on port 8001)
3. ✓ Open the dashboard in your browser

## Manual Start

If you prefer to start components separately:

1. **Start the backend server:**
   ```bash
   python3 run.py
   ```

2. **Open the dashboard:**
   ```bash
   open index.html
   ```

## Health Check

To verify the server is running correctly:

```bash
// turbo
./check_server.sh
```

## Troubleshooting

**Dashboard shows "OFFLINE" status:**
- The backend server isn't running
- Run `./start.sh` to start it

**Server won't start (port already in use):**
```bash
# Find what's using port 8001
lsof -i :8001

# Kill the process
pkill -f "python3 run.py"

# Try starting again
./start.sh
```

**View server logs:**
```bash
tail -f server.log
```

## Stopping the Server

```bash
pkill -f "python3 run.py"
```
