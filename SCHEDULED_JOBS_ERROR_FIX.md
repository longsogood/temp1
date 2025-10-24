# Sửa lỗi AttributeError: st.session_state has no attribute "scheduled_jobs"

## 🐛 Lỗi gốc
```
AttributeError: st.session_state has no attribute "scheduled_jobs". Did you forget to initialize it?
File "/mnt/c/users/nvlong8/Documents/agents/VPCP_AutoTest/pages/Agent HR Nội bộ.py", line 3192, in <module>
    st.session_state.scheduled_jobs.append(job_config)
```

## 🔍 Nguyên nhân
Trong quá trình migration từ `st.session_state.scheduled_jobs` sang `schedule_manager`, tôi đã cập nhật một số chỗ nhưng vẫn còn sót lại một số chỗ sử dụng logic cũ.

## ✅ Các thay đổi đã thực hiện

### 1. **Thiết lập lịch mới** (Create Schedule)
**Trước:**
```python
st.session_state.scheduled_jobs.append(job_config)
save_scheduled_jobs()  # Save to file
```

**Sau:**
```python
# Sử dụng Schedule Manager để lưu
if schedule_manager:
    if schedule_manager.update_schedule(site, job_config):
        st.success(f"Đã thiết lập lịch chạy test '{test_name}' cho site '{site}'.")
    else:
        st.error("❌ Lỗi khi lưu lịch test!")
else:
    st.error("❌ Schedule Manager chưa khởi tạo!")
```

### 2. **Chỉnh sửa lịch** (Edit Schedule)
**Trước:**
```python
job_index = next((i for i, job in enumerate(st.session_state.scheduled_jobs) if job['job_id'] == existing_job['job_id']), None)
if job_index is not None:
    st.session_state.scheduled_jobs[job_index]['file_path'] = get_test_cases_file_path(site)
    # ... update other fields
    save_scheduled_jobs()
```

**Sau:**
```python
# Tạo config mới
new_job_config = {
    "file_path": get_test_cases_file_path(site),
    "schedule_type": new_schedule_type,
    "schedule_time": new_schedule_time,
    "schedule_day": new_schedule_day,
    "test_name": new_test_name,
    "site": site,
    "custom_interval": new_custom_interval,
    "custom_unit": new_custom_unit,
    "api_url": new_api_url,
    "evaluate_api_url": new_eval_api_url,
    "job_id": existing_job.get('job_id', str(uuid4()))
}

# Sử dụng Schedule Manager để cập nhật
if schedule_manager:
    if schedule_manager.update_schedule(site, new_job_config):
        st.session_state.editing_existing_job = False
        st.success(f"✅ Đã cập nhật cấu hình lịch test cho site '{site}'.")
    else:
        st.error("❌ Lỗi khi cập nhật lịch test!")
else:
    st.error("❌ Schedule Manager chưa khởi tạo!")
```

### 3. **Loại bỏ functions cũ**
**Trước:**
```python
def save_scheduled_jobs():
    """Save scheduled jobs to file"""
    try:
        with open(SCHEDULED_JOBS_FILE, "wb") as f:
            pickle.dump(st.session_state.scheduled_jobs, f)
    except Exception as e:
        logger.error(f"Lỗi khi lưu scheduled jobs: {str(e)}")

def load_scheduled_jobs():
    """Load scheduled jobs from file"""
    # ... implementation
```

**Sau:**
```python
# Deprecated functions - now using schedule_manager
# def save_scheduled_jobs() and load_scheduled_jobs() are no longer needed
```

### 4. **Cập nhật remove_scheduled_job_for_site()**
**Trước:**
```python
def remove_scheduled_job_for_site(site):
    """Remove scheduled job for a specific site"""
    st.session_state.scheduled_jobs = [job for job in st.session_state.scheduled_jobs if job.get('site') != site]
    save_scheduled_jobs()
```

**Sau:**
```python
def remove_scheduled_job_for_site(site):
    """Remove scheduled job for a specific site - now using schedule_manager"""
    if schedule_manager:
        return schedule_manager.remove_schedule(site)
    return False
```

### 5. **Loại bỏ session state không cần thiết**
**Trước:**
```python
if 'schedule_manager' not in st.session_state:
    st.session_state.schedule_manager = get_schedule_manager()
```

**Sau:**
```python
# Removed - schedule_manager is now a global variable, not in session_state
```

## 🎯 Kết quả

### ✅ Đã hoàn thành
- ✅ **Create Schedule**: Sử dụng `schedule_manager.update_schedule()`
- ✅ **Edit Schedule**: Sử dụng `schedule_manager.update_schedule()`
- ✅ **Delete Schedule**: Sử dụng `schedule_manager.remove_schedule()`
- ✅ **Get Schedule**: Sử dụng `schedule_manager.get_schedule_config()`
- ✅ **Next Run**: Sử dụng `schedule_manager.get_next_run()` với GMT+7

### 🗑️ Đã loại bỏ
- ❌ `st.session_state.scheduled_jobs`
- ❌ `save_scheduled_jobs()`
- ❌ `load_scheduled_jobs()`
- ❌ `st.session_state.schedule_initialized`
- ❌ `schedule.clear()` logic

### 📊 Lợi ích
1. **Persistent**: Schedule không bị reset khi reload trang
2. **Centralized**: Tất cả schedule được quản lý bởi `schedule_manager`
3. **JSON-backed**: Lưu trữ trong `schedule_config.json`
4. **Timezone**: Hiển thị đúng giờ Việt Nam (GMT+7)
5. **Error-free**: Không còn lỗi `AttributeError`

## 🧪 Test lại

### Test Create Schedule
1. Vào Agent HR Nội bộ → Tab "Lập lịch test"
2. Tạo lịch test mới
3. ✅ Không còn lỗi `AttributeError`
4. ✅ Lịch được lưu vào `schedule_config.json`

### Test Edit Schedule
1. Vào Agent HR Nội bộ → Tab "Lập lịch test"
2. Chỉnh sửa lịch hiện có
3. ✅ Không còn lỗi `AttributeError`
4. ✅ Lịch được cập nhật trong `schedule_config.json`

### Test Delete Schedule
1. Vào Agent HR Nội bộ → Tab "Lập lịch test"
2. Xóa lịch hiện có
3. ✅ Không còn lỗi `AttributeError`
4. ✅ Lịch được xóa khỏi `schedule_config.json`

### Test Persistence
1. Tạo lịch test
2. Reload trang (F5)
3. ✅ "Chạy lần tới" vẫn hiển thị đúng (GMT+7)
4. ✅ Lịch không bị reset

## 📝 Files đã thay đổi
- `pages/Agent HR Nội bộ.py` - Hoàn toàn migration sang schedule_manager

## 🚀 Status
**✅ HOÀN THÀNH** - Agent HR Nội bộ giờ đã hoàn toàn tương thích với persistent schedule system!
