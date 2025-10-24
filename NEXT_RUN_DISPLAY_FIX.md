# Sửa lỗi "Chạy lần tới: Đang tính toán..." - Hiển thị thông tin lịch ngay lập tức

## 🐛 Vấn đề gốc
```
Chạy lần tới: Đang tính toán...
```

**Nguyên nhân:** `schedule_manager.get_next_run()` trả về `None` hoặc có lỗi, khiến hiển thị "Đang tính toán..." thay vì thông tin lịch thực tế.

## ✅ Giải pháp

### **Trước khi sửa:**
```python
if schedule_manager:
    next_run_vn = schedule_manager.get_next_run(site)
    if next_run_vn:
        st.write(f"**Chạy lần tới:** {next_run_vn.strftime('%Y-%m-%d %H:%M:%S')} (GMT+7)")
        st.caption("⏰ Thời gian được tính toán tự động và persistent qua các lần reload")
    else:
        st.write(f"**Chạy lần tới:** Đang tính toán...")  # ❌ Không hữu ích
```

### **Sau khi sửa:**
```python
if schedule_manager:
    next_run_vn = schedule_manager.get_next_run(site)
    if next_run_vn:
        st.write(f"**Chạy lần tới:** {next_run_vn.strftime('%Y-%m-%d %H:%M:%S')} (GMT+7)")
        st.caption("⏰ Thời gian được tính toán tự động và persistent qua các lần reload")
    else:
        # ✅ Hiển thị thông tin lịch thay vì "Đang tính toán"
        schedule_type = existing_job.get('schedule_type', 'N/A')
        schedule_time = existing_job.get('schedule_time', 'N/A')
        schedule_day = existing_job.get('schedule_day', 'N/A')
        
        if schedule_type == "minute":
            st.write(f"**Chạy lần tới:** Mỗi phút")
        elif schedule_type == "hourly":
            st.write(f"**Chạy lần tới:** Mỗi giờ tại phút {schedule_time.split(':')[1] if ':' in schedule_time else '00'}")
        elif schedule_type == "daily":
            st.write(f"**Chạy lần tới:** Mỗi ngày lúc {schedule_time}")
        elif schedule_type == "weekly":
            st.write(f"**Chạy lần tới:** Mỗi {schedule_day} lúc {schedule_time}")
        elif schedule_type == "custom":
            interval = existing_job.get('custom_interval', 'N/A')
            unit = existing_job.get('custom_unit', 'N/A')
            st.write(f"**Chạy lần tới:** Mỗi {interval} {unit}")
        else:
            st.write(f"**Chạy lần tới:** {schedule_type} - {schedule_time}")
```

## 🎯 Kết quả

### ✅ **Hiển thị thông tin lịch ngay lập tức:**

| Loại lịch | Hiển thị trước | Hiển thị sau |
|-----------|----------------|--------------|
| **Minute** | "Đang tính toán..." | **"Mỗi phút"** |
| **Hourly** | "Đang tính toán..." | **"Mỗi giờ tại phút 30"** |
| **Daily** | "Đang tính toán..." | **"Mỗi ngày lúc 09:00"** |
| **Weekly** | "Đang tính toán..." | **"Mỗi Monday lúc 09:00"** |
| **Custom** | "Đang tính toán..." | **"Mỗi 2 giờ"** |

### 🔧 **Logic xử lý:**

1. **Ưu tiên 1**: Nếu `schedule_manager.get_next_run()` trả về thời gian cụ thể → Hiển thị thời gian chính xác (GMT+7)

2. **Ưu tiên 2**: Nếu không có thời gian cụ thể → Hiển thị thông tin lịch từ config:
   - **Minute**: "Mỗi phút"
   - **Hourly**: "Mỗi giờ tại phút XX"
   - **Daily**: "Mỗi ngày lúc HH:MM"
   - **Weekly**: "Mỗi [Day] lúc HH:MM"
   - **Custom**: "Mỗi X [unit]"

3. **Fallback**: Nếu không có thông tin → Hiển thị "N/A"

## 📊 **Lợi ích:**

### ✅ **Trước khi sửa:**
- ❌ "Đang tính toán..." không cung cấp thông tin hữu ích
- ❌ User không biết lịch sẽ chạy như thế nào
- ❌ Cần reload nhiều lần để thấy thông tin

### ✅ **Sau khi sửa:**
- ✅ **Hiển thị ngay lập tức** thông tin lịch
- ✅ **Không cần reload** để thấy thông tin
- ✅ **Thông tin rõ ràng** về tần suất chạy
- ✅ **User-friendly** - dễ hiểu hơn

## 🧪 **Test Cases:**

### **Test 1: Minute Schedule**
- **Input**: `schedule_type = "minute"`
- **Expected**: "**Chạy lần tới:** Mỗi phút"

### **Test 2: Hourly Schedule**
- **Input**: `schedule_type = "hourly"`, `schedule_time = "09:30"`
- **Expected**: "**Chạy lần tới:** Mỗi giờ tại phút 30"

### **Test 3: Daily Schedule**
- **Input**: `schedule_type = "daily"`, `schedule_time = "09:00"`
- **Expected**: "**Chạy lần tới:** Mỗi ngày lúc 09:00"

### **Test 4: Weekly Schedule**
- **Input**: `schedule_type = "weekly"`, `schedule_day = "Monday"`, `schedule_time = "09:00"`
- **Expected**: "**Chạy lần tới:** Mỗi Monday lúc 09:00"

### **Test 5: Custom Schedule**
- **Input**: `schedule_type = "custom"`, `custom_interval = 2`, `custom_unit = "giờ"`
- **Expected**: "**Chạy lần tới:** Mỗi 2 giờ"

## 📝 **Files đã cập nhật:**
1. `pages/THFC.py` - Cập nhật logic hiển thị "Chạy lần tới"
2. `pages/Agent HR Nội bộ.py` - Cập nhật logic hiển thị "Chạy lần tới"

## 🚀 **Status:**
**✅ HOÀN THÀNH** - Không còn hiển thị "Đang tính toán...", thay vào đó hiển thị thông tin lịch ngay lập tức!
