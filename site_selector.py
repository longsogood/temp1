import streamlit as st

st.set_page_config(
    page_title="AutoTest - Trang chủ",
    page_icon="🏠",
)

st.title("Chào mừng đến với VPCP AutoTest! 👋")

st.sidebar.success("Chọn một trang demo ở trên.")

st.markdown(
    """
    Đây là công cụ tự động kiểm thử cho các Agent của VPCP.
    
    **👈 Chọn một site từ thanh bên** để bắt đầu testing!
    
    ### 🎉 Tính năng mới (v2.0):
    
    - ⚙️ **Quản lý Sites**: Thêm/xóa sites mới dễ dàng
    - 📝 **Edit Test Cases trên UI**: Chỉnh sửa trực tiếp không cần Excel
    - 🎯 **Cấu hình tiêu chí fail**: Điều chỉnh linh hoạt (accuracy, relevance, etc.)
    - 🎨 **Giao diện đẹp hơn**: Layout căn chỉnh, dễ nhìn, dễ dùng
    
    ### 📚 Hướng dẫn chi tiết:
    
    - Xem file [HUONG_DAN_TINH_NANG_MOI.md](./HUONG_DAN_TINH_NANG_MOI.md)
    - Hoặc xem hướng dẫn trong mỗi tab của ứng dụng
    
    ### 🚀 Bắt đầu nhanh:
    
    1. **Quản lý Sites**: Tạo site mới cho dự án của bạn
    2. **Test đơn lẻ**: Test nhanh 1 câu hỏi
    3. **Test hàng loạt**: Upload Excel và chạy nhiều test cùng lúc
    4. **Lập lịch test**: Tự động chạy test theo lịch
    5. **Quản lý test**: Xem lịch sử và phân tích kết quả
"""
)