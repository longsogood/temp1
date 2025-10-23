# Backup Prompts - Thư mục chứa backup của prompts & extract sections

## Mục đích

Thư mục này chứa các **bản backup** của prompts và extract sections cho từng site. Backup được tạo thủ công bởi người dùng để lưu trữ phiên bản hoạt động tốt trước khi thực hiện các thay đổi.

## Cấu trúc

```
backup_prompts/
├── <Site Name 1>/
│   ├── system_prompt.txt      # Backup system prompt
│   ├── human_prompt.txt        # Backup human prompt
│   └── extract_sections.py    # Backup extract sections code
├── <Site Name 2>/
│   ├── system_prompt.txt
│   ├── human_prompt.txt
│   └── extract_sections.py
└── README.md                   # File này
```

## Cách hoạt động

### 1. Lưu prompts & extract sections

**Trong tab "Quản lý Prompts" của mỗi site:**

- Nhấn nút **"💾 Lưu"** → Lưu cả system_prompt.txt, human_prompt.txt VÀ tự động tạo extract_sections.py

**Đặc biệt:**
- Extract sections được **tự động sinh** từ system prompt
- Không cần lưu riêng extract sections
- Đảm bảo prompts và extract luôn đồng bộ

### 2. Backup prompts & extract sections

**Trong tab "Quản lý Prompts" của mỗi site:**

- Nhấn nút **"📦 Backup"** → Lưu bản backup của cả prompts VÀ extract sections

**Lưu ý:**
- Backup ghi đè lên backup cũ (chỉ giữ 1 bản backup mới nhất cho mỗi site)
- Nên backup sau khi đã test và xác nhận prompts hoạt động tốt
- Backup được lưu tại: `backup_prompts/<site_name>/`

### 3. Reset prompts & extract sections

**Khi nhấn nút "🔄 Reset":**

Hệ thống sẽ thực hiện theo **thứ tự ưu tiên**:

1. **Ưu tiên 1: Restore từ Backup** (nếu có)
   - Kiểm tra folder `backup_prompts/<site_name>/`
   - Nếu tồn tại → Copy từ backup về `prompts/<site_name>/` hoặc `utils/<site_name>/`
   - Thông báo: ✅ "Đã reset từ backup!"

2. **Ưu tiên 2: Restore từ Original** (nếu không có backup)
   - Kiểm tra folder `original_prompts/`
   - Copy từ original về `prompts/<site_name>/` hoặc `utils/<site_name>/`
   - Thông báo: 📄 "Không tìm thấy backup, đã reset từ original_prompts!"

3. **Lỗi** (nếu cả backup và original đều không có)
   - Thông báo: ⚠️ "Không thể reset. Vui lòng kiểm tra backup hoặc original_prompts"

## So sánh với original_prompts

| Đặc điểm | `backup_prompts/` | `original_prompts/` |
|----------|-------------------|---------------------|
| **Mục đích** | Backup cá nhân theo site | Template mặc định chung |
| **Tạo bởi** | Người dùng (thủ công) | Hệ thống (tự động) |
| **Số lượng** | 1 backup/site | 1 bộ template chung |
| **Cập nhật** | Khi người dùng backup | Khi cập nhật template mặc định |
| **Ưu tiên khi Reset** | Ưu tiên 1 (cao nhất) | Ưu tiên 2 (fallback) |
| **Ghi đè** | Có (mỗi lần backup) | Không |

## Workflow khuyến nghị

### Khi chỉnh sửa prompts:

```
1. Backup hiện tại (1 nút)
   ↓
2. Chỉnh sửa và lưu (1 nút - tự động sync extract)
   ↓
3. Test
   ↓
4. Nếu OK → Backup lại
   ↓
5. Nếu KHÔNG OK → Reset (1 nút - khôi phục cả prompts + extract)
```

### Chi tiết các bước:

1. **Trước khi chỉnh sửa**: 
   - Nhấn **"📦 Backup"** 
   - → Backup cả prompts VÀ extract sections
   - Đảm bảo có backup của phiên bản đang hoạt động tốt

2. **Trong quá trình chỉnh sửa**:
   - Chỉnh sửa System Prompt và Human Prompt trên UI
   - Nhấn **"💾 Lưu"**
   - → Tự động lưu prompts VÀ tạo extract sections từ system prompt
   - Extract sections luôn đồng bộ với prompts

3. **Test**:
   - Chạy vài test cases để kiểm tra
   - Xem preview extract sections ở phần dưới

4. **Sau khi test thành công**:
   - Nhấn lại **"📦 Backup"**
   - → Backup mới ghi đè lên backup cũ

5. **Nếu có vấn đề**:
   - Nhấn **"🔄 Reset"**
   - → Restore cả prompts VÀ extract sections từ backup
   - Quay lại phiên bản hoạt động tốt

## Ví dụ thực tế

### Ví dụ 1: Chỉnh sửa system prompt cho THFC

```bash
# Trước khi sửa
1. Vào tab "Quản lý Prompts" → THFC
2. Nhấn "📦 Backup" 
   → Lưu cả prompts + extract vào backup_prompts/THFC/

# Chỉnh sửa
3. Sửa system prompt (thêm tiêu chí mới "empathy")
4. Nhấn "💾 Lưu"
   → Tự động lưu prompts
   → Tự động tạo extract_sections.py mới với tiêu chí "empathy"
5. Xem preview extract sections ở phần dưới
6. Test thử → Phát hiện extract code có lỗi

# Khôi phục
7. Nhấn "🔄 Reset"
   → Hệ thống restore cả prompts + extract từ backup_prompts/THFC/
   → Thông báo: "Đã reset từ backup!"
8. Quay lại phiên bản hoạt động tốt (cả prompts + extract)
```

### Ví dụ 2: Site mới không có backup

```bash
# Site mới "MySite"
1. Lần đầu vào → Chưa có backup
2. Nhấn "🔄 Reset"
   → Không tìm thấy backup_prompts/MySite/
   → Tự động lấy từ original_prompts/
   → Thông báo: "Đã reset từ original_prompts!"
```

### Ví dụ 3: Workflow hoàn chỉnh

```bash
# Tình huống: Cần sửa system prompt để cải thiện đánh giá

1. Backup trước khi sửa:
   📦 Backup → "Đã backup prompts & extract sections!"

2. Chỉnh sửa:
   - Sửa system prompt (thay đổi mô tả tiêu chí "accuracy")
   💾 Lưu → "Đã lưu prompts & extract sections!"
   - Extract sections được tự động cập nhật

3. Test:
   - Chạy 10 test cases
   - Kết quả: Điểm đánh giá chính xác hơn ✅

4. Backup phiên bản mới:
   📦 Backup → "Đã backup prompts & extract sections!"
   - Ghi đè lên backup cũ
   - Giữ phiên bản tốt nhất

# Nếu test không OK:
3. Test:
   - Chạy test cases
   - Kết quả: Có vấn đề ❌

4. Khôi phục:
   🔄 Reset → "Đã reset từ backup!"
   - Quay lại phiên bản hoạt động tốt
   - Thử cách sửa khác
```

## Quản lý Backup

### Xem danh sách backup

```bash
ls -la backup_prompts/
# Sẽ thấy:
# - Agent HR Nội bộ/
# - THFC/
# - MySite/ (nếu đã backup)
```

### Xóa backup của một site

```bash
rm -rf backup_prompts/THFC/
# Lần reset tiếp theo sẽ dùng original_prompts
```

### Backup toàn bộ folder

```bash
# Backup thủ công ra ngoài project
cp -r backup_prompts/ ~/my_backups/backup_prompts_$(date +%Y%m%d)/
```

## Best Practices

1. **Backup trước khi sửa**: Luôn backup trước khi chỉnh sửa prompts
2. **Test kỹ trước khi backup**: Đảm bảo phiên bản mới hoạt động tốt
3. **Một nút cho tất cả**: Chỉ cần 3 nút:
   - 💾 Lưu (cả prompts + extract)
   - 📦 Backup (cả prompts + extract)
   - 🔄 Reset (cả prompts + extract)
4. **Xem preview extract**: Kiểm tra mapping trong section "Preview Extract Sections"
5. **Không xóa backup**: Chỉ xóa khi chắc chắn không cần nữa
6. **Sử dụng Git**: Commit cả `backup_prompts/` vào Git để có version control
7. **Backup external**: Định kỳ backup folder này ra ngoài project

## Lưu ý quan trọng

⚠️ **Backup ghi đè**: Mỗi lần backup sẽ ghi đè lên bản backup cũ. Nếu cần giữ nhiều phiên bản, hãy:
- Sử dụng Git để version control
- Hoặc backup thủ công ra folder khác trước khi backup mới

⚠️ **Không tự động**: Hệ thống KHÔNG tự động backup. Người dùng phải chủ động nhấn nút "📦 Backup"

⚠️ **Reset ưu tiên backup**: Khi nhấn "🔄 Reset", hệ thống ưu tiên dùng backup trước, nên đảm bảo backup là phiên bản muốn khôi phục

## Troubleshooting

### "Không thể backup - prompts rỗng"
- Nguyên nhân: Chưa có prompts nào được load
- Giải pháp: Vào tab "Quản lý Prompts" và kiểm tra xem prompts đã được load chưa

### "Không thể reset - cả backup và original đều rỗng"
- Nguyên nhân: Thiếu cả backup và original_prompts
- Giải pháp: 
  - Kiểm tra folder `original_prompts/` có đầy đủ file không
  - Hoặc tạo backup thủ công vào `backup_prompts/<site>/`

### Reset nhưng không thấy thay đổi
- Nguyên nhân: Cache của browser
- Giải pháp: Hard refresh (Ctrl+F5) hoặc clear cache

## Liên hệ

Nếu có thắc mắc về hệ thống backup, vui lòng liên hệ team phát triển.

