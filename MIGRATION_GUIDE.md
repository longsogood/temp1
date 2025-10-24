# 🔄 Migration Guide - Test Cases Management

## ⚠️ QUAN TRỌNG: Đọc trước khi chạy app

Hệ thống đã được cập nhật với logic mới:
- **Mỗi site chỉ có 1 bộ test cases duy nhất**
- **Test cases cũ sẽ KHÔNG tự động hoạt động**

---

## 📋 Bước 1: Backup dữ liệu cũ (Nếu có)

```bash
cd /mnt/c/users/nvlong8/Documents/agents/VPCP_AutoTest

# Backup test cases cũ
cp -r test_cases test_cases_backup_$(date +%Y%m%d)

# Backup scheduled jobs
cp scheduled_tests/scheduled_jobs.pkl scheduled_tests/scheduled_jobs_backup.pkl
```

---

## 📋 Bước 2: Migrate Test Cases

### Option A: Sử dụng script tự động (Khuyến nghị)

```bash
cd /mnt/c/users/nvlong8/Documents/agents/VPCP_AutoTest
conda activate cagent
python migrate_test_cases.py
```

### Option B: Migrate thủ công

1. **Xác định test cases cũ:**
```bash
ls -la test_cases/THFC/
ls -la test_cases/"Agent HR Nội bộ"/
```

2. **Cho mỗi site:**
   - Vào Tab 4 "Quản lý Test Cases"
   - Upload file test cases mới nhất (hoặc merge từ nhiều files cũ)
   - Nhấn "💾 Lưu Test Cases"
   - File sẽ được lưu với tên chuẩn: `{site}_test_cases.xlsx`

---

## 📋 Bước 3: Cập nhật Scheduled Jobs

### Xóa scheduled jobs cũ:

1. Vào Tab 2 "Lập lịch test"
2. Xem cấu hình hiện tại
3. Nhấn "Xóa cấu hình" (jobs cũ sẽ trỏ đến files không tồn tại)

### Tạo scheduled jobs mới:

1. Đảm bảo đã có test cases mới (Bước 2)
2. Vào Tab 2 "Lập lịch test"
3. Cấu hình API URLs
4. Kiểm tra test cases hiện tại (tự động hiện)
5. Đặt tên và thiết lập lịch
6. Nhấn "Thiết lập lịch"

---

## 📋 Bước 4: Kiểm tra

### Test ngay:

```bash
cd /mnt/c/users/nvlong8/Documents/agents/VPCP_AutoTest
conda activate cagent
streamlit run site_selector.py
```

### Checklist:
- [ ] Chọn site "THFC"
- [ ] **Tab 4:** Xem test cases hiện tại (không còn dropdown)
- [ ] **Tab 2:** Kiểm tra lịch test (test cases tự động load)
- [ ] **Tab 1:** Chạy thử 1-2 test cases
- [ ] Lặp lại với site "Agent HR Nội bộ"

---

## 🔧 Script Migration (Tùy chọn)

Tạo file `migrate_test_cases.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script tự động migrate test cases từ format cũ sang mới
"""
import os
import pandas as pd
import glob

# Sites cần migrate
SITES = ["THFC", "Agent HR Nội bộ"]

def migrate_site(site):
    """Migrate test cases cho 1 site"""
    test_cases_dir = os.path.join("test_cases", site)
    
    if not os.path.exists(test_cases_dir):
        print(f"⚠️  Site '{site}' chưa có test cases")
        return
    
    # Tìm tất cả files test cases cũ
    old_files = glob.glob(os.path.join(test_cases_dir, "*.xlsx"))
    old_files = [f for f in old_files if not f.endswith(f"{site}_test_cases.xlsx")]
    
    if not old_files:
        print(f"✅ Site '{site}' không cần migrate")
        return
    
    print(f"\n📂 Site: {site}")
    print(f"   Tìm thấy {len(old_files)} file(s) cũ")
    
    # Lấy file mới nhất (theo thời gian sửa đổi)
    latest_file = max(old_files, key=os.path.getmtime)
    print(f"   ➜ Chọn file mới nhất: {os.path.basename(latest_file)}")
    
    try:
        # Đọc file cũ
        df = pd.read_excel(latest_file)
        print(f"   ✓ Đọc được {len(df)} test cases")
        
        # Lưu vào file mới
        new_file = os.path.join(test_cases_dir, f"{site}_test_cases.xlsx")
        df.to_excel(new_file, index=False)
        print(f"   ✓ Đã lưu vào: {os.path.basename(new_file)}")
        
        # Hỏi có xóa files cũ không
        print(f"\n   ❓ Có muốn xóa {len(old_files)} file(s) cũ? (y/n): ", end="")
        response = input().strip().lower()
        
        if response == 'y':
            for old_file in old_files:
                os.remove(old_file)
                print(f"   🗑️  Đã xóa: {os.path.basename(old_file)}")
            print(f"   ✅ Đã xóa {len(old_files)} file(s) cũ")
        else:
            print(f"   ℹ️  Giữ nguyên files cũ (có thể xóa thủ công sau)")
            
    except Exception as e:
        print(f"   ❌ Lỗi: {str(e)}")

def main():
    print("="*60)
    print("🔄 MIGRATION: Test Cases Management")
    print("="*60)
    print("\nĐang migrate test cases từ format cũ sang mới...")
    print("Mỗi site sẽ chỉ còn 1 file duy nhất: {site}_test_cases.xlsx")
    
    for site in SITES:
        migrate_site(site)
    
    print("\n" + "="*60)
    print("✅ HOÀN TẤT!")
    print("="*60)
    print("\n📝 Các bước tiếp theo:")
    print("   1. Kiểm tra test cases trong Tab 4")
    print("   2. Cập nhật scheduled jobs trong Tab 2")
    print("   3. Test thử trong Tab 1")
    print("\n💡 Xem file MIGRATION_GUIDE.md để biết thêm chi tiết")

if __name__ == "__main__":
    main()
```

**Chạy script:**
```bash
chmod +x migrate_test_cases.py
python migrate_test_cases.py
```

---

## 🆘 Troubleshooting

### Problem 1: "Chưa có test cases cho site này"
**Giải pháp:** Upload test cases mới trong Tab 4

### Problem 2: Scheduled job không chạy
**Giải pháp:** 
1. Xóa scheduled job cũ
2. Đảm bảo có test cases mới
3. Tạo lại scheduled job

### Problem 3: File test cases cũ vẫn còn
**Giải pháp:** 
```bash
# Xóa thủ công (sau khi backup)
cd test_cases/THFC/
ls -la
# Xóa files KHÔNG phải THFC_test_cases.xlsx
rm Test_Cases_*.xlsx
```

### Problem 4: Import error sau khi cập nhật
**Giải pháp:**
```bash
cd /mnt/c/users/nvlong8/Documents/agents/VPCP_AutoTest
conda activate cagent
python -m py_compile pages/THFC.py pages/"Agent HR Nội bộ.py"
```

---

## 📊 So sánh Format

### Format CŨ:
```
test_cases/
├── THFC/
│   ├── Test_Cases_1_20251024_100000.xlsx  ❌
│   ├── Test_Cases_2_20251024_110000.xlsx  ❌
│   └── Test_Cases_3_20251024_120000.xlsx  ❌
└── Agent HR Nội bộ/
    ├── HR_Cases_20251024_120000.xlsx  ❌
    └── Test_20251024_130000.xlsx  ❌
```

### Format MỚI:
```
test_cases/
├── THFC/
│   └── THFC_test_cases.xlsx  ✅ DUY NHẤT
└── Agent HR Nội bộ/
    └── Agent HR Nội bộ_test_cases.xlsx  ✅ DUY NHẤT
```

---

## ✅ Kết luận

Sau khi hoàn thành migration:
- ✅ Mỗi site có 1 file test cases duy nhất
- ✅ Scheduled jobs hoạt động bình thường
- ✅ Có thể xóa an toàn test cases cũ (sau khi backup)
- ✅ Hệ thống đơn giản và dễ quản lý hơn

---

**Cần hỗ trợ?** Xem file `SITE_MANAGEMENT_IMPROVEMENTS.md` để biết chi tiết kỹ thuật.

**Ngày cập nhật:** 2025-10-24

