# Original Prompts - Thư mục chứa Prompts & Extract Sections mặc định

## Mục đích

Thư mục này chứa các file prompt và extract sections **gốc/mặc định** được sử dụng cho tất cả các site mới.

## Cấu trúc

```
original_prompts/
├── system_prompt.txt       # System prompt mặc định cho LLM đánh giá
├── human_prompt.txt        # Human prompt template mặc định
├── extract_sections.py     # Code extract sections mặc định
└── README.md              # File này
```

## Cách hoạt động

### 1. Khi tạo site mới

Khi một site mới được tạo (hoặc lần đầu tiên truy cập), hệ thống sẽ:
- Kiểm tra xem folder `prompts/<site_name>/` có tồn tại không
- Nếu **KHÔNG tồn tại**, tự động copy các file từ `original_prompts/` sang `prompts/<site_name>/`
- Tương tự cho `utils/<site_name>/extract_sections.py`

### 2. Khi reset prompts

Khi người dùng nhấn nút **"🔄 Reset Prompts"** hoặc **"🔄 Reset Extract Code"**:
- Hệ thống sẽ copy lại các file từ `original_prompts/` sang folder của site đang chọn
- Điều này giúp khôi phục về cấu hình gốc nếu có chỉnh sửa sai

### 3. Khi chỉnh sửa prompts cho site

- Mỗi site có folder riêng: `prompts/<site_name>/`
- Chỉnh sửa trên UI sẽ lưu vào folder của site đó
- **KHÔNG ảnh hưởng** đến `original_prompts/` hay các site khác

## Files mô tả

### system_prompt.txt

Chứa system prompt cho LLM đánh giá, bao gồm:
- Vai trò của LLM (chuyên gia đánh giá)
- Các tiêu chí đánh giá: Relevance, Accuracy, Completeness, Clarity, Tone
- Hướng dẫn đánh giá chi tiết
- Format output (JSON)

### human_prompt.txt

Template cho human prompt, sử dụng placeholders:
- `{question}`: Câu hỏi từ user
- `{true_answer}`: Câu trả lời chuẩn/mẫu
- `{agent_answer}`: Câu trả lời từ agent
- (Site THFC có thêm: `{level}`, `{department}`)

### extract_sections.py

Code Python để extract kết quả đánh giá từ response của LLM, bao gồm:
- Hàm `extract_json()`: Trích xuất JSON từ response text
- Hàm `extract_section()`: Parse JSON và trả về dict với `scores` và `comments`
- Các tiêu chí mặc định: relevance, accuracy, completeness, clarity, tone

## Lưu ý quan trọng

1. **Không nên chỉnh sửa trực tiếp các file trong `original_prompts/`** khi đang test
   - Chỉ chỉnh sửa khi muốn thay đổi cấu hình mặc định cho **TẤT CẢ** site mới trong tương lai

2. **Backup trước khi thay đổi**
   - Nên backup các file này trước khi thay đổi để có thể khôi phục

3. **Đồng bộ giữa system_prompt.txt và extract_sections.py**
   - Các tiêu chí trong `system_prompt.txt` phải khớp với các field trong `extract_sections.py`
   - Ví dụ: Nếu thêm tiêu chí mới "empathy" trong system prompt, cần thêm vào extract_sections

4. **Sử dụng tính năng Auto-generate**
   - Trong tab "Quản lý Prompts", có thể dùng nút "💾 Lưu Extract Code" để tự động tạo extract code từ system prompt
   - Điều này đảm bảo sự đồng bộ giữa system prompt và extract code

## Ví dụ workflow

### Tạo site mới "MyNewSite"

1. Tạo file `pages/MyNewSite.py` (copy từ THFC.py hoặc Agent HR Nội bộ.py)
2. Thay đổi `SITE = "MyNewSite"` trong file
3. Khi chạy lần đầu, hệ thống tự động tạo:
   - `prompts/MyNewSite/system_prompt.txt` (copy từ `original_prompts/system_prompt.txt`)
   - `prompts/MyNewSite/human_prompt.txt` (copy từ `original_prompts/human_prompt.txt`)
   - `utils/MyNewSite/extract_sections.py` (copy từ `original_prompts/extract_sections.py`)

### Chỉnh sửa prompts cho site cụ thể

1. Vào tab "Quản lý Prompts" của site đó
2. Chỉnh sửa System Prompt và Human Prompt
3. Nhấn "💾 Lưu Prompts"
4. Nếu muốn reset về mặc định: Nhấn "🔄 Reset Prompts"

## Bảo trì

- **Thường xuyên backup**: Backup folder `original_prompts/` định kỳ
- **Version control**: Nên commit các thay đổi vào Git
- **Testing**: Test kỹ trước khi thay đổi `original_prompts/` vì ảnh hưởng đến tất cả site mới

## Liên hệ

Nếu có thắc mắc hoặc cần hỗ trợ, vui lòng liên hệ team phát triển.

