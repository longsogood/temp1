#!/bin/bash

# Script để rebuild và restart Docker container sau khi cập nhật
# Sử dụng: ./rebuild_docker.sh [option]
# Options: 
#   --full    : Rebuild hoàn toàn không dùng cache (mặc định)
#   --quick   : Rebuild nhanh với cache
#   --restart : Chỉ restart container

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print with color
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Header
echo -e "${BLUE}"
echo "╔════════════════════════════════════════════╗"
echo "║   🐳 VPCP Docker Rebuild Script          ║"
echo "║   Cập nhật: Backup/Restore Prompts       ║"
echo "╚════════════════════════════════════════════╝"
echo -e "${NC}"

# Get option
OPTION="${1:---full}"

case $OPTION in
    --full)
        print_info "Chế độ: Rebuild HOÀN TOÀN (không cache)"
        print_warning "Quá trình này có thể mất vài phút..."
        echo ""
        
        # Stop container
        print_info "Bước 1/4: Dừng container hiện tại..."
        docker-compose down
        print_success "Container đã dừng"
        echo ""
        
        # Rebuild with no cache
        print_info "Bước 2/4: Rebuild image (không dùng cache)..."
        docker-compose build --no-cache
        print_success "Image đã được rebuild"
        echo ""
        
        # Start container
        print_info "Bước 3/4: Khởi động container..."
        docker-compose up -d
        print_success "Container đã khởi động"
        echo ""
        
        # Wait for health check
        print_info "Bước 4/4: Đợi container sẵn sàng (health check)..."
        sleep 5
        ;;
        
    --quick)
        print_info "Chế độ: Rebuild NHANH (có dùng cache)"
        echo ""
        
        # Stop container
        print_info "Bước 1/3: Dừng container..."
        docker-compose down
        print_success "Container đã dừng"
        echo ""
        
        # Rebuild with cache
        print_info "Bước 2/3: Rebuild image (dùng cache)..."
        docker-compose build
        print_success "Image đã được rebuild"
        echo ""
        
        # Start container
        print_info "Bước 3/3: Khởi động container..."
        docker-compose up -d
        print_success "Container đã khởi động"
        echo ""
        
        sleep 3
        ;;
        
    --restart)
        print_info "Chế độ: Chỉ RESTART container"
        echo ""
        
        print_info "Restarting container..."
        docker-compose restart
        print_success "Container đã restart"
        echo ""
        
        sleep 3
        ;;
        
    *)
        print_error "Option không hợp lệ: $OPTION"
        echo ""
        echo "Sử dụng:"
        echo "  ./rebuild_docker.sh --full     # Rebuild hoàn toàn (khuyến nghị)"
        echo "  ./rebuild_docker.sh --quick    # Rebuild nhanh"
        echo "  ./rebuild_docker.sh --restart  # Chỉ restart"
        exit 1
        ;;
esac

# Check status
print_info "Kiểm tra trạng thái container..."
echo ""
docker ps --filter "name=vpcp-automation-test" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

# Check health
print_info "Kiểm tra health endpoint..."
sleep 2
HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8501/_stcore/health || echo "000")

if [ "$HEALTH_CHECK" == "200" ]; then
    print_success "Health check OK!"
else
    print_warning "Health check chưa sẵn sàng (code: $HEALTH_CHECK)"
    print_info "Đợi thêm 10 giây..."
    sleep 10
    
    HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8501/_stcore/health || echo "000")
    if [ "$HEALTH_CHECK" == "200" ]; then
        print_success "Health check OK!"
    else
        print_warning "Health check vẫn chưa OK. Kiểm tra logs: docker-compose logs -f"
    fi
fi

echo ""
print_success "Hoàn tất! Ứng dụng đang chạy tại: http://localhost:8501"
echo ""

# Show logs option
read -p "Bạn có muốn xem logs không? (y/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Đang xem logs... (Ctrl+C để thoát)"
    docker-compose logs -f
fi

