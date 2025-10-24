# ✅ Cải tiến Quản lý Test Cases và Sites

## 🎯 Mục tiêu đã hoàn thành

### 1. **Mỗi site chỉ có 1 bộ test cases duy nhất**
- ✅ Thay vì nhiều files test cases, mỗi site giờ chỉ có 1 file: `{site}_test_cases.xlsx`
- ✅ Đơn giản hóa quản lý - không cần chọn file nào để chạy
- ✅ Tự động overwrite khi lưu - luôn có phiên bản mới nhất

### 2. **Xóa test cases sẽ xóa cả file**
- ✅ Nút "🗑️ Xóa Test Cases" trong Tab 4 sẽ xóa luôn file test cases
- ✅ Log đầy đủ vào `logs/test_log.log`

### 3. **Xóa site sẽ xóa toàn bộ dữ liệu liên quan**
- ✅ Hàm `delete_site_completely(site)` xóa tất cả:
  - `prompts/{site}/` - System và Human prompts
  - `backup_prompts/{site}/` - Backup prompts
  - `utils/{site}/` - Extract sections code
  - `test_cases/{site}/` - Test cases
  - `test_results/{site}/` - Kết quả test
  - `scheduled_tests/{site}/` - File test cho scheduled jobs
  - `config/{site}_config.pkl` - File cấu hình
  - Session state và scheduled jobs

---

## 📂 Cấu trúc mới

### Trước đây:
```
test_cases/
├── THFC/
│   ├── Test_Cases_1_20251024_100000.xlsx
│   ├── Test_Cases_2_20251024_110000.xlsx
│   └── Test_Cases_3_20251024_120000.xlsx  ❌ Nhiều files!
```

### Bây giờ:
```
test_cases/
├── THFC/
│   └── THFC_test_cases.xlsx  ✅ Chỉ 1 file duy nhất!
```

---

## 🔧 Các hàm mới/đã thay đổi

### Test Cases Management

#### **`get_test_cases_file_path(site)`**
```python
# Trả về đường dẫn file test cases duy nhất của site
filepath = get_test_cases_file_path("THFC")
# → "test_cases/THFC/THFC_test_cases.xlsx"
```

#### **`save_test_cases(site, test_cases_df)`**
```python
# Lưu test cases (overwrite nếu đã tồn tại)
# KHÔNG cần tham số test_name nữa
save_test_cases("THFC", df)
```

#### **`load_test_cases(site)`**
```python
# Load test cases của site (trả về DataFrame hoặc None)
df = load_test_cases("THFC")
```

#### **`test_cases_exists(site)`**
```python
# Kiểm tra xem site có test cases chưa
if test_cases_exists("THFC"):
    print("Có test cases")
```

#### **`delete_test_cases(site)`**
```python
# Xóa file test cases của site
success = delete_test_cases("THFC")
```

#### **`delete_site_completely(site)`** ⭐ MỚI
```python
# Xóa toàn bộ dữ liệu liên quan đến site
success, deleted_items = delete_site_completely("THFC")
# → (True, ["prompts/THFC", "test_cases/THFC", ...])
```

---

## 🎨 Thay đổi giao diện

### Tab 2 - Lập lịch test

**Trước:**
```
Bước 2: Chọn test cases và đặt tên
[Dropdown: Chọn bộ test cases] ❌ Phức tạp!
```

**Sau:**
```
Bước 2: Kiểm tra test cases và đặt tên
✅ Test cases hiện tại: 50 test cases
[Preview 5 test cases đầu tiên]
```

### Tab 4 - Quản lý Test Cases

**Trước:**
```
📚 Danh sách Test Cases đã lưu
[Dropdown: Chọn file test cases để xem]  ❌ Nhiều files!
  Test_Cases_1_...
  Test_Cases_2_...
```

**Sau:**
```
📚 Test Cases hiện tại
Số test cases: 50
[Preview 10 test cases đầu tiên]
[🗑️ Xóa Test Cases] [📥 Tải xuống]  ✅ Đơn giản!
```

---

## 📝 Files đã cập nhật

✅ `pages/THFC.py`
✅ `pages/Agent HR Nội bộ.py`

### Các thay đổi chính:

1. **Test Cases Functions** (lines ~1035-1088 in THFC.py, ~967-1082 in Agent HR.py)
   - Thay thế 3 hàm cũ bằng 6 hàm mới
   - Thêm `delete_site_completely()`

2. **Tab 2 - Lập lịch test** (lines ~3173-3246)
   - Bỏ selectbox chọn test cases file
   - Tự động load test cases hiện tại của site
   - Sử dụng `get_test_cases_file_path(site)`

3. **Tab 4 - Quản lý Test Cases** (lines ~2211-2292)
   - Bỏ input tên test cases (không cần nữa)
   - Hiển thị test cases hiện tại thay vì list files
   - Nút xóa gọi `delete_test_cases(site)`
   - Download với tên file `{site}_test_cases.xlsx`

---

## 🚀 Cách sử dụng

### 1. Lưu test cases mới
```python
# Trong Tab 4 - Upload Excel và nhấn "💾 Lưu Test Cases"
# File sẽ được lưu tại: test_cases/{site}/{site}_test_cases.xlsx
```

### 2. Xóa test cases
```python
# Trong Tab 4 - Nhấn "🗑️ Xóa Test Cases"
# File test_cases/{site}/{site}_test_cases.xlsx sẽ bị xóa
```

### 3. Lập lịch test
```python
# Trong Tab 2:
# - Kiểm tra test cases hiện tại (tự động load)
# - Đặt tên và thiết lập lịch
# - Hệ thống tự động dùng file test cases duy nhất của site
```

### 4. Xóa site hoàn toàn (cần thêm UI)
```python
# Gọi hàm để xóa toàn bộ dữ liệu site:
success, deleted_items = delete_site_completely("THFC")
if success:
    print(f"Đã xóa: {', '.join(deleted_items)}")
```

---

## ⚠️ Lưu ý quan trọng

### Breaking Changes:
1. **Test cases cũ sẽ KHÔNG tự động migrate**
   - Files test cases cũ: `Test_Cases_*_datetime.xlsx`
   - File mới: `{site}_test_cases.xlsx`
   - **Giải pháp:** Upload lại test cases trong Tab 4

2. **Scheduled jobs cũ có thể bị lỗi**
   - Jobs cũ vẫn trỏ đến files cũ (không tồn tại)
   - **Giải pháp:** Xóa và tạo lại scheduled jobs

3. **API changes:**
   - `save_test_cases(site, df, name)` → `save_test_cases(site, df)`
   - `load_test_cases_from_file(site, filename)` → `load_test_cases(site)`
   - `load_test_cases_list(site)` → ❌ Đã xóa

---

## 🔍 Testing Checklist

### Manual Testing:
- [ ] Upload test cases mới trong Tab 4
- [ ] Xem test cases hiện tại trong Tab 4
- [ ] Xóa test cases và kiểm tra file đã bị xóa
- [ ] Tạo scheduled job mới trong Tab 2
- [ ] Chạy test hàng loạt trong Tab 1
- [ ] Test với cả 2 sites: THFC và "Agent HR Nội bộ"

### Expected Behaviors:
- ✅ Chỉ có 1 file test cases cho mỗi site
- ✅ Lưu mới sẽ overwrite file cũ
- ✅ Xóa test cases sẽ xóa file khỏi disk
- ✅ Scheduled jobs tự động dùng file test cases hiện tại
- ✅ Không còn dropdown chọn test cases file

---

## 📌 TODO: Thêm UI xóa site

Cần thêm UI để gọi `delete_site_completely()`:

### Option 1: Thêm vào Tab 5 (Quản lý Prompts)
```python
st.write("### ⚠️ Xóa Site hoàn toàn")
st.warning("Thao tác này sẽ xóa TẤT CẢ dữ liệu liên quan đến site!")

if st.button("🗑️ Xóa Site và toàn bộ dữ liệu", type="secondary"):
    # Confirm dialog
    confirm = st.checkbox(f"Tôi hiểu rủi ro và muốn xóa site '{site}' hoàn toàn")
    if confirm and st.button("Xác nhận xóa", type="primary"):
        success, deleted_items = delete_site_completely(site)
        if success:
            st.success(f"✅ Đã xóa: {', '.join(deleted_items)}")
            # Redirect về trang chủ
        else:
            st.error("❌ Lỗi khi xóa site!")
```

### Option 2: Tạo Tab mới "Quản lý Sites"
- Hiển thị danh sách tất cả sites
- Cho phép xóa từng site
- Hiển thị thống kê dung lượng sử dụng

---

## 🎉 Kết luận

✅ **Đã hoàn thành:**
- Mỗi site chỉ có 1 bộ test cases duy nhất
- Xóa test cases xóa cả file
- Hàm xóa site hoàn toàn đã sẵn sàng

⏳ **Cần thêm:**
- UI để xóa site (gọi `delete_site_completely()`)
- Migration guide cho test cases cũ
- Thông báo khi có scheduled jobs cũ bị lỗi

---

**Ngày cập nhật:** 2025-10-24  
**Files updated:** `pages/THFC.py`, `pages/Agent HR Nội bộ.py`  
**Status:** ✅ HOÀN THÀNH

