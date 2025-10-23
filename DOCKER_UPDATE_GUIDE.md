# 🐳 Hướng dẫn cập nhật Docker sau khi thêm tính năng Backup/Restore

## 📝 Tóm tắt thay đổi

Các file Docker đã được cập nhật để hỗ trợ tính năng mới:
- ✅ Backup/Restore prompts và extract sections
- ✅ Thư mục `original_prompts` cho template mặc định
- ✅ Thư mục `backup_prompts` cho việc backup
- ✅ Package `schedule` cho chức năng lập lịch

## 🔧 Các file đã được cập nhật

### 1. `Dockerfile`
- ➕ Thêm thư mục `/app/original_prompts`
- ➕ Thêm thư mục `/app/backup_prompts`
- ✅ Set permissions cho 2 thư mục mới

### 2. `docker-compose.yml`
- ➕ Mount `./original_prompts:/app/original_prompts`
- ➕ Mount `./backup_prompts:/app/backup_prompts`
- ➕ Mount `./original_site.py:/app/original_site.py`

### 3. `requirements.txt`
- ➕ Thêm `schedule>=1.2.0` cho chức năng lập lịch test

### 4. `.gitignore`
- 📝 Thêm comment cho `backup_prompts/` (mặc định vẫn commit)

## 🚀 Cách rebuild và restart Docker

### Option 1: Rebuild hoàn toàn (Khuyến nghị)

```bash
# Dừng container hiện tại
docker-compose down

# Rebuild image với các thay đổi mới
docker-compose build --no-cache

# Khởi động lại
docker-compose up -d

# Xem logs để kiểm tra
docker-compose logs -f
```

### Option 2: Rebuild nhanh (Không build lại toàn bộ)

```bash
# Dừng container
docker-compose down

# Rebuild với cache
docker-compose build

# Khởi động
docker-compose up -d
```

### Option 3: Chỉ restart (Nếu chỉ thay đổi code, không thay đổi dependencies)

```bash
docker-compose restart
```

## ✅ Kiểm tra sau khi cập nhật

### 1. Kiểm tra container đang chạy
```bash
docker ps
```

Kết quả mong đợi:
```
CONTAINER ID   IMAGE              STATUS         PORTS                    NAMES
xxxxx          vpcp-streamlit     Up 2 minutes   0.0.0.0:8501->8501/tcp   vpcp-automation-test
```

### 2. Kiểm tra logs
```bash
docker-compose logs -f vpcp-streamlit
```

### 3. Kiểm tra các thư mục được mount
```bash
docker exec vpcp-automation-test ls -la /app | grep prompts
```

Kết quả mong đợi:
```
drwxrwxrwx  2 root root 4096 ... original_prompts
drwxrwxrwx  2 root root 4096 ... backup_prompts
drwxrwxrwx  2 root root 4096 ... prompts
```

### 4. Truy cập ứng dụng
Mở trình duyệt: http://localhost:8501

Kiểm tra:
- ✅ Tab "Quản lý Prompts" có đầy đủ 3 nút: 💾 Lưu, 📦 Backup, 🔄 Reset
- ✅ Preview Extract Sections hiển thị mapping
- ✅ Có thể lưu và backup prompts

## 🐛 Troubleshooting

### Lỗi: Container không khởi động được
```bash
# Xem logs chi tiết
docker-compose logs vpcp-streamlit

# Kiểm tra ports
netstat -an | grep 8501
```

### Lỗi: Module 'schedule' not found
```bash
# Rebuild lại image với --no-cache
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Lỗi: Permission denied khi ghi file
```bash
# Kiểm tra permissions trong container
docker exec vpcp-automation-test ls -la /app/original_prompts
docker exec vpcp-automation-test ls -la /app/backup_prompts

# Nếu cần, fix permissions
docker exec vpcp-automation-test chmod -R 777 /app/original_prompts
docker exec vpcp-automation-test chmod -R 777 /app/backup_prompts
```

### Lỗi: Thư mục không tồn tại trên host
```bash
# Tạo các thư mục cần thiết trên host
mkdir -p original_prompts backup_prompts

# Copy file template vào original_prompts
# (đã có sẵn từ trước)
```

## 📦 Backup dữ liệu trước khi update

**Quan trọng:** Nên backup các thư mục sau trước khi rebuild:

```bash
# Backup toàn bộ data
tar -czf backup_$(date +%Y%m%d_%H%M%S).tar.gz \
  prompts/ \
  original_prompts/ \
  backup_prompts/ \
  test_results/ \
  scheduled_tests/

# Hoặc chỉ backup prompts
cp -r prompts/ prompts_backup_$(date +%Y%m%d_%H%M%S)
cp -r original_prompts/ original_prompts_backup_$(date +%Y%m%d_%H%M%S)
```

## 🎯 Workflow sau khi update

1. **Tạo site mới:**
   - Copy `original_site.py` → `pages/MySite.py`
   - Đổi `SITE = "MySite"`
   - Prompts tự động copy từ `original_prompts/`

2. **Backup prompts:**
   - Vào tab "Quản lý Prompts"
   - Nhấn **📦 Backup**
   - File được lưu vào `backup_prompts/<site>/`

3. **Reset prompts:**
   - Nhấn **🔄 Reset**
   - Ưu tiên restore từ backup
   - Nếu không có backup → restore từ original

4. **Lưu prompts:**
   - Chỉnh sửa System/Human Prompt
   - Nhấn **💾 Lưu**
   - Tự động tạo và lưu Extract Sections

## 📚 Tài liệu tham khảo

- [QUICKSTART_DOCKER.md](./QUICKSTART_DOCKER.md) - Hướng dẫn cơ bản về Docker
- [backup_prompts/README.md](./backup_prompts/README.md) - Chi tiết về backup workflow
- [original_prompts/README.md](./original_prompts/README.md) - Chi tiết về original prompts

## 💡 Tips

1. **Development workflow:**
   - Code thay đổi tự động sync vào container (nhờ volume mount)
   - Không cần rebuild nếu chỉ sửa code Python
   - Chỉ rebuild khi thay đổi `requirements.txt` hoặc `Dockerfile`

2. **Production deployment:**
   - Sử dụng `docker-compose build --no-cache` để đảm bảo build sạch
   - Test kỹ trước khi deploy
   - Backup dữ liệu thường xuyên

3. **Monitoring:**
   - Xem logs: `docker-compose logs -f`
   - Xem resource usage: `docker stats vpcp-automation-test`
   - Health check: `curl http://localhost:8501/_stcore/health`

