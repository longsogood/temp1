#!/bin/bash

# Script để build và chạy VPCP Automation Test với Docker

echo "🚀 Bắt đầu build và chạy VPCP Automation Test..."

# Kiểm tra xem Docker có được cài đặt không
if ! command -v docker &> /dev/null; then
    echo "❌ Docker chưa được cài đặt. Vui lòng cài đặt Docker trước."
    exit 1
fi

# Kiểm tra xem Docker Compose có được cài đặt không
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose chưa được cài đặt. Vui lòng cài đặt Docker Compose trước."
    exit 1
fi

# Tạo thư mục output nếu chưa có
mkdir -p output

echo "📦 Đang build Docker image..."
docker-compose build

if [ $? -eq 0 ]; then
    echo "✅ Build thành công!"
    echo "🌐 Đang khởi động container..."
    docker-compose up -d
    
    if [ $? -eq 0 ]; then
        echo "✅ Container đã được khởi động thành công!"
        echo "🔗 Ứng dụng có thể truy cập tại: http://localhost:8501"
        echo ""
        echo "📋 Các lệnh hữu ích:"
        echo "  - Xem logs: docker-compose logs -f"
        echo "  - Dừng container: docker-compose down"
        echo "  - Restart container: docker-compose restart"
        echo "  - Xem trạng thái: docker-compose ps"
    else
        echo "❌ Không thể khởi động container"
        exit 1
    fi
else
    echo "❌ Build thất bại"
    exit 1
fi 