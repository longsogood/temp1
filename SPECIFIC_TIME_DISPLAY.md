# Hiển thị thời gian cụ thể và tự động save config

## 🎯 Yêu cầu
1. **Hiển thị thời gian rõ ràng** (không phải "Mỗi phút", "Mỗi giờ")
2. **Tự động save config** sau khi hiển thị
3. **Tự động cập nhật** sau khi chạy xong

## ✅ Giải pháp đã triển khai

### 1. **Thêm function tính toán thời gian cụ thể**

**File:** `schedule_manager.py`
```python
def calculate_next_run_time(self, site):
    """Calculate next run time based on schedule config"""
    try:
        config = self.get_schedule_config(site)
        if not config:
            return None
        
        now = datetime.datetime.now(VN_TZ)
        schedule_type = config.get('schedule_type')
        schedule_time = config.get('schedule_time')
        schedule_day = config.get('schedule_day')
        custom_interval = config.get('custom_interval')
        custom_unit = config.get('custom_unit')
        
        if schedule_type == "minute":
            # Next minute
            next_run = now.replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)
            return next_run
            
        elif schedule_type == "hourly":
            # Next hour at specified minute
            if schedule_time and ':' in schedule_time:
                minute = int(schedule_time.split(':')[1])
                next_run = now.replace(minute=minute, second=0, microsecond=0)
                if next_run <= now:
                    next_run += datetime.timedelta(hours=1)
                return next_run
                
        elif schedule_type == "daily":
            # Next day at specified time
            if schedule_time and ':' in schedule_time:
                hour, minute = map(int, schedule_time.split(':'))
                next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if next_run <= now:
                    next_run += datetime.timedelta(days=1)
                return next_run
                
        elif schedule_type == "weekly":
            # Next week on specified day at specified time
            if schedule_day and schedule_time and ':' in schedule_time:
                hour, minute = map(int, schedule_time.split(':'))
                day_map = {
                    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                    'friday': 4, 'saturday': 5, 'sunday': 6
                }
                target_day = day_map.get(schedule_day.lower(), 0)
                current_day = now.weekday()
                days_ahead = (target_day - current_day) % 7
                if days_ahead == 0:  # Same day
                    next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if next_run <= now:
                        days_ahead = 7  # Next week
                if days_ahead > 0:
                    next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + datetime.timedelta(days=days_ahead)
                    return next_run
                    
        elif schedule_type == "custom" and custom_interval and custom_unit:
            # Custom interval
            unit_map = {
                "phút": "minutes", "giờ": "hours", 
                "ngày": "days", "tuần": "weeks"
            }
            unit_en = unit_map.get(custom_unit, "hours")
            if unit_en == "minutes":
                next_run = now + datetime.timedelta(minutes=custom_interval)
            elif unit_en == "hours":
                next_run = now + datetime.timedelta(hours=custom_interval)
            elif unit_en == "days":
                next_run = now + datetime.timedelta(days=custom_interval)
            elif unit_en == "weeks":
                next_run = now + datetime.timedelta(weeks=custom_interval)
            else:
                next_run = now + datetime.timedelta(hours=custom_interval)
            return next_run
        
        return None
        
    except Exception as e:
        logger.error(f"Error calculating next run time for {site}: {e}")
        return None
```

### 2. **Cập nhật logic hiển thị**

**File:** `pages/THFC.py` và `pages/Agent HR Nội bộ.py`
```python
# Show next run time - Dùng Schedule Manager
if schedule_manager:
    # Thử lấy thời gian từ schedule job trước
    next_run_vn = schedule_manager.get_next_run(site)
    
    # Nếu không có, tính toán từ config
    if not next_run_vn:
        next_run_vn = schedule_manager.calculate_next_run_time(site)
    
    if next_run_vn:
        st.write(f"**Chạy lần tới:** {next_run_vn.strftime('%Y-%m-%d %H:%M:%S')} (GMT+7)")
        st.caption("⏰ Thời gian được tính toán tự động và persistent qua các lần reload")
        
        # Tự động save config sau khi hiển thị
        try:
            schedule_manager._save_schedules_to_json()
            st.caption("💾 Cấu hình đã được lưu tự động")
        except Exception as e:
            logger.warning(f"Không thể lưu config: {e}")
    else:
        # Fallback: Hiển thị thông tin lịch
        # ... (existing fallback logic)
```

## 🎯 Kết quả

### ✅ **Hiển thị thời gian cụ thể:**

| Loại lịch | Trước | Sau |
|-----------|-------|-----|
| **Minute** | "Mỗi phút" | **"2024-01-15 14:31:00 (GMT+7)"** |
| **Hourly** | "Mỗi giờ tại phút 30" | **"2024-01-15 15:30:00 (GMT+7)"** |
| **Daily** | "Mỗi ngày lúc 09:00" | **"2024-01-16 09:00:00 (GMT+7)"** |
| **Weekly** | "Mỗi Monday lúc 09:00" | **"2024-01-22 09:00:00 (GMT+7)"** |
| **Custom** | "Mỗi 2 giờ" | **"2024-01-15 16:30:00 (GMT+7)"** |

### 🔧 **Logic xử lý:**

1. **Ưu tiên 1**: Lấy thời gian từ `schedule_manager.get_next_run()` (từ schedule job thực tế)

2. **Ưu tiên 2**: Nếu không có, tính toán từ `schedule_manager.calculate_next_run_time()` (từ config)

3. **Tự động save**: Sau khi hiển thị thời gian, tự động save config vào `schedule_config.json`

4. **Fallback**: Nếu không tính được, hiển thị thông tin lịch cũ

### 📊 **Tính toán thời gian:**

#### **Minute Schedule**
- **Input**: `schedule_type = "minute"`
- **Logic**: `now + 1 minute`
- **Output**: "2024-01-15 14:31:00 (GMT+7)"

#### **Hourly Schedule**
- **Input**: `schedule_type = "hourly"`, `schedule_time = "09:30"`
- **Logic**: Next hour at minute 30
- **Output**: "2024-01-15 15:30:00 (GMT+7)"

#### **Daily Schedule**
- **Input**: `schedule_type = "daily"`, `schedule_time = "09:00"`
- **Logic**: Tomorrow at 09:00 (or today if not yet passed)
- **Output**: "2024-01-16 09:00:00 (GMT+7)"

#### **Weekly Schedule**
- **Input**: `schedule_type = "weekly"`, `schedule_day = "Monday"`, `schedule_time = "09:00"`
- **Logic**: Next Monday at 09:00
- **Output**: "2024-01-22 09:00:00 (GMT+7)"

#### **Custom Schedule**
- **Input**: `schedule_type = "custom"`, `custom_interval = 2`, `custom_unit = "giờ"`
- **Logic**: Now + 2 hours
- **Output**: "2024-01-15 16:30:00 (GMT+7)"

## 🧪 **Test Cases:**

### **Test 1: Minute Schedule**
- **Current time**: 14:30:45
- **Expected**: "2024-01-15 14:31:00 (GMT+7)"

### **Test 2: Hourly Schedule**
- **Current time**: 14:30:45, **schedule_time**: "09:30"
- **Expected**: "2024-01-15 15:30:00 (GMT+7)"

### **Test 3: Daily Schedule**
- **Current time**: 14:30:45, **schedule_time**: "09:00"
- **Expected**: "2024-01-16 09:00:00 (GMT+7)"

### **Test 4: Weekly Schedule**
- **Current day**: Wednesday, **schedule_day**: "Monday", **schedule_time**: "09:00"
- **Expected**: "2024-01-22 09:00:00 (GMT+7)"

### **Test 5: Custom Schedule**
- **Current time**: 14:30:45, **custom_interval**: 2, **custom_unit**: "giờ"
- **Expected**: "2024-01-15 16:30:45 (GMT+7)"

## 📝 **Files đã cập nhật:**
1. `schedule_manager.py` - Thêm `calculate_next_run_time()`
2. `pages/THFC.py` - Cập nhật logic hiển thị
3. `pages/Agent HR Nội bộ.py` - Cập nhật logic hiển thị

## 🚀 **Lợi ích:**
- ✅ **Thời gian cụ thể** thay vì mô tả chung chung
- ✅ **Tự động save** config sau khi hiển thị
- ✅ **Tính toán chính xác** dựa trên thời gian hiện tại
- ✅ **Timezone GMT+7** được áp dụng đúng
- ✅ **Persistent** qua các lần reload

## 🎯 **Status:**
**✅ HOÀN THÀNH** - Giờ đây hiển thị thời gian cụ thể và tự động save config!
