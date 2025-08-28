# 🔍 Trace Analysis Demo

Ứng dụng Streamlit để phân tích và hiển thị trace results từ session ID.

## 🚀 Tính năng

- **Phân tích Trace**: Hiển thị observation cuối cùng của mỗi trace
- **System Prompt**: Hiển thị system prompt của mỗi observation (có thể expand)
- **Lịch sử hội thoại**: Xem toàn bộ messages giữa user và assistant (có thể expand)
- **Tool Analysis**: Phân tích các tool calls và results
- **Token Analysis**: Tính toán và hiển thị số lượng input tokens
- **Session Comparison**: So sánh 2 session để phân tích hiệu quả memory
- **Visualization**: Biểu đồ thống kê và phân tích tokens
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

### Phân tích đơn session:
1. Mở trình duyệt và truy cập `http://localhost:8501`
2. Chọn "Phân tích đơn" trong sidebar
3. Nhập Session ID vào ô input (mặc định đã có sẵn)
4. Nhấn nút "🔍 Phân tích" (sẽ gọi `TokenCounter.get_tracing_result()`)
5. Xem kết quả trong các expander:
   - **🎯 System Prompt**: System prompt của observation (có thể expand)
   - **💬 Messages**: Lịch sử hội thoại (có thể expand)
   - **📈 Analytics**: Thống kê và biểu đồ
   - **🔧 Tools**: Tool calls và results
   - **🎯 Tokens**: Phân tích tokens cho từng observation

### So sánh 2 session:
1. Chọn "So sánh 2 session" trong sidebar
2. Nhập Session ID 1 (ví dụ: không có memory)
3. Nhập Session ID 2 (ví dụ: có memory)
4. Đặt nhãn cho từng session
5. Nhấn "🔄 So sánh"
6. Xem biểu đồ so sánh tokens và chi tiết từng session

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

### Token Analysis
- Tính toán số lượng input tokens cho mỗi observation
- Biểu đồ phân tích tokens theo trace và observation
- Thống kê tổng quan về token usage

### Session Comparison
- So sánh tokens giữa 2 session
- Biểu đồ so sánh tokens theo trace
- Phân tích chênh lệch để đánh giá hiệu quả memory

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
