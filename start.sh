#!/bin/bash
# PigmentOS Startup Script
# Ensures backend server is running and opens dashboard

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}     PIGMENT OS - Startup Sequence${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Navigate to script directory
cd "$(dirname "$0")"

# Load environment variables from .env file if it exists
if [ -f ".env" ]; then
    echo -e "${YELLOW}Loading environment from .env...${NC}"
    set -a
    source .env
    set +a
fi

# Check if server is already running
PORT="${PORT:-8001}"
echo -e "${YELLOW}[1/3]${NC} Checking server status on port $PORT..."
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    PID=$(lsof -Pi :$PORT -sTCP:LISTEN -t)
    echo -e "${YELLOW}⚠${NC} Port $PORT is busy (PID: $PID). Cleaning up..."
    kill -9 $PID
    sleep 1
    echo -e "${GREEN}✓${NC} Cleanup complete."
fi

echo -e "${YELLOW}[2/3]${NC} Starting backend server..."

# Start server in background and redirect output to log file
PYTHON_CMD="python3"
if [ -f ".venv/bin/python" ]; then
    PYTHON_CMD=".venv/bin/python"
fi
nohup $PYTHON_CMD run.py > server.log 2>&1 &
SERVER_PID=$!

# Wait for server to start (max 5 seconds)
echo -n "     Waiting for server startup"
for i in {1..10}; do
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}✓${NC} Server started successfully (PID: $SERVER_PID)"
        break
    fi
    echo -n "."
    sleep 0.5
done

# Verify server is actually running
if ! lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo ""
    echo -e "${RED}✗${NC} Server failed to start. Check server.log for details."
    exit 1
fi

# Open dashboard in browser
echo -e "${YELLOW}[3/3]${NC} Opening dashboard..."
DASHBOARD_PATH="http://localhost:$PORT/index.html"

# Detect OS and open browser
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    open "$DASHBOARD_PATH"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    xdg-open "$DASHBOARD_PATH" 2>/dev/null || firefox "$DASHBOARD_PATH" || google-chrome "$DASHBOARD_PATH"
else
    echo -e "${YELLOW}⚠${NC} Unknown OS. Please open: $DASHBOARD_PATH"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}     Dashboard Ready!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "Dashboard: ${BLUE}$DASHBOARD_PATH${NC}"
echo -e "Server:    ${BLUE}http://localhost:$PORT${NC}"
echo -e "Logs:      ${BLUE}$(pwd)/server.log${NC}"
echo ""
echo -e "To stop the server: ${YELLOW}pkill -f 'python3 run.py'${NC}"
echo ""
