# ✅ Checklist triển khai tính năng Backup/Restore

## 📋 Pre-deployment Checklist

### 1. Files đã được cập nhật ✅

- [x] `original_site.py` - Template site mới với tính năng backup/restore
- [x] `pages/Agent HR Nội bộ.py` - Cập nhật UI và logic
- [x] `pages/THFC.py` - Cập nhật UI và logic
- [x] `Dockerfile` - Thêm thư mục original_prompts và backup_prompts
- [x] `docker-compose.yml` - Mount 2 thư mục mới + original_site.py
- [x] `requirements.txt` - Thêm package schedule
- [x] `.gitignore` - Thêm comment cho backup_prompts
- [x] `backup_prompts/README.md` - Tài liệu workflow backup
- [x] `original_prompts/README.md` - Tài liệu original prompts
- [x] `original_prompts/extract_sections.py` - Template extract
- [x] `original_prompts/system_prompt.txt` - Template system prompt
- [x] `original_prompts/human_prompt.txt` - Template human prompt

### 2. Scripts và tài liệu ✅

- [x] `rebuild_docker.sh` - Script rebuild Docker tự động
- [x] `DOCKER_UPDATE_GUIDE.md` - Hướng dẫn cập nhật Docker
- [x] `DEPLOYMENT_CHECKLIST.md` - File này

## 🚀 Deployment Steps

### Bước 1: Backup dữ liệu hiện tại

```bash
# Tạo backup folder với timestamp
BACKUP_DIR="backup_before_deploy_$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

# Backup các thư mục quan trọng
cp -r prompts/ $BACKUP_DIR/
cp -r original_prompts/ $BACKUP_DIR/ 2>/dev/null || true
cp -r backup_prompts/ $BACKUP_DIR/ 2>/dev/null || true
cp -r test_results/ $BACKUP_DIR/
cp -r scheduled_tests/ $BACKUP_DIR/

echo "✅ Backup hoàn tất tại: $BACKUP_DIR"
```

- [ ] Đã backup dữ liệu
- [ ] Kiểm tra backup folder chứa đầy đủ file

### Bước 2: Kiểm tra cấu trúc thư mục

```bash
# Kiểm tra các thư mục cần thiết
ls -la original_prompts/
ls -la backup_prompts/

# Kiểm tra file trong original_prompts
ls -la original_prompts/*.txt
ls -la original_prompts/*.py
```

- [ ] Thư mục `original_prompts/` tồn tại
- [ ] Thư mục `backup_prompts/` tồn tại
- [ ] File `original_prompts/system_prompt.txt` tồn tại
- [ ] File `original_prompts/human_prompt.txt` tồn tại
- [ ] File `original_prompts/extract_sections.py` tồn tại

### Bước 3: Stop container hiện tại (nếu đang chạy)

```bash
docker-compose down
```

- [ ] Container đã dừng
- [ ] Không còn container nào chạy trên port 8501

### Bước 4: Rebuild Docker image

**Option A: Sử dụng script tự động (Khuyến nghị)**
```bash
./rebuild_docker.sh --full
```

**Option B: Thủ công**
```bash
# Rebuild với no-cache
docker-compose build --no-cache

# Start container
docker-compose up -d

# Xem logs
docker-compose logs -f
```

- [ ] Build thành công không có lỗi
- [ ] Container đã khởi động
- [ ] Health check OK (http://localhost:8501/_stcore/health)

### Bước 5: Kiểm tra mount volumes

```bash
# Kiểm tra volumes được mount
docker exec vpcp-automation-test ls -la /app | grep prompts

# Kết quả mong đợi:
# drwxrwxrwx ... original_prompts
# drwxrwxrwx ... backup_prompts
# drwxrwxrwx ... prompts
```

- [ ] `original_prompts` được mount
- [ ] `backup_prompts` được mount
- [ ] `prompts` được mount
- [ ] Permissions đúng (777)

### Bước 6: Test chức năng mới

#### 6.1. Test trên site hiện có (Agent HR Nội bộ)

1. Truy cập: http://localhost:8501
2. Chọn site "Agent HR Nội bộ"
3. Vào tab "Quản lý Prompts"
4. Kiểm tra:

- [ ] Hiển thị 3 nút: 💾 Lưu, 📦 Backup, 🔄 Reset
- [ ] Preview Extract Sections hiển thị mapping
- [ ] System Prompt và Human Prompt load được

#### 6.2. Test chức năng Backup

1. Nhấn nút **📦 Backup**
2. Kiểm tra:

```bash
# Kiểm tra file backup
ls -la backup_prompts/Agent\ HR\ Nội\ bộ/
```

- [ ] Thông báo "✅ Đã backup prompts & extract sections!"
- [ ] Folder `backup_prompts/Agent HR Nội bộ/` được tạo
- [ ] File `system_prompt.txt` có trong backup
- [ ] File `human_prompt.txt` có trong backup
- [ ] File `extract_sections.py` có trong backup

#### 6.3. Test chức năng Lưu (Save)

1. Chỉnh sửa System Prompt hoặc Human Prompt
2. Nhấn nút **💾 Lưu**
3. Kiểm tra:

- [ ] Thông báo "✅ Đã lưu prompts & extract sections!"
- [ ] Extract sections tự động được tạo
- [ ] Preview Extract Sections cập nhật

#### 6.4. Test chức năng Reset

1. Chỉnh sửa prompts để tạo thay đổi
2. Nhấn nút **🔄 Reset**
3. Kiểm tra:

- [ ] Nếu có backup: Thông báo "✅ Đã reset từ backup!"
- [ ] Nếu không có backup: Thông báo về việc dùng original
- [ ] Prompts được restore về phiên bản trước

#### 6.5. Test tạo site mới

1. Copy `original_site.py` → `pages/TestSite.py`
2. Đổi `SITE = "TestSite"` trong file
3. Restart Streamlit
4. Chọn site "TestSite"
5. Kiểm tra:

```bash
# Kiểm tra folder prompts mới
ls -la prompts/TestSite/
```

- [ ] Site mới xuất hiện trong dropdown
- [ ] Folder `prompts/TestSite/` được tạo tự động
- [ ] Prompts được copy từ `original_prompts/`
- [ ] Extract sections được copy từ `original_prompts/`

### Bước 7: Test chức năng khác

#### 7.1. Test đơn lẻ
- [ ] Tab "Test đơn lẻ" hoạt động bình thường
- [ ] Chat history hoạt động (nếu có)

#### 7.2. Test hàng loạt
- [ ] Upload file Excel thành công
- [ ] Test cases chạy được
- [ ] Kết quả lưu vào `test_results/`

#### 7.3. Lập lịch test
- [ ] Tạo lịch test mới thành công
- [ ] Chỉnh sửa lịch test hoạt động
- [ ] Xóa lịch test hoạt động

#### 7.4. Quản lý test
- [ ] Dashboard hiển thị đúng
- [ ] Lịch sử test hiển thị
- [ ] File kết quả tải về được

### Bước 8: Monitoring

```bash
# Xem logs real-time
docker-compose logs -f

# Xem resource usage
docker stats vpcp-automation-test

# Health check
curl http://localhost:8501/_stcore/health
```

- [ ] Logs không có lỗi nghiêm trọng
- [ ] Memory usage ổn định (< 4GB)
- [ ] CPU usage hợp lý
- [ ] Health endpoint trả về 200

### Bước 9: Cleanup (Optional)

```bash
# Xóa các image cũ không dùng
docker image prune -f

# Xóa các volume không dùng
docker volume prune -f
```

- [ ] Đã cleanup images cũ
- [ ] Đã cleanup volumes không dùng

## 🐛 Rollback Plan (Nếu có vấn đề)

### Quick Rollback

```bash
# 1. Stop container hiện tại
docker-compose down

# 2. Restore backup
BACKUP_DIR="<tên folder backup ở Bước 1>"
cp -r $BACKUP_DIR/prompts/ ./
cp -r $BACKUP_DIR/original_prompts/ ./ 2>/dev/null || true
cp -r $BACKUP_DIR/backup_prompts/ ./ 2>/dev/null || true

# 3. Checkout code cũ (nếu cần)
git checkout <commit-hash-cũ>

# 4. Rebuild và start
docker-compose build
docker-compose up -d
```

## 📊 Post-deployment Verification

### Checklist cuối cùng

- [ ] Tất cả sites hiện có hoạt động bình thường
- [ ] Backup/Restore hoạt động cho mỗi site
- [ ] Scheduled tests vẫn chạy đúng lịch
- [ ] Không có error logs nghiêm trọng
- [ ] Performance không giảm sút
- [ ] Team đã được thông báo về tính năng mới

## 📝 Notes

**Ngày deploy:** _______________

**Người deploy:** _______________

**Vấn đề gặp phải (nếu có):**
```
[Ghi chú ở đây]
```

**Thời gian downtime:** _______________

**Backup location:** _______________

## 🎉 Tính năng mới

Sau khi deploy thành công, team có thể:

1. ✅ **Backup prompts** trước khi thử nghiệm
2. ✅ **Reset về phiên bản cũ** nếu có vấn đề
3. ✅ **Tạo site mới** nhanh chóng từ template
4. ✅ **Đồng bộ prompts & extract** tự động
5. ✅ **Preview mapping** trước khi lưu

## 📚 Tài liệu tham khảo

- [DOCKER_UPDATE_GUIDE.md](./DOCKER_UPDATE_GUIDE.md)
- [backup_prompts/README.md](./backup_prompts/README.md)
- [original_prompts/README.md](./original_prompts/README.md)

