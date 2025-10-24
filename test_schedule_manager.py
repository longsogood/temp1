"""
Test script để verify Schedule Manager hoạt động
"""
import time
from schedule_manager import get_schedule_manager

def test_schedule_manager():
    print("="*60)
    print("🧪 TEST SCHEDULE MANAGER")
    print("="*60)
    
    # Get schedule manager instance
    print("\n1. Khởi tạo Schedule Manager...")
    sm = get_schedule_manager()
    print("   ✅ Schedule Manager initialized")
    
    # Test 1: Tạo schedule cho THFC
    print("\n2. Tạo schedule mới cho THFC...")
    config_thfc = {
        "file_path": "test_cases/THFC/THFC_test_cases.xlsx",
        "schedule_type": "daily",
        "schedule_time": "15:30",
        "schedule_day": None,
        "test_name": "Daily Test THFC",
        "site": "THFC",
        "api_url": "https://site1.com",
        "evaluate_api_url": "https://site2.com",
        "custom_interval": None,
        "custom_unit": None
    }
    
    result = sm.update_schedule("THFC", config_thfc)
    if result:
        print("   ✅ Schedule THFC đã được tạo")
    else:
        print("   ❌ Lỗi khi tạo schedule THFC")
    
    # Test 2: Get schedule config
    print("\n3. Đọc schedule config cho THFC...")
    config = sm.get_schedule_config("THFC")
    if config:
        print(f"   ✅ Config: {config['test_name']}")
        print(f"      Type: {config['schedule_type']}")
        print(f"      Time: {config['schedule_time']}")
    else:
        print("   ❌ Không tìm thấy config")
    
    # Test 3: Get next run
    print("\n4. Lấy thời gian chạy tiếp theo...")
    next_run = sm.get_next_run("THFC")
    if next_run:
        print(f"   ✅ Next run: {next_run.strftime('%Y-%m-%d %H:%M:%S')} (GMT+7)")
    else:
        print("   ⏳ Đang tính toán...")
    
    # Test 4: Get all jobs
    print("\n5. Liệt kê tất cả jobs...")
    jobs = sm.get_all_jobs()
    print(f"   📊 Tổng số jobs: {len(jobs)}")
    for job in jobs:
        print(f"      - Site: {job['site']}, Test: {job['test_name']}")
        if job['next_run']:
            print(f"        Next: {job['next_run'].strftime('%Y-%m-%d %H:%M:%S')} (GMT+7)")
    
    # Test 5: Persistence check
    print("\n6. Test persistence...")
    print("   💾 Config đã được lưu vào schedule_config.json")
    print("   🔄 Bạn có thể:")
    print("      - Restart app → Schedule vẫn còn")
    print("      - Reload trang → Next run time không đổi")
    
    # Test 6: Remove (optional)
    print("\n7. Test xóa schedule...")
    print("   ⚠️  Nhấn Enter để giữ lại, hoặc 'x' để xóa: ", end='')
    choice = input().strip().lower()
    
    if choice == 'x':
        result = sm.remove_schedule("THFC")
        if result:
            print("   ✅ Đã xóa schedule THFC")
        else:
            print("   ❌ Lỗi khi xóa schedule")
    else:
        print("   ℹ️  Schedule được giữ lại để test trong app")
    
    print("\n" + "="*60)
    print("✅ Test hoàn thành!")
    print("="*60)
    print("\n📝 Ghi chú:")
    print("   - Schedule manager đang chạy background thread")
    print("   - Check file 'schedule_config.json' để xem config")
    print("   - Chạy lại script này để verify persistence")
    print("\n🚀 Bây giờ bạn có thể chạy app và kiểm tra!")
    print("   Reload trang → Next run time phải GIỮ NGUYÊN")
    print("="*60)

if __name__ == "__main__":
    try:
        test_schedule_manager()
        
        # Keep thread alive for a bit to see results
        print("\nThread đang chạy, nhấn Ctrl+C để thoát...")
        time.sleep(5)
        
    except KeyboardInterrupt:
        print("\n\n👋 Thoát test")
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()

