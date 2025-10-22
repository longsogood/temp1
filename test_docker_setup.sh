#!/bin/bash

# Script để test Docker setup
# Kiểm tra xem tất cả volumes có được mount đúng không

echo "🧪 Testing Docker Volume Mounts..."
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if container is running
if ! docker ps | grep -q vpcp-automation-test; then
    echo -e "${RED}❌ Container is not running${NC}"
    echo "Please start container first: ./run_docker.sh start"
    exit 1
fi

echo -e "${GREEN}✅ Container is running${NC}"
echo ""

# Test volume mounts
echo "📁 Testing volume mounts..."
echo ""

test_mount() {
    local host_path=$1
    local container_path=$2
    local description=$3
    
    if docker exec vpcp-automation-test test -e "$container_path"; then
        echo -e "${GREEN}✅${NC} $description: $host_path → $container_path"
    else
        echo -e "${RED}❌${NC} $description: $host_path → $container_path"
    fi
}

# Test directories
test_mount "./pages" "/app/pages" "Pages directory"
test_mount "./utils" "/app/utils" "Utils directory"
test_mount "./prompts" "/app/prompts" "Prompts directory"
test_mount "./test_results" "/app/test_results" "Test results directory"
test_mount "./logs" "/app/logs" "Logs directory"
test_mount "./scheduled_tests" "/app/scheduled_tests" "Scheduled tests directory"

echo ""
echo "📄 Testing file mounts..."
echo ""

test_mount "./site_selector.py" "/app/site_selector.py" "Site selector file"
test_mount "./utils.py" "/app/utils.py" "Utils file"

echo ""
echo "🔍 Testing write permissions..."
echo ""

# Test write to test_results
if docker exec vpcp-automation-test touch /app/test_results/.test_write 2>/dev/null; then
    if [ -f "./test_results/.test_write" ]; then
        echo -e "${GREEN}✅${NC} Can write to test_results (found on host)"
        rm -f ./test_results/.test_write
        docker exec vpcp-automation-test rm -f /app/test_results/.test_write 2>/dev/null
    else
        echo -e "${YELLOW}⚠️${NC} Can write to container but file not on host"
    fi
else
    echo -e "${RED}❌${NC} Cannot write to test_results"
fi

# Test write to logs
if docker exec vpcp-automation-test touch /app/logs/.test_write 2>/dev/null; then
    if [ -f "./logs/.test_write" ]; then
        echo -e "${GREEN}✅${NC} Can write to logs (found on host)"
        rm -f ./logs/.test_write
        docker exec vpcp-automation-test rm -f /app/logs/.test_write 2>/dev/null
    else
        echo -e "${YELLOW}⚠️${NC} Can write to container but file not on host"
    fi
else
    echo -e "${RED}❌${NC} Cannot write to logs"
fi

echo ""
echo "🌐 Testing Streamlit..."
echo ""

# Test Streamlit health
if curl -f http://localhost:8501/_stcore/health >/dev/null 2>&1; then
    echo -e "${GREEN}✅${NC} Streamlit is healthy and responding"
else
    echo -e "${RED}❌${NC} Streamlit health check failed"
fi

echo ""
echo "📊 Container resource usage:"
echo ""
docker stats vpcp-automation-test --no-stream

echo ""
echo -e "${GREEN}✅ Docker setup test completed!${NC}"
echo ""
echo "🌐 Access the application at: http://localhost:8501"

