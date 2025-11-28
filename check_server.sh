#!/bin/bash
# Quick health check for PigmentOS backend server

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Checking PigmentOS server health..."
echo ""

# Check if port 8001 is listening
if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    PID=$(lsof -Pi :8001 -sTCP:LISTEN -t)
    echo -e "${GREEN}✓ Server is running${NC}"
    echo -e "  PID: $PID"
    echo -e "  Port: 8001"
    
    # Try to fetch data from API
    echo ""
    echo "Testing API endpoints..."
    
    if curl -s --max-time 2 http://localhost:8001/api/cnn-fear-greed > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} /api/cnn-fear-greed"
    else
        echo -e "  ${YELLOW}⚠${NC} /api/cnn-fear-greed (timeout or error)"
    fi
    
    if curl -s --max-time 2 http://localhost:8001/api/news > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} /api/news"
    else
        echo -e "  ${YELLOW}⚠${NC} /api/news (timeout or error)"
    fi
    
    echo ""
    echo -e "${GREEN}Status: HEALTHY${NC}"
    exit 0
else
    echo -e "${RED}✗ Server is not running${NC}"
    echo ""
    echo "To start the server, run:"
    echo "  ./start.sh"
    echo ""
    echo -e "${RED}Status: OFFLINE${NC}"
    exit 1
fi
