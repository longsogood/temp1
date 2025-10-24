# 🔄 Persistent Schedule System - Hướng dẫn

## 🎯 Vấn đề đã giải quyết

### ❌ Trước:
- Schedule lưu trong Streamlit session_state → Mất khi reload/timeout
- Thread schedule manager bị terminate khi session end
- Không persistent giữa các lần restart app

### ✅ Sau:
- Schedule config lưu trong **`schedule_config.json`**
- **ScheduleManager singleton** chạy background thread độc lập
- **Thread-safe** và persistent qua các session
- Tự động load lại schedule khi app restart

---

## 📁 Files mới

### 1. **`schedule_config.json`**
```json
{
  "THFC": {
    "file_path": "test_cases/THFC/THFC_test_cases.xlsx",
    "schedule_type": "daily",
    "schedule_time": "15:30",
    "schedule_day": null,
    "test_name": "Daily Test",
    "site": "THFC",
    "api_url": "https://site1.com",
    "evaluate_api_url": "https://site2.com",
    "custom_interval": null,
    "custom_unit": null
  },
  "Agent HR Nội bộ": null
}
```

### 2. **`schedule_manager.py`**
**ScheduleManager** - Singleton class quản lý schedule:
- `load_schedules()` - Load từ JSON
- `save_schedules(configs)` - Save vào JSON
- `get_schedule_config(site)` - Get config cho 1 site
- `update_schedule(site, config)` - Update schedule (create/edit)
- `remove_schedule(site)` - Xóa schedule
- `get_next_run(site)` - Lấy thời gian chạy tiếp theo (GMT+7)
- `get_all_jobs()` - List tất cả jobs đang chạy

---

## 🔧 Thay đổi trong THFC.py

### 1. Import (Line 16)
```python
from schedule_manager import get_schedule_manager
```

### 2. Khởi tạo Schedule Manager (Line ~1690)
```python
# Initialize Persistent Schedule Manager (Global, thread-safe)
try:
    schedule_manager = get_schedule_manager()
    logger.info("Schedule Manager initialized successfully")
except Exception as e:
    logger.error(f"Error initializing Schedule Manager: {e}")
    schedule_manager = None
```

### 3. Get Schedule (Line ~1678)
```python
def get_scheduled_job_for_site(site):
    """Get scheduled job for a specific site"""
    if schedule_manager:
        return schedule_manager.get_schedule_config(site)
    return None
```

### 4. Hiển thị "Chạy lần tới" (Line ~2989)
```python
# Show next run time - Dùng Schedule Manager
if schedule_manager:
    next_run_vn = schedule_manager.get_next_run(site)
    if next_run_vn:
        st.write(f"**Chạy lần tới:** {next_run_vn.strftime('%Y-%m-%d %H:%M:%S')} (GMT+7)")
        st.caption("⏰ Thời gian được tính toán tự động và persistent qua các lần reload")
    else:
        st.write(f"**Chạy lần tới:** Đang tính toán...")
else:
    st.warning("⚠️ Schedule Manager chưa khởi tạo")
```

---

## 📝 Các thay đổi CẦN làm thêm

### ❗ QUAN TRỌNG: Update các operations schedule

#### 1. **Xóa Schedule** (Line ~3005)
```python
if st.button("Xóa cấu hình", key="delete_existing_job"):
    if schedule_manager:
        if schedule_manager.remove_schedule(site):
            st.success(f"✅ Đã xóa lịch test cho site '{site}'")
        else:
            st.error("❌ Lỗi khi xóa lịch test")
    st.rerun()
```

#### 2. **Edit Schedule** (Line ~3237)
```python
if st.button("Lưu thay đổi", key="save_edit_existing"):
    # Tạo config mới
    new_config = {
        "file_path": get_test_cases_file_path(site),
        "schedule_type": new_schedule_type,
        "schedule_time": new_schedule_time,
        "schedule_day": new_schedule_day,
        "test_name": new_test_name,
        "site": site,
        "api_url": new_api_url,
        "evaluate_api_url": new_eval_api_url,
        "custom_interval": new_custom_interval,
        "custom_unit": new_custom_unit
    }
    
    # Update schedule
    if schedule_manager:
        if schedule_manager.update_schedule(site, new_config):
            st.success(f"✅ Đã cập nhật lịch test cho site '{site}'")
        else:
            st.error("❌ Lỗi khi cập nhật lịch test")
    
    st.session_state.editing_existing_job = False
    st.rerun()
```

#### 3. **Tạo Schedule mới** (Line ~3352)
```python
if st.button("Thiết lập lịch"):
    # Tạo config
    config = {
        "file_path": get_test_cases_file_path(site),
        "schedule_type": schedule_type,
        "schedule_time": schedule_time,
        "schedule_day": schedule_day,
        "test_name": test_name,
        "site": site,
        "api_url": schedule_api_url,
        "evaluate_api_url": schedule_evaluate_api_url,
        "custom_interval": schedule_custom_interval,
        "custom_unit": schedule_custom_unit
    }
    
    # Update schedule
    if schedule_manager:
        if schedule_manager.update_schedule(site, config):
            st.success(f"✅ Đã thiết lập lịch chạy test '{test_name}' cho site '{site}'")
        else:
            st.error("❌ Lỗi khi thiết lập lịch test")
    
    st.rerun()
```

---

## 🧪 Cách test

### Test 1: Tạo schedule
1. Vào Tab "Lập lịch test"
2. Tạo schedule mới (VD: daily 15:30)
3. Note "Chạy lần tới"
4. Kiểm tra file `schedule_config.json` có config cho site

### Test 2: Reload persistence
1. **Reload trang (F5)**
2. Kiểm tra "Chạy lần tới" → Phải giữ nguyên
3. **Restart app (Ctrl+C, chạy lại)**
4. Kiểm tra "Chạy lần tới" → Phải vẫn còn!

### Test 3: Edit schedule
1. Edit schedule (thay đổi thời gian)
2. Kiểm tra "Chạy lần tới" cập nhật
3. Reload → Phải giữ thời gian mới

### Test 4: Delete schedule
1. Xóa schedule
2. Kiểm tra "Chạy lần tới" biến mất
3. Kiểm tra `schedule_config.json` → Site = null

### Test 5: Multiple sites
1. Tạo schedule cho cả THFC và Agent HR Nội bộ
2. Kiểm tra cả 2 schedule độc lập
3. Reload → Cả 2 vẫn còn

---

## 🔍 Debug

### Kiểm tra logs
```python
# Trong THFC.py có logging
logger.info("Schedule Manager initialized successfully")

# Trong schedule_manager.py
logger.info(f"Setup schedule for {site}: {schedule_type}")
logger.info(f"Schedule loop started")
```

### Kiểm tra schedule_config.json
```bash
cat schedule_config.json
```

### Kiểm tra jobs đang chạy
```python
if schedule_manager:
    jobs = schedule_manager.get_all_jobs()
    for job in jobs:
        print(f"Site: {job['site']}, Next: {job['next_run']}")
```

---

## ⚠️ Lưu ý quan trọng

### 1. File JSON phải có quyền ghi
```bash
chmod 666 schedule_config.json
```

### 2. Thread daemon
Schedule manager chạy daemon thread → Tự động terminate khi app stop

### 3. Circular import
schedule_manager.py import dynamic để tránh circular dependency:
```python
import importlib
module = importlib.import_module("pages.THFC")
run_scheduled_test = getattr(module, 'run_scheduled_test')
```

### 4. Timezone
Tất cả next_run time đều convert sang GMT+7:
```python
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')
```

---

## 📊 So sánh

| Tính năng | Session State (Cũ) | JSON + ScheduleManager (Mới) |
|-----------|---------------------|------------------------------|
| **Persistent qua reload** | ❌ Không | ✅ Có |
| **Persistent qua restart** | ❌ Không | ✅ Có |
| **Thread-safe** | ⚠️ Có thể race condition | ✅ Thread-safe (singleton + lock) |
| **Storage** | Memory (session_state) | File (schedule_config.json) |
| **Next run time** | Reset mỗi lần reload | ✅ Giữ nguyên |
| **Performance** | Nhanh (in-memory) | Nhanh (singleton cache) |

---

## ✅ Checklist migration

- [x] Tạo `schedule_manager.py`
- [x] Tạo `schedule_config.json`
- [x] Import schedule_manager trong THFC.py
- [x] Update `get_scheduled_job_for_site()`
- [x] Update hiển thị "Chạy lần tới"
- [ ] **CẦN LÀM:** Update "Xóa cấu hình" button
- [ ] **CẦN LÀM:** Update "Lưu thay đổi" (edit) button  
- [ ] **CẦN LÀM:** Update "Thiết lập lịch" (create) button
- [ ] Test đầy đủ các scenarios
- [ ] Áp dụng tương tự cho Agent HR Nội bộ

---

## 🚀 Next Steps

1. **Hoàn thành migration trong THFC.py** (3 buttons còn lại)
2. **Test kỹ toàn bộ flow**
3. **Áp dụng cho Agent HR Nội bộ**
4. **Xóa code cũ** (sau khi confirm hoạt động tốt)
5. **Document** cho team

---

**Ngày tạo:** 2025-10-24  
**Status:** ⚠️ In Progress - Cần hoàn thành 3 buttons còn lại

