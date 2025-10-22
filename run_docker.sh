#!/bin/bash

# Script để quản lý Docker container cho VPCP AutoTest
# Author: VPCP Team
# Usage: ./run_docker.sh [build|start|stop|restart|logs|clean]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Tạo các thư mục cần thiết nếu chưa có
create_directories() {
    print_info "Tạo các thư mục cần thiết..."
    mkdir -p test_results logs scheduled_tests prompts utils pages QAs output failed_tests .streamlit
    
    # Set permissions
    chmod -R 755 test_results logs scheduled_tests prompts utils pages QAs output failed_tests
    
    print_info "✅ Đã tạo các thư mục"
}

# Build Docker image
build_image() {
    print_info "Building Docker image..."
    docker-compose build
    print_info "✅ Build completed"
}

# Start containers
start_containers() {
    print_info "Starting containers..."
    create_directories
    docker-compose up -d
    print_info "✅ Containers started"
    print_info "🌐 Application is running at: http://localhost:8501"
}

# Stop containers
stop_containers() {
    print_info "Stopping containers..."
    docker-compose down
    print_info "✅ Containers stopped"
}

# Restart containers
restart_containers() {
    print_info "Restarting containers..."
    docker-compose restart
    print_info "✅ Containers restarted"
}

# Show logs
show_logs() {
    print_info "Showing logs (Ctrl+C to exit)..."
    docker-compose logs -f
}

# Clean up everything
clean_all() {
    print_warning "⚠️  This will remove all containers, images, and volumes!"
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "$confirm" = "yes" ]; then
        print_info "Cleaning up..."
        docker-compose down -v
        docker rmi vpcp_autotest-vpcp-streamlit 2>/dev/null || true
        print_info "✅ Cleanup completed"
    else
        print_info "Cleanup cancelled"
    fi
}

# Rebuild and restart (for development)
rebuild() {
    print_info "Rebuilding and restarting..."
    docker-compose down
    docker-compose build --no-cache
    docker-compose up -d
    print_info "✅ Rebuild completed"
    print_info "🌐 Application is running at: http://localhost:8501"
}

# Show container status
show_status() {
    print_info "Container status:"
    docker-compose ps
    echo ""
    print_info "Resource usage:"
    docker stats --no-stream vpcp-automation-test 2>/dev/null || print_warning "Container is not running"
}

# Execute command in container
exec_shell() {
    print_info "Opening shell in container..."
    docker-compose exec vpcp-streamlit /bin/bash
}

# Show help
show_help() {
    echo "VPCP AutoTest - Docker Management Script"
    echo ""
    echo "Usage: ./run_docker.sh [command]"
    echo ""
    echo "Commands:"
    echo "  build       Build Docker image"
    echo "  start       Start containers"
    echo "  stop        Stop containers"
    echo "  restart     Restart containers"
    echo "  logs        Show container logs"
    echo "  clean       Remove all containers and images"
    echo "  rebuild     Rebuild and restart (no cache)"
    echo "  status      Show container status and resource usage"
    echo "  shell       Open shell in container"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./run_docker.sh build"
    echo "  ./run_docker.sh start"
    echo "  ./run_docker.sh logs"
}

# Main script
case "$1" in
    build)
        build_image
        ;;
    start)
        start_containers
        ;;
    stop)
        stop_containers
        ;;
    restart)
        restart_containers
        ;;
    logs)
        show_logs
        ;;
    clean)
        clean_all
        ;;
    rebuild)
        rebuild
        ;;
    status)
        show_status
        ;;
    shell)
        exec_shell
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        if [ -z "$1" ]; then
            print_error "No command specified"
        else
            print_error "Unknown command: $1"
        fi
        echo ""
        show_help
        exit 1
        ;;
esac

exit 0
