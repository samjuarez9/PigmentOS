#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🔍 RUNNING SAFETY CHECKS...${NC}"

# 1. Run Tests
if python3 -m unittest discover -p "test_*.py"; then
    echo -e "${GREEN}✅ Tests Passed!${NC}"
else
    echo -e "${RED}❌ Tests Failed! Fix errors before deploying.${NC}"
    exit 1
fi

# 2. Ask for Commit Message
echo ""
echo -e "${YELLOW}📝 Enter commit message (what did you change?):${NC}"
read -r commit_msg

if [ -z "$commit_msg" ]; then
    echo -e "${RED}❌ Commit message cannot be empty.${NC}"
    exit 1
fi

# 3. Deploy
echo ""
echo -e "${YELLOW}🚀 Deploying to GitHub...${NC}"
git add .
git commit -m "$commit_msg"
git push

echo ""
echo -e "${GREEN}✅ DEPLOYMENT COMPLETE!${NC}"
echo -e "Your changes are on their way to the cloud."
