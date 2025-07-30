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
    page_title="VPCP Agent Testing",
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
    evaluate_human_prompt_template = open("prompts/evaluation/human_prompt.txt").read()
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
            response = session.post(url, json=payload, timeout=120, verify=False)
            response.raise_for_status()
            # print("Gọi VPCP API thành công: ", response.json())
            return response
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(delay * (attempt + 1))
    return None

def process_single_question(question, true_answer, index, total_questions):
    try:
        chat_id = str(uuid4())
        vpcp_resposne = query_with_retry(VPCP_API_URL,
                                        {"question": question.replace("ACL", "ACL - Khách hàng cá nhân"),
                                         "overrideConfig": {
                                             "sessionId": chat_id
                                         }})
        if not vpcp_resposne:
            progress_queue.put(f"ERROR Lỗi khi lấy câu trả lời từ agent cho câu hỏi {index + 1}")
            return None
        vpcp_resposne = vpcp_resposne.json()["text"]
        
        evaluate_human_prompt = evaluate_human_prompt_template.format(
            question=question,
            true_answer=true_answer.replace("ACL", "ACL - Khách hàng cá nhân"),
            agent_answer=vpcp_resposne
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
            progress_queue.put(f"ERROR Lỗi khi đánh giá câu trả lời cho câu hỏi {index + 1}")
            print(f"Lỗi khi đánh giá câu trả lời cho câu hỏi {index + 1}: {str(e)}")
            return None
        try:
            evaluate_response = evaluate_response.json()["text"]
        except Exception as e:
            print(f"Lỗi khi lấy response: {evaluate_response.json()}")
        try:
            evaluate_result = extract_section(evaluate_response)
            print(f"Kết quả đánh giá câu hỏi {index + 1}: {evaluate_result}")
        except Exception as e:
            st.error(f"Lỗi khi trích xuất kết quả đánh giá: {str(e)}")
            print(f"Lỗi khi trích xuất kết quả đánh giá: {str(e)}")
            return None
        
        progress_queue.put(f"SUCCESS Đã xử lý thành công câu hỏi {index + 1}/{total_questions}")
        print(f"Đã xử lý thành công câu hỏi {index + 1}/{total_questions}: {evaluate_result}")
        return {
            "chat_id": chat_id,
            "question": question,
            "true_answer": true_answer,
            "vpcp_response": vpcp_resposne,
            "evaluate_result": evaluate_result,
            # "ref": ref
        }
    except Exception as e:
        progress_queue.put(f"ERROR Lỗi khi xử lý câu hỏi {index + 1}: {str(e)}")
        print(f"Lỗi khi xử lý câu hỏi {index + 1}: {str(e)}")
        return None

def process_questions_batch(questions, true_answers):
    results = []
    failed_questions = []
    
    # Tạo container cho tiến trình
    progress_container = st.empty()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for i, (question, true_answer) in enumerate(zip(questions, true_answers)):
            future = executor.submit(process_single_question, question, true_answer, i, len(questions))
            futures.append(future)
        
        # Hiển thị tiến trình tổng thể
        progress_queue.put(f"Đang xử lý {len(questions)} câu hỏi...")
        
        # Cập nhật tiến trình trong khi chờ kết quả
        while not all(future.done() for future in futures):
            update_progress(progress_container, len(questions))
            time.sleep(0.1)
        
        # Cập nhật lần cuối
        update_progress(progress_container, len(questions))
        
        for future in futures:
            try:
                result = future.result()
                if result:
                    print("Cập nhật kết quả...")
                    results.append(result)
            except Exception as e:
                st.error(f"Lỗi khi thu thập kết quả: {str(e)}")
                failed_questions.append((question, str(e)))
    
    return results, failed_questions


# Giao diện Streamlit
st.title("🤖 VPCP Agent Testing")

# Tạo các tab
tab1, tab2 = st.tabs(["Test đơn lẻ", "Test hàng loạt"])

with tab1:
    st.subheader("Nhập câu hỏi và câu trả lời chuẩn")
    question = st.text_area("Câu hỏi:", height=100)
    true_answer = st.text_area("Câu trả lời chuẩn:", height=200)
    
    if st.button("Test"):
        if question and true_answer:
            progress_container = st.empty()
            progress_container.text("Đang xử lý...")
            result = process_single_question(question, true_answer, 0, 1)
            
            if result:
                progress_container.success("Xử lý thành công!")
                
                # Hiển thị kết quả
                st.subheader("Kết quả")
                st.write("**Câu trả lời từ VPCP Agent:**")
                st.write(result["vpcp_response"])
                
                st.write("**Đánh giá:**")
                scores = result["evaluate_result"]["scores"]
                for metric, score in scores.items():
                    st.write(f"- {metric}: {score}")
                
                st.write("**Nhận xét và góp ý cải thiện:**")
                st.write(result["evaluate_result"]["Nhận xét và góp ý cải thiện"])
        else:
            st.warning("Vui lòng nhập cả câu hỏi và câu trả lời chuẩn")

with tab2:
    st.subheader("Test hàng loạt từ file Excel")
    
    # Thêm chức năng tải lên file
    uploaded_file = st.file_uploader("Chọn file Excel", type=['xlsx', 'xls'])
    
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            if len(df.columns) < 2:
                st.error("File Excel phải có ít nhất 2 cột: câu hỏi và câu trả lời chuẩn")
                st.stop()
                
            questions = df.iloc[:, 0].tolist()
            true_answers = df.iloc[:, 1].tolist()
            # refs = df.iloc[:,2].tolist()
            
            # Làm sạch DataFrame: loại bỏ các hàng có cell là null
            clean_df = df.dropna(subset=[df.columns[0], df.columns[1]])
            questions = clean_df.iloc[:, 0].tolist()
            true_answers = clean_df.iloc[:, 1].tolist()
            # refs = clean_df.iloc[:,2].tolist()
            
            # Tạo DataFrame để hiển thị
            display_df = pd.DataFrame({
                'Câu hỏi': questions,
                'Câu trả lời chuẩn': true_answers,
                # 'Refs': refs
            })
            
            # Hiển thị bảng có thể chỉnh sửa
            edited_df = st.dataframe(
                display_df,
                use_container_width=True,
                selection_mode="multi-row",
                on_select="rerun",
                hide_index=True
            )
            
            # Lấy các câu hỏi đã chọn
            selected_rows = edited_df['selection']['rows']
            selected_questions = display_df.loc[selected_rows, 'Câu hỏi'].tolist()
            selected_true_answers = display_df.loc[selected_rows, 'Câu trả lời chuẩn'].tolist()
            # selected_refs = display_df.loc[selected_rows, 'Refs'].tolist()
            
            if st.button("Test hàng loạt"):
                if len(selected_questions) > 0:
                    # Xử lý đa luồng
                    results, failed_questions = process_questions_batch(selected_questions, selected_true_answers)
                    print("Đã xử lý đa luồng")
                    if results:
                        # Lưu kết quả vào session state
                        st.session_state.results = results
                        
                        with open("results.pkl", "wb") as f:
                            pickle.dump(results, f)
                        # Tạo DataFrame từ kết quả
                        data = {
                            'Question': [r["question"] for r in results],
                            'True Answer': [r["true_answer"] for r in results],
                            'Agent Answer': [r["vpcp_response"] for r in results],
                            # 'Ref': [r["ref"] for r in results],
                            'Session ID': [r["chat_id"] for r in results],
                            'Relevance Score': [r["evaluate_result"]["scores"].get("relevance", 0) for r in results],
                            'Accuracy Score': [r["evaluate_result"]["scores"].get("accuracy", 0) for r in results],
                            'Completeness Score': [r["evaluate_result"]["scores"].get("completeness", 0) for r in results],
                            'Clarity Score': [r["evaluate_result"]["scores"].get("clarity", 0) for r in results],
                            'Tone Score': [r["evaluate_result"]["scores"].get("tone", 0) for r in results],
                            'Average Score': [r["evaluate_result"]["scores"].get("average", 0) for r in results],
                            'Comment': [r["evaluate_result"].get("comments", "") for r in results]
                        }
                        print("Đã tạo DataFrame từ kết quả")
                        results_df = pd.DataFrame(data)
                        
                        # Lưu DataFrame vào session state
                        st.session_state.results_df = results_df
                        
                        # Hiển thị kết quả
                        st.dataframe(results_df, use_container_width=True)
                        
                        # Thêm nút tải xuống kết quả
                        st.download_button(
                            label="Tải xuống kết quả",
                            data=results_df.to_csv(index=False).encode('utf-8'),
                            file_name='evaluation_results.csv',
                            mime='text/csv'
                        )
                        
                        # # Thêm phần lọc kết quả theo điểm
                        # st.subheader("Lọc kết quả theo điểm")
                        
                        # # Lấy tất cả tiêu chí điểm
                        # score_columns = [col for col in results_df.columns if 'Score' in col]
                        
                        # col1, col2 = st.columns(2)
                        # with col1:
                        #     selected_criterion = st.selectbox("Chọn tiêu chí điểm", score_columns)
                        # with col2:
                        #     threshold = st.slider("Ngưỡng điểm", 0.0, 10.0, 5.0, 0.5)
                        
                        # filter_type = st.radio("Loại lọc", ["Lớn hơn hoặc bằng", "Nhỏ hơn hoặc bằng"])
                        
                        # if st.button("Áp dụng bộ lọc"):
                        #     # Lọc DataFrame dựa trên tiêu chí đã chọn
                        #     if filter_type == "Lớn hơn hoặc bằng":
                        #         filtered_df = results_df[results_df[selected_criterion] >= threshold]
                        #     else:
                        #         filtered_df = results_df[results_df[selected_criterion] <= threshold]
                            
                        #     # Hiển thị kết quả đã lọc
                        #     st.write(f"Tìm thấy {len(filtered_df)} kết quả phù hợp với bộ lọc")
                        #     st.dataframe(filtered_df, use_container_width=True)
                            
                        #     # Tùy chọn xuất kết quả đã lọc
                        #     st.download_button(
                        #         label="Tải xuống kết quả đã lọc",
                        #         data=filtered_df.to_csv(index=False).encode('utf-8'),
                        #         file_name=f'filtered_results_{selected_criterion}_{threshold}.csv',
                        #         mime='text/csv'
                        #     )
                        
                        # if failed_questions:
                        #     st.warning(f"Có {len(failed_questions)} câu hỏi xử lý thất bại")
                    else:
                        print("Không có kết quả")
                else:
                    st.warning("Vui lòng chọn ít nhất một câu hỏi để test")
        except Exception as e:
            st.error(f"Lỗi khi đọc file Excel: {str(e)}")
    else:
        st.info("Vui lòng tải lên file Excel để bắt đầu")

# Hiển thị hướng dẫn sử dụng
st.sidebar.subheader("Hướng dẫn sử dụng")
st.sidebar.markdown("""
### Test đơn lẻ
1. Nhập câu hỏi vào ô "Câu hỏi"
2. Nhập câu trả lời chuẩn vào ô "Câu trả lời chuẩn"
3. Nhấn nút "Test" để bắt đầu đánh giá

### Test hàng loạt
1. Chọn các câu hỏi muốn test từ bảng
2. Nhấn nút "Test hàng loạt" để bắt đầu đánh giá
3. Kết quả sẽ được hiển thị dưới dạng bảng và có thể tải về Excel
""") 
