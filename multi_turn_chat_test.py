import streamlit as st
import requests
import json
import time
import pandas as pd
import concurrent.futures
import os
import multiprocessing
from utils import extract_section
from streamlit.runtime.scriptrunner_utils.script_run_context import add_script_run_ctx, get_script_run_ctx
import queue
from uuid import uuid4
from threading import Lock
import warnings
import pickle
warnings.filterwarnings("ignore")

# Khởi tạo session state nếu chưa có
if 'results' not in st.session_state:
    st.session_state.results = None
if 'results_df' not in st.session_state:
    st.session_state.results_df = None
if 'filtered_df' not in st.session_state:
    st.session_state.filtered_df = None
if 'filter_applied' not in st.session_state:
    st.session_state.filter_applied = False

# Hàm callback để lọc kết quả
def filter_results():
    if st.session_state.results_df is not None:
        selected_criterion = st.session_state.selected_criterion
        threshold = st.session_state.threshold
        filter_type = st.session_state.filter_type
        
        # Lọc DataFrame dựa trên tiêu chí đã chọn
        if filter_type == "Lớn hơn hoặc bằng":
            st.session_state.filtered_df = st.session_state.results_df[st.session_state.results_df[selected_criterion] >= threshold]
        else:
            st.session_state.filtered_df = st.session_state.results_df[st.session_state.results_df[selected_criterion] <= threshold]
        
        st.session_state.filter_applied = True

# Cấu hình trang
st.set_page_config(
    page_title="Văn phòng chính phủ Agent Multi-Turn Testing",
    page_icon="🤖",
    layout="wide"
)
GENERAL_PURPOSE_API_URL = st.text_input("GENERAL_PURPOSE_API_URL")
VPCP_API_URL = st.text_input("VPCP_API_URL")

# Tự động xác định số workers tối ưu
CPU_COUNT = multiprocessing.cpu_count()
MAX_WORKERS = min(int(CPU_COUNT * 0.75), 8)  # Sử dụng 75% số CPU cores, nhưng không quá 8 workers
MAX_WORKERS = max(MAX_WORKERS, 2)  # Đảm bảo có ít nhất 2 workers

# Tạo session để tái sử dụng kết nối
session = requests.Session()
session.mount('https://', requests.adapters.HTTPAdapter(
    max_retries=3,
    pool_connections=MAX_WORKERS,
    pool_maxsize=MAX_WORKERS
))

# Load prompts
try:
    # evaluate_prompt = json.load(open("prompts/evaluation/prompt.json", "r"))
    evaluate_system_prompt = open("prompts/evaluation/system_prompt.txt").read()
    evaluate_human_prompt_template = open("prompts/evaluation/system_prompt.txt").read()
except Exception as e:
    st.error(f"Lỗi khi đọc file prompt: {str(e)}")
    st.stop()

# Thêm biến toàn cục để lưu trữ tiến trình
progress_queue = queue.Queue()
progress_lock = Lock()

def update_progress(progress_container, total_questions):
    """Cập nhật tiến trình từ queue"""
    while True:
        try:
            message = progress_queue.get_nowait()
            with progress_container.container():
                if message.startswith("SUCCESS"):
                    st.success(message[7:])
                elif message.startswith("ERROR"):
                    st.error(message[5:])
                else:
                    st.info(message)
        except queue.Empty:
            break

def query_with_retry(url, payload, max_retries=3, delay=1):
    for attempt in range(max_retries):
        try:
            print("Đang gọi API...")
            response = session.post(url, json=payload, timeout=120)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(delay * (attempt + 1))
    return None

def process_chat_session(chat_questions, chat_answers, chat_refs, chat_id, index, total_chats):
    try:
        session_id = str(uuid4())
        chat_results = []
        
        progress_queue.put(f"INFO Bắt đầu xử lý phiên chat {index + 1}/{total_chats} (ID: {chat_id})")
        
        # Xử lý từng câu hỏi trong phiên chat
        for i, (question, true_answer, ref) in enumerate(zip(chat_questions, chat_answers, chat_refs)):
            progress_queue.put(f"INFO Đang xử lý câu hỏi {i + 1}/{len(chat_questions)} trong phiên chat {index + 1}")
            
            # Gửi câu hỏi đến API
            vpcp_response = query_with_retry(VPCP_API_URL,
                                          {"question": question,
                                           "overrideConfig": {
                                               "sessionId": session_id
                                           }})
            if not vpcp_response:
                progress_queue.put(f"ERROR Lỗi khi lấy câu trả lời từ agent cho câu hỏi {i + 1} trong phiên chat {index + 1}")
                continue
                
            vpcp_response = vpcp_response.json()["text"]
            
            # Đánh giá câu trả lời
            evaluate_human_prompt = evaluate_human_prompt_template.format(
                question=question,
                true_answer=true_answer,
                agent_answer=vpcp_response
            )
            
            payload = {
                "question": "Đánh giá câu trả lời từ agent so với câu trả lời chuẩn (true_answer)",
                "overrideConfig": {
                        "systemMessagePrompt": evaluate_system_prompt,
                        "humanMessagePrompt": evaluate_human_prompt
                    }
            }
            
            evaluate_response = query_with_retry(GENERAL_PURPOSE_API_URL, payload)
            if not evaluate_response:
                progress_queue.put(f"ERROR Lỗi khi đánh giá câu trả lời cho câu hỏi {i + 1} trong phiên chat {index + 1}")
                continue
                
            evaluate_response = evaluate_response.json()["text"]
            
            try:
                evaluate_result = extract_section(evaluate_response)
                print(f"Kết quả đánh giá câu hỏi {i + 1} trong phiên chat {index + 1}: {evaluate_result}")
            except Exception as e:
                progress_queue.put(f"ERROR Lỗi khi trích xuất kết quả đánh giá: {str(e)}")
                continue
            
            # Lưu kết quả của câu hỏi
            chat_results.append({
                "session_id": session_id,
                "chat_id": chat_id,
                "question_index": i + 1,
                "question": question,
                "true_answer": true_answer,
                "vpcp_response": vpcp_response,
                "evaluate_result": evaluate_result,
                "ref": ref
            })
            
            progress_queue.put(f"SUCCESS Đã xử lý thành công câu hỏi {i + 1}/{len(chat_questions)} trong phiên chat {index + 1}")
        
        progress_queue.put(f"SUCCESS Đã hoàn thành phiên chat {index + 1}/{total_chats} (ID: {chat_id})")
        return chat_results
    except Exception as e:
        progress_queue.put(f"ERROR Lỗi khi xử lý phiên chat {index + 1}: {str(e)}")
        print(f"Lỗi khi xử lý phiên chat {index + 1}: {str(e)}")
        return []

def process_chat_sessions_batch(chat_sessions):
    all_results = []
    failed_chats = []
    
    # Tạo container cho tiến trình
    progress_container = st.empty()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        
        for i, (chat_id, chat_data) in enumerate(chat_sessions.items()):
            chat_questions = [item["question"] for item in chat_data]
            chat_answers = [item["answer"] for item in chat_data]
            chat_refs = [item["ref"] for item in chat_data]
            
            future = executor.submit(process_chat_session, chat_questions, chat_answers, chat_refs, chat_id, i, len(chat_sessions))
            futures.append(future)
        
        # Hiển thị tiến trình tổng thể
        progress_queue.put(f"Đang xử lý {len(chat_sessions)} phiên chat...")
        
        # Cập nhật tiến trình trong khi chờ kết quả
        while not all(future.done() for future in futures):
            update_progress(progress_container, len(chat_sessions))
            time.sleep(0.1)
        
        # Cập nhật lần cuối
        update_progress(progress_container, len(chat_sessions))
        
        for i, future in enumerate(futures):
            try:
                result = future.result()
                if result:
                    all_results.extend(result)
            except Exception as e:
                st.error(f"Lỗi khi thu thập kết quả từ phiên chat {i + 1}: {str(e)}")
                failed_chats.append((i, str(e)))
    
    return all_results, failed_chats

# Giao diện Streamlit
st.title("🤖 VPCP Agent Multi-Turn Testing")

st.subheader("Test phiên chat từ file Excel")

# Thêm chức năng tải lên file
uploaded_file = st.file_uploader("Chọn file Excel", type=['xlsx', 'xls'])

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        
        # Kiểm tra cấu trúc file Excel
        required_columns = ["chat_script_id", "qa_id", "question", "answer", "ref"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            st.error(f"File Excel thiếu các cột: {', '.join(missing_columns)}")
            st.stop()
        
        # Nhóm dữ liệu theo chat_script_id
        chat_sessions = {}
        for chat_id, group in df.groupby("chat_script_id"):
            chat_sessions[chat_id] = []
            # Sắp xếp theo qa_id để đảm bảo thứ tự đúng
            sorted_group = group.sort_values("qa_id")
            for _, row in sorted_group.iterrows():
                chat_sessions[chat_id].append({
                    "question": row["question"],
                    "answer": row["answer"],
                    "ref": row["ref"]
                })
        
        # Hiển thị danh sách các phiên chat
        st.write(f"Tìm thấy {len(chat_sessions)} phiên chat")
        
        # Tạo DataFrame để hiển thị
        chat_summary = []
        for chat_id, questions in chat_sessions.items():
            chat_summary.append({
                "Chat ID": chat_id,
                "Số câu hỏi": len(questions),
                "Câu hỏi đầu tiên": questions[0]["question"][:100] + "..." if len(questions[0]["question"]) > 100 else questions[0]["question"]
            })
        
        chat_summary_df = pd.DataFrame(chat_summary)
        
        # Hiển thị bảng có thể chọn
        edited_df = st.dataframe(
            chat_summary_df,
            use_container_width=True,
            selection_mode="multi-row",
            on_select="rerun",
            hide_index=True
        )
        
        # Lấy các phiên chat đã chọn
        selected_rows = edited_df['selection']['rows']
        selected_chat_ids = [chat_summary_df.iloc[row]["Chat ID"] for row in selected_rows]
        
        # Tạo dict chỉ chứa các phiên chat đã chọn
        selected_chat_sessions = {chat_id: chat_sessions[chat_id] for chat_id in selected_chat_ids if chat_id in chat_sessions}
        
        if st.button("Test phiên chat"):
            if len(selected_chat_sessions) > 0:
                # Xử lý đa luồng
                results, failed_chats = process_chat_sessions_batch(selected_chat_sessions)
                
                if results:
                    # Lưu kết quả vào session state
                    st.session_state.results = results
                    
                    with open("chat_results.pkl", "wb") as f:
                        pickle.dump(results, f)
                    
                    # Tạo DataFrame từ kết quả
                    data = {
                        'Chat ID': [r["chat_id"] for r in results],
                        'Question Index': [r["question_index"] for r in results],
                        'Question': [r["question"] for r in results],
                        'True Answer': [r["true_answer"] for r in results],
                        'Agent Answer': [r["vpcp_response"] for r in results],
                        'Ref': [r["ref"] for r in results],
                        'Session ID': [r["session_id"] for r in results],
                        'Information Coverage Score': [r["evaluate_result"]["scores"].get("information_coverage", 0) for r in results],
                        'Hallucination Score': [r["evaluate_result"]["scores"].get("hallucination_control", 0) for r in results],
                        'Format Score': [r["evaluate_result"]["scores"].get("format_and_structure", 0) for r in results],
                        'Language Score': [r["evaluate_result"]["scores"].get("language_and_style", 0) for r in results],
                        'Handling Unknown Score': [r["evaluate_result"]["scores"].get("handling_unknown", 0) for r in results],
                        'Average Score': [r["evaluate_result"]["scores"].get("average", 0) for r in results],
                        'Comment': [r["evaluate_result"].get("comments", "") for r in results]
                    }
                    
                    results_df = pd.DataFrame(data)
                    
                    # Lưu DataFrame vào session state
                    st.session_state.results_df = results_df
                    
                    # Hiển thị kết quả
                    st.dataframe(results_df, use_container_width=True)
                    
                    # Thêm nút tải xuống kết quả
                    st.download_button(
                        label="Tải xuống kết quả",
                        data=results_df.to_csv(index=False).encode('utf-8'),
                        file_name='chat_evaluation_results.csv',
                        mime='text/csv'
                    )
                    
                    # Tính điểm trung bình cho mỗi phiên chat
                    chat_avg_scores = results_df.groupby('Chat ID').agg({
                        'Information Coverage Score': 'mean',
                        'Hallucination Score': 'mean',
                        'Format Score': 'mean',
                        'Language Score': 'mean',
                        'Handling Unknown Score': 'mean',
                        'Average Score': 'mean'
                    }).reset_index()
                    
                    st.subheader("Điểm trung bình theo phiên chat")
                    st.dataframe(chat_avg_scores, use_container_width=True)
                    
                    # Thêm phần lọc kết quả theo điểm
                    st.subheader("Lọc kết quả theo điểm")
                    
                    # Sử dụng form để tránh rerun tự động
                    with st.form(key='filter_form'):
                        # Lấy tất cả tiêu chí điểm
                        score_columns = [col for col in results_df.columns if 'Score' in col]
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.selectbox("Chọn tiêu chí điểm", score_columns, key='selected_criterion')
                        with col2:
                            st.slider("Ngưỡng điểm", 0.0, 10.0, 5.0, 0.5, key='threshold')
                        
                        st.radio("Loại lọc", ["Lớn hơn hoặc bằng", "Nhỏ hơn hoặc bằng"], key='filter_type')
                        
                        # Nút submit form
                        submitted = st.form_submit_button("Áp dụng bộ lọc", on_click=filter_results)
                    
                    # Hiển thị kết quả đã lọc nếu đã áp dụng bộ lọc
                    if st.session_state.filter_applied and st.session_state.filtered_df is not None:
                        # Hiển thị kết quả đã lọc
                        st.write(f"Tìm thấy {len(st.session_state.filtered_df)} kết quả phù hợp với bộ lọc")
                        st.dataframe(st.session_state.filtered_df, use_container_width=True)
                        
                        # Tùy chọn xuất kết quả đã lọc
                        st.download_button(
                            label="Tải xuống kết quả đã lọc",
                            data=st.session_state.filtered_df.to_csv(index=False).encode('utf-8'),
                            file_name=f'filtered_chat_results_{st.session_state.selected_criterion}_{st.session_state.threshold}.csv',
                            mime='text/csv'
                        )
                    
                    if failed_chats:
                        st.warning(f"Có {len(failed_chats)} phiên chat xử lý thất bại")
                else:
                    st.error("Không có kết quả từ quá trình xử lý")
            else:
                st.warning("Vui lòng chọn ít nhất một phiên chat để test")
    except Exception as e:
        st.error(f"Lỗi khi đọc file Excel: {str(e)}")
else:
    st.info("Vui lòng tải lên file Excel để bắt đầu")

# Hiển thị hướng dẫn sử dụng
st.sidebar.subheader("Hướng dẫn sử dụng")
st.sidebar.markdown("""
### Test phiên chat
1. Tải lên file Excel chứa dữ liệu phiên chat
2. Chọn các phiên chat muốn test từ bảng
3. Nhấn nút "Test phiên chat" để bắt đầu đánh giá
4. Kết quả sẽ được hiển thị dưới dạng bảng và có thể tải về Excel
5. Bạn có thể xem điểm trung bình theo phiên chat và lọc kết quả theo điểm

### Cấu trúc file Excel
File Excel cần có các cột sau:
- chat_script_id: ID của phiên chat
- qa_id: ID của câu hỏi trong phiên chat
- question: Nội dung câu hỏi
- answer: Câu trả lời chuẩn
- ref: Tham chiếu (nếu có)
""")