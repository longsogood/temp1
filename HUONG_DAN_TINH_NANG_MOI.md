# 📚 Hướng Dẫn Các Tính Năng Mới

## 🎉 Tóm tắt các cập nhật

Hệ thống AutoTest đã được cập nhật với nhiều tính năng mới giúp tester làm việc hiệu quả hơn:

---

## 1. ⚙️ Quản lý Sites

### Tính năng:
- **Thêm Site mới**: Tạo site mới với cấu trúc hoàn chỉnh tự động
- **Xóa Site**: Xóa site không cần thiết (giữ lại dữ liệu test)
- **Clone từ HR Nội bộ**: Mỗi site mới được copy từ template HR Nội bộ

### Cách sử dụng:
1. Vào trang **"Quản lý Sites"** trên menu sidebar
2. Để thêm site mới:
   - Nhập tên site (ví dụ: "Agent Marketing")
   - Nhấn "➕ Thêm Site"
   - Refresh trang để thấy site mới trong menu
3. Để xóa site:
   - Chọn site từ dropdown
   - Nhấn "🗑️ Xóa Site"
   - Dữ liệu test sẽ được giữ lại

### Lưu ý:
- Không thể xóa 2 site mặc định: "Agent HR Nội bộ" và "THFC"
- Site mới sẽ có đầy đủ cấu trúc thư mục và file template
- Cần refresh trang sau khi thêm/xóa site

---

## 2. 📝 Chỉnh sửa Test Cases trên UI

### Tính năng:
- **Edit trực tiếp**: Click vào ô để chỉnh sửa câu hỏi và câu trả lời
- **Thêm/Xóa dòng**: Có thể thêm test case mới hoặc xóa test case cũ
- **Checkbox chọn**: Tick vào cột "Chọn" để chọn test case muốn chạy
- **Lưu tự động**: Các thay đổi được lưu trong session

### Cách sử dụng:
1. Vào tab **"Test hàng loạt"**
2. Upload file Excel như bình thường
3. Bảng test cases sẽ hiển thị với khả năng chỉnh sửa:
   - Click vào ô bất kỳ để sửa nội dung
   - Tick ✓ vào cột "Chọn" để chọn test case
   - Untick để bỏ qua test case không muốn chạy
4. Nhấn "▶️ Chạy test" để chạy các test case đã chọn

### Lợi ích:
- Không cần sửa file Excel
- Nhanh chóng điều chỉnh test case
- Linh hoạt chọn test case để chạy

---

## 3. 🎯 Cấu hình Tiêu chí Fail

### Tính năng:
- **Chọn tiêu chí**: accuracy, relevance, completeness, clarity, tone, average
- **Điều chỉnh ngưỡng**: Từ 0 đến 10, mặc định là 8.0
- **Áp dụng toàn cục**: Tất cả test sẽ sử dụng cấu hình này

### Cách sử dụng:
1. Mở expander **"⚙️ Cấu hình API và các tham số"**
2. Trong phần "Tiêu chí đánh giá fail":
   - Chọn tiêu chí từ dropdown (mặc định: accuracy)
   - Nhập ngưỡng fail (mặc định: 8.0)
3. Xem tóm tắt: "Fail nếu **accuracy** < 8.0"

### Ví dụ:
- `accuracy < 8.0`: Test fail nếu độ chính xác < 8/10
- `completeness < 7.0`: Test fail nếu tính đầy đủ < 7/10
- `average < 8.5`: Test fail nếu điểm trung bình < 8.5/10

### Lưu ý:
- Cấu hình này áp dụng cho tất cả test trong session
- Có thể thay đổi bất cứ lúc nào
- Ảnh hưởng đến cả test đơn lẻ và test hàng loạt

---

## 4. 🎨 Cải thiện Giao diện

### Các cải tiến:
1. **Layout 2 cột**: Câu hỏi và câu trả lời hiển thị song song
2. **Icons rõ ràng**: Mỗi phần có icon phân biệt
3. **Buttons đẹp hơn**: Nút "Chạy test" nổi bật, dễ nhìn
4. **Metrics trực quan**: Hiển thị thống kê bằng st.metric
5. **Expander cho settings**: Thu gọn các phần cấu hình

### Cải tiến cụ thể:

#### Tab 1 - Test đơn lẻ:
- Layout 2 cột cho input
- Button "▶️ Chạy Test" căn giữa
- Kết quả hiển thị với metrics đẹp
- Phân chia rõ ràng giữa câu trả lời và điểm

#### Tab 2 - Test hàng loạt:
- File uploader với status indicator
- Data editor với cấu hình column rõ ràng
- Metrics tổng quan: Tổng/Chọn/Passed/Failed
- Button actions căn đều
- Kết quả hiển thị với charts và metrics

#### Cấu hình:
- Layout 2 cột: API settings vs Test settings
- Fail criteria riêng biệt với 3 cột
- Tóm tắt cấu hình trực quan

---

## 📊 So sánh Trước & Sau

### Trước:
- ❌ Chỉ có 2 sites cố định
- ❌ Không thể edit test cases trên UI
- ❌ Tiêu chí fail hardcode (accuracy < 8)
- ❌ Layout lộn xộn, khó nhìn

### Sau:
- ✅ Thêm/xóa sites dễ dàng
- ✅ Edit test cases trực tiếp trên UI
- ✅ Điều chỉnh tiêu chí fail linh hoạt
- ✅ Layout đẹp, căn chỉnh tốt, dễ sử dụng

---

## 🚀 Hướng dẫn Bắt đầu

### Bước 1: Chạy ứng dụng
```bash
streamlit run site_selector.py
```

### Bước 2: Tạo Site mới (nếu cần)
1. Vào "Quản lý Sites"
2. Thêm site mới
3. Refresh trang

### Bước 3: Cấu hình tiêu chí fail
1. Mở expander "⚙️ Cấu hình"
2. Chọn tiêu chí và ngưỡng
3. Đóng expander

### Bước 4: Chạy test
#### Test đơn lẻ:
1. Nhập câu hỏi và câu trả lời
2. Nhấn "▶️ Chạy Test"

#### Test hàng loạt:
1. Upload file Excel
2. Edit test cases nếu cần
3. Tick chọn test cases
4. Nhấn "▶️ Chạy test"

---

## ❓ FAQ

**Q: Site mới có sẵn prompts không?**  
A: Có, site mới tự động copy prompts từ "Agent HR Nội bộ"

**Q: Có thể xóa 2 site mặc định không?**  
A: Không, "Agent HR Nội bộ" và "THFC" được bảo vệ

**Q: Dữ liệu test có bị mất khi xóa site không?**  
A: Không, dữ liệu trong `test_results` được giữ lại

**Q: Thay đổi tiêu chí fail có ảnh hưởng đến test cũ không?**  
A: Không, chỉ ảnh hưởng đến test mới chạy từ thời điểm đó

**Q: Có thể lưu test cases đã edit không?**  
A: Hiện tại chỉ lưu trong session, cần download về nếu muốn giữ lâu dài

---

## 📞 Hỗ trợ

Nếu gặp vấn đề, vui lòng:
1. Kiểm tra logs trong thư mục `logs/`
2. Xem lại hướng dẫn trong sidebar
3. Liên hệ team phát triển

---

**Phiên bản**: 2.0  
**Ngày cập nhật**: 2025-10-22  
**Người phát triển**: AI Assistant

