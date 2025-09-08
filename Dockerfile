# Sử dụng Python 3.11 làm base image
FROM python:3.11-slim

# Thiết lập thư mục làm việc
WORKDIR /app

# Cài đặt các dependencies hệ thống cần thiết
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt trước để tận dụng Docker cache
COPY requirements.txt .

# Cài đặt Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code ứng dụng
COPY . .

# Tạo thư mục để lưu kết quả nếu chưa có
RUN mkdir -p /app/output

# Expose port 8501 (port mặc định của Streamlit)
EXPOSE 8501

# Thiết lập biến môi trường
ENV PYTHONPATH=/app
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Health check để kiểm tra ứng dụng có hoạt động không
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Command để chạy Streamlit
CMD ["streamlit", "run", "single_turn_automation_test.py", "--server.port=8501", "--server.address=0.0.0.0"] 