# 🕐 Sửa lỗi Timezone và Reset Schedule

## 📋 Vấn đề đã sửa:

### 1. **Timezone - Hiển thị sai giờ (GMT+7)**
❌ **Trước:** Hiển thị giờ UTC  
✅ **Sau:** Hiển thị giờ Việt Nam (GMT+7) với `pytz.timezone('Asia/Ho_Chi_Minh')`

### 2. **Schedule bị reset khi reload trang**
❌ **Trước:**  
- Mỗi lần reload, `schedule.clear()` xóa tất cả jobs
- `next_run` time bị reset về thời gian mới
- `schedule_initialized` flag bị set lại thành False sau mỗi thao tác

✅ **Sau:**  
- Không clear schedule nữa
- Chỉ thêm jobs mới nếu chưa tồn tại
- Khi edit/xóa job: Xóa job cụ thể bằng `schedule.cancel_job()`
- `next_run` time được giữ nguyên

---

## 🔧 Các thay đổi chi tiết:

### **File: `pages/THFC.py`**

#### 1. Thêm import pytz (dòng 15):
```python
import pytz
```

#### 2. Sửa hiển thị "Chạy lần tới" với timezone (dòng ~3023-3031):
```python
if found_job:
    # Convert thời gian sang timezone Việt Nam (GMT+7)
    if found_job.next_run:
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        # schedule library trả về naive datetime, coi như UTC
        next_run_utc = pytz.utc.localize(found_job.next_run)
        next_run_vn = next_run_utc.astimezone(vn_tz)
        st.write(f"**Chạy lần tới:** {next_run_vn.strftime('%Y-%m-%d %H:%M:%S')} (GMT+7)")
    else:
        st.write(f"**Chạy lần tới:** N/A")
```

#### 3. Không clear schedule khi khởi tạo (dòng ~1699-1734):
```python
if not st.session_state.schedule_initialized:
    # Không clear schedule để giữ lại next_run time
    # Chỉ thêm các job chưa có
    existing_job_identifiers = set()
    for job in schedule.jobs:
        try:
            if len(job.job_func.args) >= 3:
                existing_job_identifiers.add((job.job_func.args[1], job.job_func.args[2]))
        except (IndexError, AttributeError):
            continue
    
    for job_config in st.session_state.scheduled_jobs:
        job_identifier = (job_config["test_name"], job_config["site"])
        
        if os.path.exists(job_config["file_path"]):
            # Chỉ thêm job nếu chưa có trong schedule
            if job_identifier not in existing_job_identifiers:
                setup_schedule(...)
```

#### 4. Xóa job cụ thể thay vì reset toàn bộ (dòng ~3054-3079):
```python
if st.button("Xóa cấu hình", key="delete_existing_job"):
    # Xóa job khỏi schedule
    jobs_to_remove = []
    for job in schedule.jobs:
        try:
            if len(job.job_func.args) >= 3 and job.job_func.args[1] == existing_job['test_name'] and job.job_func.args[2] == existing_job['site']:
                jobs_to_remove.append(job)
        except (IndexError, AttributeError):
            continue
    
    for job in jobs_to_remove:
        schedule.cancel_job(job)
    
    # Remove from scheduled jobs
    remove_scheduled_job_for_site(site)
    # Không còn: st.session_state.schedule_initialized = False
```

#### 5. Edit job: Xóa job cũ và tạo mới (dòng ~3239-3268):
```python
# Xóa job cũ và tạo lại với cấu hình mới
jobs_to_remove = []
for job in schedule.jobs:
    try:
        if len(job.job_func.args) >= 3 and job.job_func.args[1] == existing_job['test_name'] and job.job_func.args[2] == existing_job['site']:
            jobs_to_remove.append(job)
    except (IndexError, AttributeError):
        continue

for job in jobs_to_remove:
    schedule.cancel_job(job)

# Tạo lại job với cấu hình mới
setup_schedule(...)
# Không còn: st.session_state.schedule_initialized = False
```

#### 6. Tạo job mới: Thêm trực tiếp vào schedule (dòng ~3355-3367):
```python
# Thêm job mới vào schedule ngay lập tức
setup_schedule(
    file_path=saved_file_path,
    schedule_type=schedule_type,
    schedule_time=schedule_time,
    schedule_day=schedule_day,
    test_name=test_name,
    site=site,
    api_url=schedule_api_url,
    evaluate_api_url=schedule_evaluate_api_url,
    custom_interval=schedule_custom_interval,
    custom_unit=schedule_custom_unit
)
# Không còn: st.session_state.schedule_initialized = False
```

---

## 🎯 Kết quả:

✅ **Timezone Việt Nam (GMT+7)** được hiển thị chính xác  
✅ **Next run time** không bị reset khi reload trang  
✅ **Schedule** chỉ được cập nhật khi thực sự cần (create/edit/delete job)  
✅ **Performance** tốt hơn (không clear/recreate schedule mỗi lần reload)

---

## 📝 Lưu ý:

- File `pages/Agent HR Nội bộ.py` đã thêm `import pytz` nhưng **chưa áp dụng đầy đủ các thay đổi trên**
- Nếu cần, có thể áp dụng tương tự cho file Agent HR Nội bộ
- Dependencies cần thiết: `pytz` (có thể cần `pip install pytz` nếu chưa có)

---

## 🧪 Cách test:

1. Tạo một scheduled job mới
2. Note lại "Chạy lần tới" (VD: `2025-10-24 15:30:00 (GMT+7)`)
3. Reload trang (F5)
4. Kiểm tra "Chạy lần tới" → Phải giữ nguyên thời gian chính xác
5. Đợi đến giờ chạy và kiểm tra job có chạy không

---

**Ngày cập nhật:** 2025-10-24  
**Files đã sửa:**
- ✅ `pages/THFC.py`
- ⚠️ `pages/Agent HR Nội bộ.py` (chỉ thêm import pytz)

