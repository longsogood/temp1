#!/bin/bash

# Script để test các tab đã được cải thiện

echo "🚀 Khởi động VPCP AutoTest..."
echo ""
echo "📋 Hướng dẫn test:"
echo "  1. Đợi app khởi động (mở tự động trong browser)"
echo "  2. Chọn site 'THFC' hoặc 'Agent HR Nội bộ' từ sidebar"
echo "  3. Click vào Tab 3 'Quản lý test' → Xem empty state mới"
echo "  4. Click vào Tab 4 'Quản lý Test Cases' → Cuộn xuống xem empty state"
echo "  5. Tab 5 luôn có nội dung nên không có vấn đề"
echo ""
echo "✨ Bạn sẽ thấy:"
echo "  - Dashboard placeholder đẹp mắt với gradient"
echo "  - Hướng dẫn chi tiết 5 bước"
echo "  - Tips và lợi ích được highlight"
echo "  - Không còn cảm giác 'trống' nữa!"
echo ""
echo "---"
echo ""

cd /mnt/c/users/nvlong8/Documents/agents/VPCP_AutoTest
conda activate cagent
streamlit run site_selector.py

