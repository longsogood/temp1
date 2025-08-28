# 🔍 Trace Analysis Demo

Ứng dụng Streamlit để phân tích và hiển thị trace results từ session ID.

## 🚀 Tính năng

- **Phân tích Trace**: Hiển thị observation cuối cùng của mỗi trace
- **System Prompt**: Hiển thị system prompt của mỗi observation
- **Lịch sử hội thoại**: Xem toàn bộ messages giữa user và assistant
- **Tool Analysis**: Phân tích các tool calls và results
- **Visualization**: Biểu đồ thống kê và phân tích
- **Expander UI**: Mỗi trace được hiển thị dưới dạng expander có thể mở/đóng

## 📋 Cài đặt

1. Cài đặt dependencies:
```bash
pip install -r requirements.txt
```

2. Chạy ứng dụng:
```bash
streamlit run streamlit_demo.py
```

## 🎯 Cách sử dụng

1. Mở trình duyệt và truy cập `http://localhost:8501`
2. Nhập Session ID vào ô input (mặc định đã có sẵn)
3. Nhấn nút "🔍 Phân tích" (sẽ gọi `TokenCounter.get_tracing_result()`)
4. Xem kết quả trong các expander:
   - **🎯 System Prompt**: System prompt của observation
   - **💬 Messages**: Lịch sử hội thoại
   - **📈 Analytics**: Thống kê và biểu đồ
   - **🔧 Tools**: Tool calls và results

## 📊 Cấu trúc dữ liệu

### Trace
- Một lần chat hoàn chỉnh
- Chứa nhiều observations

### Observation
- Các action của LLM trong một lần invoke
- Chứa messages, system prompts, tool calls

### Tool Call
- Lời gọi công cụ từ assistant
- Bao gồm tool name, input parameters

### Tool Result
- Kết quả trả về từ công cụ
- Status và content

## 🎨 Giao diện

- **Responsive Design**: Tương thích với nhiều kích thước màn hình
- **Color-coded Messages**: Phân biệt user, assistant, tool calls
- **Interactive Charts**: Biểu đồ tương tác với Plotly
- **Clean UI**: Giao diện sạch sẽ, dễ sử dụng

## 📁 Files

- `streamlit_demo.py`: Ứng dụng chính
- `requirements.txt`: Dependencies
- `.env`: File cấu hình môi trường (AWS, Langfuse credentials)
- `README.md`: Hướng dẫn sử dụng

## 🔧 Tùy chỉnh

Bạn có thể tùy chỉnh:
- CSS styles trong file `streamlit_demo.py`
- Thêm các biểu đồ phân tích khác
- Mở rộng tính năng export dữ liệu
- Thêm filters và search functionality
- Cấu hình AWS và Langfuse credentials trong file `.env`

## ⚙️ Cấu hình

Tạo file `.env` với các thông tin sau:
```
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=your_aws_region
LANGFUSE_PUBLIC_KEY=your_langfuse_public_key
LANGFUSE_SECRET_KEY=your_langfuse_secret_key
LANGFUSE_HOST=your_langfuse_host
```
