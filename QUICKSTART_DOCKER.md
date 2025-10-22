# 🚀 Quick Start - Docker

Hướng dẫn nhanh để chạy VPCP AutoTest với Docker.

## ⚡ 3 Bước để bắt đầu

### 1️⃣ Build Docker Image

```bash
./run_docker.sh build
```

### 2️⃣ Start Container

```bash
./run_docker.sh start
```

### 3️⃣ Truy cập ứng dụng

Mở trình duyệt: **http://localhost:8501**

---

## 🎯 Các lệnh thường dùng

```bash
# Xem logs real-time
./run_docker.sh logs

# Stop container
./run_docker.sh stop

# Restart container  
./run_docker.sh restart

# Kiểm tra status
./run_docker.sh status

# Xem tất cả lệnh
./run_docker.sh help
```

---

## 📁 Đồng bộ dữ liệu

**Mọi thay đổi được tự động đồng bộ 2 chiều:**

✅ **Code trên host** → Tự động cập nhật trong container  
✅ **Kết quả test trong container** → Tự động lưu ra host  
✅ **Logs trong container** → Tự động xuất ra host  

### Các thư mục được đồng bộ:

- `./test_results` - Kết quả test
- `./logs` - Log files
- `./scheduled_tests` - Scheduled jobs
- `./pages` - Streamlit pages
- `./utils` - Utility functions
- `./prompts` - Prompts cho LLM
- `./QAs` - Q&A datasets

---

## 🔧 Development Workflow

```bash
# 1. Start container
./run_docker.sh start

# 2. Sửa code trên máy local (VS Code, PyCharm, etc.)
#    → Code tự động sync vào container
#    → Streamlit tự động reload

# 3. Xem kết quả tại http://localhost:8501

# 4. Kết quả test tự động lưu ra ./test_results
```

---

## ✅ Test Setup

Kiểm tra xem Docker đã setup đúng chưa:

```bash
./test_docker_setup.sh
```

---

## 🆘 Troubleshooting

### Container không start?

```bash
# Xem logs lỗi
./run_docker.sh logs

# Rebuild image
./run_docker.sh rebuild
```

### Port 8501 bị chiếm?

```bash
# Tìm process đang dùng port
lsof -i :8501

# Hoặc đổi port trong docker-compose.yml
ports:
  - "8502:8501"
```

### Permission denied?

```bash
# Linux/Mac
sudo chmod -R 755 test_results logs scheduled_tests

# Windows WSL2
# Chuyển sang WSL 2 backend trong Docker Desktop
```

---

## 📚 Xem thêm

Chi tiết đầy đủ: [README_Docker.md](README_Docker.md)

---

**Happy Testing! 🎉**

