# 🐳 VPCP AutoTest - Docker Setup Guide

Hướng dẫn sử dụng Docker để chạy VPCP AutoTest với đồng bộ dữ liệu 2 chiều giữa host và container.

## 📋 Mục lục

- [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
- [Cài đặt nhanh](#cài-đặt-nhanh)
- [Cấu trúc volumes](#cấu-trúc-volumes)
- [Quản lý Docker](#quản-lý-docker)
- [Troubleshooting](#troubleshooting)

## 🔧 Yêu cầu hệ thống

- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB RAM (khuyến nghị 8GB)
- 2 CPU cores (khuyến nghị 4 cores)
- 10GB ổ đĩa trống

## 🚀 Cài đặt nhanh

### 1. Clone repository (nếu chưa có)

```bash
git clone <repository-url>
cd VPCP_AutoTest
```

### 2. Tạo các thư mục cần thiết

```bash
mkdir -p test_results logs scheduled_tests prompts utils pages QAs output failed_tests .streamlit
```

### 3. Build và chạy container

```bash
# Sử dụng script quản lý
chmod +x run_docker.sh
./run_docker.sh build
./run_docker.sh start

# Hoặc sử dụng docker-compose trực tiếp
docker-compose build
docker-compose up -d
```

### 4. Truy cập ứng dụng

Mở trình duyệt và truy cập: **http://localhost:8501**

## 📁 Cấu trúc volumes

### Volume Mounts (Đồng bộ 2 chiều)

Tất cả các thư mục và file sau được mount từ host vào container, cho phép:
- ✅ Chỉnh sửa code trên host → Tự động cập nhật trong container
- ✅ Kết quả test trong container → Tự động lưu ra host
- ✅ Dữ liệu không bị mất khi restart container

```
Host (Local)              →  Container (/app)
─────────────────────────────────────────────
./pages                   →  /app/pages
./utils                   →  /app/utils
./prompts                 →  /app/prompts
./test_results            →  /app/test_results        (Kết quả test)
./logs                    →  /app/logs                (Log files)
./scheduled_tests         →  /app/scheduled_tests     (Scheduled jobs)
./QAs                     →  /app/QAs                 (Q&A datasets)
./output                  →  /app/output              (Output files)
./failed_tests            →  /app/failed_tests        (Failed tests)
./site_selector.py        →  /app/site_selector.py
./utils.py                →  /app/utils.py
./.streamlit              →  /app/.streamlit          (Streamlit config)
```

### Lợi ích của Volume Mounting

1. **🔄 Development Mode**: Sửa code trên host, container tự động reload
2. **💾 Data Persistence**: Dữ liệu không bị mất khi container restart
3. **📊 Real-time Sync**: Kết quả test xuất hiện ngay trên host
4. **🛠️ Easy Debugging**: Có thể xem logs và debug trực tiếp trên host

## 🎮 Quản lý Docker

### Sử dụng script `run_docker.sh`

```bash
# Build image
./run_docker.sh build

# Start containers
./run_docker.sh start

# Stop containers
./run_docker.sh stop

# Restart containers
./run_docker.sh restart

# Show logs (real-time)
./run_docker.sh logs

# Show container status
./run_docker.sh status

# Open shell in container
./run_docker.sh shell

# Rebuild (no cache)
./run_docker.sh rebuild

# Clean up everything
./run_docker.sh clean

# Show help
./run_docker.sh help
```

### Sử dụng Docker Compose trực tiếp

```bash
# Build image
docker-compose build

# Start containers (detached mode)
docker-compose up -d

# Stop containers
docker-compose down

# Restart containers
docker-compose restart

# Show logs
docker-compose logs -f

# Execute command in container
docker-compose exec vpcp-streamlit bash

# Show container status
docker-compose ps
```

## 📊 Giám sát và Debugging

### Xem logs

```bash
# Real-time logs
./run_docker.sh logs

# Hoặc
docker-compose logs -f vpcp-streamlit
```

### Kiểm tra status

```bash
./run_docker.sh status

# Hoặc
docker-compose ps
docker stats vpcp-automation-test
```

### Vào container để debug

```bash
./run_docker.sh shell

# Hoặc
docker-compose exec vpcp-streamlit bash
```

### Health check

Container có health check tự động:
- Interval: 30s
- Timeout: 10s
- Retries: 3

```bash
# Kiểm tra health status
docker inspect --format='{{.State.Health.Status}}' vpcp-automation-test
```

## 🔧 Troubleshooting

### Container không start

```bash
# Xem logs chi tiết
docker-compose logs vpcp-streamlit

# Rebuild image
./run_docker.sh rebuild
```

### Permission denied

```bash
# Trên Linux/Mac, set permissions cho thư mục
sudo chmod -R 755 test_results logs scheduled_tests

# Hoặc chạy với sudo
sudo ./run_docker.sh start
```

### Port 8501 đã được sử dụng

```bash
# Tìm process đang dùng port 8501
lsof -i :8501

# Hoặc thay đổi port trong docker-compose.yml
ports:
  - "8502:8501"  # Thay 8501 thành 8502
```

### Volume mount không hoạt động

Trên Windows với WSL2:
```bash
# Chuyển sang WSL2 backend
# Settings → General → Use WSL 2 based engine

# Hoặc sử dụng đường dẫn absolute
volumes:
  - /mnt/c/Users/nvlong8/Documents/agents/VPCP_AutoTest/test_results:/app/test_results
```

### Container bị crash

```bash
# Xem logs lỗi
docker-compose logs --tail=100 vpcp-streamlit

# Kiểm tra resource usage
docker stats vpcp-automation-test

# Tăng memory limit trong docker-compose.yml
deploy:
  resources:
    limits:
      memory: 8G  # Tăng từ 4G lên 8G
```

### Hot reload không hoạt động

```bash
# Restart container sau khi sửa code
./run_docker.sh restart

# Hoặc rebuild nếu cần
./run_docker.sh rebuild
```

## 🎯 Best Practices

### 1. Development Workflow

```bash
# 1. Start container
./run_docker.sh start

# 2. Sửa code trên host (VS Code, PyCharm, etc.)
# 3. Streamlit tự động reload trong container
# 4. Xem kết quả tại http://localhost:8501
```

### 2. Data Backup

```bash
# Backup test results
tar -czf backup_$(date +%Y%m%d).tar.gz test_results/ logs/ scheduled_tests/

# Restore
tar -xzf backup_20250101.tar.gz
```

### 3. Update Dependencies

```bash
# 1. Sửa requirements.txt
# 2. Rebuild container
./run_docker.sh rebuild
```

### 4. Clean Docker Resources

```bash
# Clean unused Docker resources
docker system prune -a

# Clean volumes (⚠️ cẩn thận, sẽ xóa data)
docker volume prune
```

## 📈 Resource Limits

Trong `docker-compose.yml`, có thể điều chỉnh resource limits:

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'      # Tối đa 2 CPU cores
      memory: 4G       # Tối đa 4GB RAM
    reservations:
      cpus: '1.0'      # Đảm bảo ít nhất 1 CPU core
      memory: 2G       # Đảm bảo ít nhất 2GB RAM
```

## 🔐 Security Notes

- Container chạy với user root (có thể thay đổi nếu cần)
- Các thư mục mount có permissions 755
- Health check endpoint: `http://localhost:8501/_stcore/health`
- CORS và XSRF protection đã tắt (cho development)

## 📚 Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Streamlit Documentation](https://docs.streamlit.io/)

## 🆘 Support

Nếu gặp vấn đề:
1. Kiểm tra logs: `./run_docker.sh logs`
2. Xem status: `./run_docker.sh status`
3. Rebuild container: `./run_docker.sh rebuild`
4. Liên hệ team support

---

**Happy Testing! 🚀**
