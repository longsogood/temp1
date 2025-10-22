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
    
    **👈 Chọn một demo từ thanh bên** để xem các ví dụ về những gì Streamlit có thể làm!
    
    ### Bạn muốn tìm hiểu thêm?
    
    - Xem tài liệu tại [streamlit.io](https://streamlit.io)
    - Đọc sâu hơn trong [tài liệu của chúng tôi](https://docs.streamlit.io)
    - Đặt câu hỏi trong [diễn đàn cộng đồng](https://discuss.streamlit.io)
"""
)