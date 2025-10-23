# 📝 Changelog - Docker Configuration Updates

## Version: Docker v2.0 - Backup/Restore Support
**Ngày cập nhật:** 23/10/2025

---

## 🎯 Tóm tắt

Cập nhật cấu hình Docker để hỗ trợ đầy đủ tính năng **Backup/Restore prompts & extract sections**.

### Tại sao cần cập nhật?

Phiên bản mới thêm 2 thư mục quan trọng:
- `original_prompts/` - Lưu template mặc định cho site mới
- `backup_prompts/` - Lưu backup của từng site

Docker cần mount 2 thư mục này để dữ liệu được đồng bộ giữa host và container.

---

## 📦 Các file đã thay đổi

### 1. `Dockerfile` ⭐⭐⭐

**Thay đổi:**
```dockerfile
# TRƯỚC
RUN mkdir -p /app/test_results \
    /app/logs \
    /app/scheduled_tests \
    /app/prompts \
    /app/utils \
    ...

# SAU
RUN mkdir -p /app/test_results \
    /app/logs \
    /app/scheduled_tests \
    /app/prompts \
    /app/original_prompts \      # ← MỚI
    /app/backup_prompts \        # ← MỚI
    /app/utils \
    ...
```

**Tác động:**
- Container tạo 2 thư mục mới khi build
- Set permissions 777 để ghi file được

**Action required:** ✅ Cần rebuild image

---

### 2. `docker-compose.yml` ⭐⭐⭐

**Thay đổi:**
```yaml
volumes:
  - ./pages:/app/pages
  - ./utils:/app/utils
  - ./prompts:/app/prompts
  - ./original_prompts:/app/original_prompts    # ← MỚI
  - ./backup_prompts:/app/backup_prompts        # ← MỚI
  
  # Mount files
  - ./site_selector.py:/app/site_selector.py
  - ./original_site.py:/app/original_site.py    # ← MỚI
  ...
```

**Tác động:**
- Dữ liệu trong `original_prompts/` và `backup_prompts/` được đồng bộ 2 chiều
- File `original_site.py` accessible trong container

**Action required:** ✅ Cần restart container

---

### 3. `requirements.txt` ⭐⭐

**Thay đổi:**
```txt
# Thêm dòng mới:
schedule>=1.2.0
```

**Tác động:**
- Package `schedule` cần thiết cho chức năng lập lịch test
- Đã dùng trong code nhưng chưa được khai báo

**Action required:** ✅ Cần rebuild image

---

### 4. `.gitignore` ⭐

**Thay đổi:**
```gitignore
# Thêm comment:
# Backup prompts - có thể uncomment dòng dưới nếu muốn giữ backup local only
# backup_prompts/
```

**Tác động:**
- Mặc định: backup_prompts/ vẫn được commit vào Git
- Nếu muốn chỉ lưu local → uncomment dòng `backup_prompts/`

**Action required:** ❌ Không cần rebuild

---

## 🆕 Files mới được tạo

### 1. `DOCKER_UPDATE_GUIDE.md`
- Hướng dẫn chi tiết cách rebuild Docker
- Troubleshooting các lỗi thường gặp

### 2. `rebuild_docker.sh`
- Script tự động rebuild Docker
- 3 modes: `--full`, `--quick`, `--restart`

### 3. `DEPLOYMENT_CHECKLIST.md`
- Checklist đầy đủ cho deployment
- Bao gồm rollback plan

### 4. `CHANGELOG_DOCKER.md`
- File này - tóm tắt thay đổi

---

## 🚀 Hướng dẫn nâng cấp

### Quick Start (3 bước)

```bash
# Bước 1: Backup dữ liệu
tar -czf backup_$(date +%Y%m%d).tar.gz prompts/ original_prompts/ backup_prompts/

# Bước 2: Rebuild Docker
./rebuild_docker.sh --full

# Bước 3: Kiểm tra
curl http://localhost:8501/_stcore/health
```

### Chi tiết

Xem file [DOCKER_UPDATE_GUIDE.md](./DOCKER_UPDATE_GUIDE.md) để biết chi tiết.

---

## ✅ So sánh trước và sau

### Trước khi cập nhật

```
Container structure:
/app
├── pages/
├── utils/
├── prompts/
├── test_results/
├── logs/
└── scheduled_tests/

Volume mounts:
- prompts/     → /app/prompts
- test_results/ → /app/test_results
- ...
```

### Sau khi cập nhật

```
Container structure:
/app
├── pages/
├── utils/
├── prompts/
├── original_prompts/      ← MỚI
├── backup_prompts/        ← MỚI
├── test_results/
├── logs/
├── scheduled_tests/
└── original_site.py       ← MỚI

Volume mounts:
- prompts/          → /app/prompts
- original_prompts/ → /app/original_prompts   ← MỚI
- backup_prompts/   → /app/backup_prompts     ← MỚI
- original_site.py  → /app/original_site.py   ← MỚI
- test_results/     → /app/test_results
- ...
```

---

## 🎯 Lợi ích

### 1. Data Persistence ✅
- Backup prompts được lưu ngoài container
- Không mất dữ liệu khi rebuild

### 2. Consistency ✅
- Original prompts là single source of truth
- Mọi site mới đều dùng template giống nhau

### 3. Easy Rollback ✅
- Backup và restore trong 1 click
- Không cần SSH vào container

### 4. Team Collaboration ✅
- Backup có thể commit vào Git (nếu muốn)
- Share prompts giữa các developers

---

## ⚠️ Breaking Changes

### Không có Breaking Changes

Tất cả chức năng cũ vẫn hoạt động bình thường:
- ✅ Test đơn lẻ
- ✅ Test hàng loạt
- ✅ Lập lịch test
- ✅ Quản lý test
- ✅ Sites hiện có (THFC, Agent HR Nội bộ)

Chỉ **THÊM** tính năng mới, không **THAY ĐỔI** tính năng cũ.

---

## 🐛 Known Issues

### Issue 1: Folder không tồn tại trên host

**Triệu chứng:**
```
ERROR: Cannot start service vpcp-streamlit: 
error while creating mount source path 'original_prompts': mkdir
```

**Giải pháp:**
```bash
mkdir -p original_prompts backup_prompts
```

### Issue 2: Permission denied

**Triệu chứng:**
```
PermissionError: [Errno 13] Permission denied: '/app/backup_prompts/...'
```

**Giải pháp:**
```bash
docker exec vpcp-automation-test chmod -R 777 /app/backup_prompts
docker exec vpcp-automation-test chmod -R 777 /app/original_prompts
```

### Issue 3: Module 'schedule' not found

**Triệu chứng:**
```
ModuleNotFoundError: No module named 'schedule'
```

**Giải pháp:**
Rebuild image với `--no-cache`:
```bash
docker-compose build --no-cache
```

---

## 📊 Testing Checklist

Sau khi rebuild, test các chức năng sau:

- [ ] Container khởi động thành công
- [ ] Health check OK (http://localhost:8501/_stcore/health)
- [ ] Truy cập được UI (http://localhost:8501)
- [ ] Tab "Quản lý Prompts" hiển thị đầy đủ
- [ ] Nút 💾 Lưu hoạt động
- [ ] Nút 📦 Backup hoạt động
- [ ] Nút 🔄 Reset hoạt động
- [ ] Preview Extract Sections hiển thị mapping
- [ ] Test đơn lẻ chạy được
- [ ] Test hàng loạt chạy được
- [ ] Lập lịch test hoạt động

---

## 🔄 Rollback

Nếu có vấn đề sau khi upgrade:

```bash
# 1. Checkout code cũ
git checkout <commit-hash-trước-khi-update>

# 2. Rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# 3. Restore data từ backup
tar -xzf backup_YYYYMMDD.tar.gz
```

---

## 📞 Support

Nếu gặp vấn đề:

1. Kiểm tra [DOCKER_UPDATE_GUIDE.md](./DOCKER_UPDATE_GUIDE.md) - Section Troubleshooting
2. Xem logs: `docker-compose logs -f`
3. Kiểm tra [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md)

---

## 📅 Timeline

- **23/10/2025**: Release Docker v2.0 với Backup/Restore support
- **TBD**: Monitoring và feedback từ users

---

## 👥 Contributors

- **Developer**: AI Assistant
- **Reviewer**: nvlong8

---

## 📚 Related Documents

- [DOCKER_UPDATE_GUIDE.md](./DOCKER_UPDATE_GUIDE.md) - Chi tiết rebuild
- [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md) - Checklist đầy đủ
- [backup_prompts/README.md](./backup_prompts/README.md) - Workflow backup
- [original_prompts/README.md](./original_prompts/README.md) - Original prompts

---

**Happy Deploying! 🚀**

