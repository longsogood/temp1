import streamlit as st
import pandas as pd
import requests
import time
import datetime
import os
import pickle
import schedule
import threading
from uuid import uuid4
import concurrent.futures
import logging

# Cấu hình logging
log_file = "logs/test_log.log"
os.makedirs(os.path.dirname(log_file), exist_ok=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(log_file, encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(file_handler)

# Khởi tạo session state
if 'results' not in st.session_state:
    st.session_state.results = None
if 'schedule_enabled' not in st.session_state:
    st.session_state.schedule_enabled = {}
if 'schedule_thread' not in st.session_state:
    st.session_state.schedule_thread = {}
if 'test_history' not in st.session_state:
    st.session_state.test_history = {}
if 'failed_tests' not in st.session_state:
    st.session_state.failed_tests = {}
if 'test_changes_history' not in st.session_state:
    st.session_state.test_changes_history = {}
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = None
if 'current_site' not in st.session_state:
    st.session_state.current_site = "Agent HR Nội bộ" # Hoặc một giá trị mặc định khác

# Đường dẫn file
RESULTS_DIR = "test_results"
FAILED_TESTS_FILE = os.path.join(RESULTS_DIR, "failed_tests.pkl")
TEST_HISTORY_FILE = os.path.join(RESULTS_DIR, "test_history.pkl")
TEST_CHANGES_FILE = os.path.join(RESULTS_DIR, "test_changes.pkl")

# Tạo thư mục nếu chưa có
os.makedirs(RESULTS_DIR, exist_ok=True)

# --- Các hàm xử lý ---
def get_current_site():
    """Safely get current site from session state"""
    try:
        return st.session_state.current_site
    except AttributeError:
        return "Agent HR Nội bộ"

def filter_results(results, threshold, criterion, filter_type):
    filtered_data = []
    for result in results:
        score = result["evaluate_result"]["scores"].get(criterion, 0)
        if (filter_type == "greater" and score >= threshold) or \
           (filter_type == "less" and score <= threshold):
            filtered_data.append(result)
    return filtered_data

def save_test_results(results, test_name, site):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{test_name}_{timestamp}.xlsx"
    filepath = os.path.join(RESULTS_DIR, site, filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    df = pd.DataFrame(results)
    df.to_excel(filepath, index=False)

    num_passed = sum(1 for r in results if r["evaluate_result"]["scores"].get("average", 0) >= 5)
    num_failed = len(results) - num_passed

    history_entry = {
        "timestamp": timestamp,
        "test_name": test_name,
        "num_questions": len(results),
        "num_passed": num_passed,
        "num_failed": num_failed,
        "filename": filename
    }

    # Initialize test_history if not exists
    try:
        if 'test_history' not in st.session_state:
            st.session_state.test_history = {}
        if site not in st.session_state.test_history:
            st.session_state.test_history[site] = []
        st.session_state.test_history[site].append(history_entry)

        site_paths = get_site_paths(site)
        with open(site_paths["test_history"], "wb") as f:
            pickle.dump(st.session_state.test_history[site], f)
    except Exception as e:
        logger.warning(f"Không thể lưu lịch sử test: {str(e)}")

    return filepath

def save_failed_test_details(failed_results, site=None):
    # Use provided site or fallback to session state
    if site is None:
        site = get_current_site()
    
    # Initialize failed_tests if not exists
    if 'failed_tests' not in st.session_state:
        st.session_state.failed_tests = {}
    
    if site not in st.session_state.failed_tests:
        st.session_state.failed_tests[site] = []

    for result in failed_results:
        st.session_state.failed_tests[site].append(result)

    site_paths = get_site_paths(site)
    with open(site_paths["failed_tests"], "wb") as f:
        pickle.dump(st.session_state.failed_tests[site], f)

def run_scheduled_test(file_path, test_name, site, api_url, evaluate_api_url):
    logger.info(f"Bắt đầu chạy test theo lịch: {test_name} cho site {site} với API {api_url}")
    
    # Initialize session state for scheduled context if needed
    try:
        if 'failed_tests' not in st.session_state:
            st.session_state.failed_tests = {}
        if 'test_history' not in st.session_state:
            st.session_state.test_history = {}
        if 'test_changes_history' not in st.session_state:
            st.session_state.test_changes_history = {}
    except Exception as e:
        logger.warning(f"Không thể khởi tạo session state: {str(e)}")
    
    try:
        abs_path = os.path.abspath(file_path)
        if not os.path.exists(abs_path):
            logger.error(f"File test không tồn tại: {abs_path}")
            return
        logger.info(f"Đọc file test: {abs_path}")
    except Exception as e:
        logger.error(f"Lỗi khi kiểm tra file test: {str(e)}")
        return
    try:
        df = pd.read_excel(abs_path)
        questions = df.iloc[:, 0].tolist()
        true_answers = df.iloc[:, 1].tolist()
        logger.info(f"Số câu hỏi đọc được: {len(questions)} | Số đáp án: {len(true_answers)}")

        results, failed_questions = process_questions_batch(
            questions, 
            true_answers, 
            test_name=test_name, 
            is_scheduled=True,
            site=site,
            api_url=api_url,
            evaluate_api_url=evaluate_api_url
        )

        try:
            # Luôn cố gắng lưu file kết quả để thuận tiện kiểm tra, kể cả khi rỗng
            saved_path = save_test_results(results or [], test_name, site)
            logger.info(f"Đã lưu kết quả test: {test_name} → {os.path.abspath(saved_path)}")
        except Exception as e:
            logger.error(f"Lỗi khi lưu kết quả test {test_name}: {str(e)}")
        if failed_questions:
            logger.warning(f"Có {len(failed_questions)} câu hỏi thất bại trong test: {test_name}")

    except Exception as e:
        logger.error(f"Lỗi khi chạy test theo lịch {test_name}: {str(e)}")

def schedule_manager():
    while True:
        schedule.run_pending()
        time.sleep(1)

def setup_schedule(file_path, schedule_type, schedule_time, schedule_day,
                   test_name, site, api_url, evaluate_api_url,
                   custom_interval=None, custom_unit=None):
    logger.info(f"Thiết lập lịch cho test: {test_name} - {schedule_type} - Site: {site}")
    
    import schedule  # đảm bảo import trong hàm hoặc đầu file
    
    # Loại bỏ việc dùng job = schedule.every() rồi tiếp tục job.xxx
    # Thay vào đó mỗi nhánh sẽ tạo schedule mới trực tiếp
    
    if schedule_type == "minute":
        # chạy mỗi phút
        schedule.every().minute.do(
            run_scheduled_test,
            file_path, test_name, site, api_url, evaluate_api_url
        )
    
    elif schedule_type == "hourly":
        # chạy mỗi giờ tại phút cụ thể
        # schedule.every().hour.at(":MM").do(...)
        minute = schedule_time.split(':')[1]
        schedule.every().hour.at(f":{minute}").do(
            run_scheduled_test,
            file_path, test_name, site, api_url, evaluate_api_url
        )
    
    elif schedule_type == "daily":
        # mỗi ngày vào lúc HH:MM
        schedule.every().day.at(schedule_time).do(
            run_scheduled_test,
            file_path, test_name, site, api_url, evaluate_api_url
        )
    
    elif schedule_type == "weekly":
        day = schedule_day.lower()
        if day == "monday":
            schedule.every().monday.at(schedule_time).do(
                run_scheduled_test,
                file_path, test_name, site, api_url, evaluate_api_url
            )
        elif day == "tuesday":
            schedule.every().tuesday.at(schedule_time).do(
                run_scheduled_test,
                file_path, test_name, site, api_url, evaluate_api_url
            )
        elif day == "wednesday":
            schedule.every().wednesday.at(schedule_time).do(
                run_scheduled_test,
                file_path, test_name, site, api_url, evaluate_api_url
            )
        elif day == "thursday":
            schedule.every().thursday.at(schedule_time).do(
                run_scheduled_test,
                file_path, test_name, site, api_url, evaluate_api_url
            )
        elif day == "friday":
            schedule.every().friday.at(schedule_time).do(
                run_scheduled_test,
                file_path, test_name, site, api_url, evaluate_api_url
            )
        elif day == "saturday":
            schedule.every().saturday.at(schedule_time).do(
                run_scheduled_test,
                file_path, test_name, site, api_url, evaluate_api_url
            )
        elif day == "sunday":
            schedule.every().sunday.at(schedule_time).do(
                run_scheduled_test,
                file_path, test_name, site, api_url, evaluate_api_url
            )
        else:
            # mặc định Monday nếu không hợp lệ
            schedule.every().monday.at(schedule_time).do(
                run_scheduled_test,
                file_path, test_name, site, api_url, evaluate_api_url
            )
    
    elif schedule_type == "custom" and custom_interval and custom_unit:
        # chạy theo khoảng custom
        if custom_unit == "phút":
            schedule.every(custom_interval).minutes.do(
                run_scheduled_test,
                file_path, test_name, site, api_url, evaluate_api_url
            )
        elif custom_unit == "giờ":
            schedule.every(custom_interval).hours.do(
                run_scheduled_test,
                file_path, test_name, site, api_url, evaluate_api_url
            )
        elif custom_unit == "ngày":
            schedule.every(custom_interval).days.do(
                run_scheduled_test,
                file_path, test_name, site, api_url, evaluate_api_url
            )
        elif custom_unit == "tuần":
            schedule.every(custom_interval).weeks.do(
                run_scheduled_test,
                file_path, test_name, site, api_url, evaluate_api_url
            )
        else:
            logger.warning(f"Đơn vị lịch không hợp lệ: {custom_unit}")
    else:
        logger.warning(f"Không có lịch hợp lệ cho loại {schedule_type}")
    
    # Khởi động thread nếu chưa có cho site
    if site not in st.session_state.schedule_thread or not st.session_state.schedule_thread[site].is_alive():
        thread = threading.Thread(target=schedule_manager, daemon=True)
        st.session_state.schedule_thread[site] = thread
        thread.start()
        logger.info(f"Đã khởi động thread quản lý lịch cho site: {site}")

# Giao diện Streamlit
st.title("🤖 Agent Testing")

# --- Cấu hình và các biến toàn cục ---
with st.expander("Cấu hình API và các tham số", expanded=False):
    API_URL = st.text_input("API URL", st.session_state.get("api_url", "https://site1.com"))
    EVALUATE_API_URL = st.text_input("Evaluate API URL", st.session_state.get("evaluate_api_url", "https://site2.com"))
    MAX_WORKERS = st.slider("Số luồng xử lý đồng thời", 1, 20, 5)
    add_chat_history_global = st.checkbox("Thêm chat history (giả lập đã cung cấp thông tin)", value=False)
    
    st.session_state.api_url = API_URL
    st.session_state.evaluate_api_url = EVALUATE_API_URL


# Tải prompts
def load_prompts():
    global evaluate_system_prompt
    try:
        with open("prompts/evaluation/system_prompt.txt", "r", encoding="utf-8") as f:
            evaluate_system_prompt = f.read()
    except FileNotFoundError:
        st.error("Không tìm thấy file prompt. Vui lòng kiểm tra lại đường dẫn.")
        evaluate_system_prompt = ""
load_prompts()

# --- Các hàm xử lý chính ---
progress_queue = st.empty()

def update_progress(container, total):
    processed_count = 0
    while processed_count < total:
        try:
            message = progress_queue.get(timeout=1)
            if "SUCCESS" in message:
                processed_count += 1
            container.text(f"Tiến trình: {processed_count}/{total} câu hỏi đã xử lý.")
            st.info(message)
        except Exception:
            break

def extract_section(text):
    try:
        # Kiểm tra xem text có chứa các keyword cần thiết không
        if "scores:" not in text or "comments:" not in text:
            return {"scores": {}, "comments": "Format đánh giá không hợp lệ - thiếu scores hoặc comments"}
        
        # Tìm và trích xuất điểm
        scores_parts = text.split("scores:")
        if len(scores_parts) < 2:
            return {"scores": {}, "comments": "Không tìm thấy phần scores"}
        
        scores_section = scores_parts[1]
        comments_parts = scores_section.split("comments:")
        if len(comments_parts) < 2:
            return {"scores": {}, "comments": "Không tìm thấy phần comments"}
        
        scores_str = comments_parts[0].strip()
        comments = comments_parts[1].strip()
        
        # Kiểm tra scores_str có rỗng không
        if not scores_str:
            return {"scores": {}, "comments": "Phần scores rỗng"}
        
        # Thử parse scores
        try:
            scores = eval(scores_str)
            if not isinstance(scores, dict):
                scores = {}
        except Exception as parse_error:
            logger.warning(f"Lỗi khi parse scores: {parse_error}")
            scores = {}
        
        return {"scores": scores, "comments": comments}
    except Exception as e:
        logger.error(f"Lỗi khi trích xuất: {e}")
        return {"scores": {}, "comments": f"Lỗi khi phân tích kết quả đánh giá: {str(e)}"}

def process_single_question(question, true_answer, index, total_questions, add_chat_history=False, custom_history=None, site=None, api_url=None, evaluate_api_url=None):
    try:
        chat_id = str(uuid4())
        payload = {
            "chat_id": chat_id,
            "question": question,
            "site": site or get_current_site()
        }
        if add_chat_history and custom_history:
            payload["chat_history"] = custom_history

        request_api_url = api_url or API_URL
        request_evaluate_api_url = evaluate_api_url or EVALUATE_API_URL

        response = requests.post(request_api_url, json=payload)
        if not response.ok:
            return f"Lỗi API: {response.text}"
        
        site_response = response.json()["text"]
        
        evaluate_payload = {
            "question": question,
            "true_answer": true_answer,
            "site_response": site_response,
            "system_prompt": evaluate_system_prompt
        }
        evaluate_response = requests.post(request_evaluate_api_url, json=evaluate_payload)
        
        if not evaluate_response.ok:
            return f"Lỗi khi đánh giá câu trả lời: {evaluate_response.text}"
        
        time.sleep(5)
        
        try:
            evaluate_json = evaluate_response.json()
            if "text" not in evaluate_json:
                return f"Response đánh giá không có trường 'text': {evaluate_json}"
            
            evaluate_response_text = evaluate_json["text"]
            if not evaluate_response_text:
                return "Response đánh giá rỗng"
                
            evaluate_result = extract_section(evaluate_response_text)
        except Exception as e:
            return f"Lỗi khi xử lý response đánh giá: {str(e)}"

        return {
            "chat_id": chat_id,
            "question": question,
            "true_answer": true_answer,
            "site_response": site_response,
            "evaluate_result": evaluate_result,
        }
    except requests.exceptions.RequestException as e:
        return f"Lỗi API: {str(e)}"
    except Exception as e:
        return f"Lỗi khi xử lý câu hỏi {index + 1}: {str(e)}"

def process_questions_batch(questions, true_answers, add_chat_history=False, custom_history=None, test_name=None, is_scheduled=False, site=None, api_url=None, evaluate_api_url=None):
    results = []
    failed_questions = []
    
    progress_container = st.empty() if not is_scheduled else None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_single_question, q, ta, i, len(questions), add_chat_history, custom_history, site, api_url, evaluate_api_url): (q, ta) for i, (q, ta) in enumerate(zip(questions, true_answers))}
        
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            question, true_answer = futures[future]
            try:
                result = future.result()
                if isinstance(result, dict):
                    if result["evaluate_result"]["scores"].get("average", 0) < 5:
                        result["failed_details"] = {
                            "timestamp": datetime.datetime.now().isoformat(),
                            "test_name": test_name,
                            "reason": "Điểm đánh giá thấp",
                            "expected_output": result["true_answer"],
                            "actual_output": result["site_response"],
                            "scores": result["evaluate_result"]["scores"]
                        }
                        failed_questions.append((question, "Điểm đánh giá thấp", result))
                    results.append(result)
                else:
                    error_result = {
                        "chat_id": str(uuid4()), "question": question, "true_answer": true_answer,
                        "site_response": "[Lỗi khi xử lý]",
                        "evaluate_result": {"scores": {}, "comments": f"Lỗi: {result}"},
                        "failed_details": {"timestamp": datetime.datetime.now().isoformat(), "test_name": test_name, "reason": "Lỗi xử lý API", "error_message": str(result)}
                    }
                    results.append(error_result)
                    failed_questions.append((question, "Lỗi xử lý API", result))
            except Exception as e:
                error_message = f"Lỗi: {str(e)}"
                error_result = {
                    "chat_id": str(uuid4()), "question": question, "true_answer": true_answer,
                    "site_response": "[Lỗi khi xử lý]",
                    "evaluate_result": {"scores": {}, "comments": error_message},
                    "failed_details": {"timestamp": datetime.datetime.now().isoformat(), "test_name": test_name, "reason": "Exception", "error_message": str(e)}
                }
                results.append(error_result)
                failed_questions.append((question, "Exception", str(e)))
            
            if not is_scheduled and progress_container:
                progress_container.text(f"Đã xử lý {i + 1}/{len(questions)} câu hỏi.")

    if failed_questions and (is_scheduled or test_name):
        failed_results = [r for r in results if "failed_details" in r]
        if failed_results:
            save_failed_test_details(failed_results, site)
    
    return results, failed_questions


# Tải lịch sử test, test case thất bại và lịch sử thay đổi
def get_site_paths(site):
    site_dir = os.path.join(RESULTS_DIR, site)
    os.makedirs(site_dir, exist_ok=True)
    return {
        "failed_tests": os.path.join(site_dir, "failed_tests.pkl"),
        "test_history": os.path.join(site_dir, "test_history.pkl"),
        "test_changes": os.path.join(site_dir, "test_changes.pkl")
    }

current_site = get_current_site()
site_paths = get_site_paths(current_site)
FAILED_TESTS_FILE = site_paths["failed_tests"]
TEST_HISTORY_FILE = site_paths["test_history"]
TEST_CHANGES_FILE = site_paths["test_changes"]

if os.path.exists(TEST_HISTORY_FILE):
    with open(TEST_HISTORY_FILE, "rb") as f:
        st.session_state.test_history[current_site] = pickle.load(f)
else:
    st.session_state.test_history[current_site] = []

if os.path.exists(FAILED_TESTS_FILE):
    with open(FAILED_TESTS_FILE, "rb") as f:
        st.session_state.failed_tests[current_site] = pickle.load(f)
else:
    st.session_state.failed_tests[current_site] = []

if os.path.exists(TEST_CHANGES_FILE):
    with open(TEST_CHANGES_FILE, "rb") as f:
        st.session_state.test_changes_history[current_site] = pickle.load(f)
else:
    st.session_state.test_changes_history[current_site] = []


SCHEDULED_TESTS_DIR = "scheduled_tests"
SCHEDULED_JOBS_FILE = os.path.join(SCHEDULED_TESTS_DIR, "scheduled_jobs.pkl")
os.makedirs(SCHEDULED_TESTS_DIR, exist_ok=True)

# Functions to save and load scheduled jobs
def save_scheduled_jobs():
    """Save scheduled jobs to file"""
    try:
        with open(SCHEDULED_JOBS_FILE, "wb") as f:
            pickle.dump(st.session_state.scheduled_jobs, f)
    except Exception as e:
        logger.error(f"Lỗi khi lưu scheduled jobs: {str(e)}")

def load_scheduled_jobs():
    """Load scheduled jobs from file"""
    try:
        if os.path.exists(SCHEDULED_JOBS_FILE):
            with open(SCHEDULED_JOBS_FILE, "rb") as f:
                return pickle.load(f)
        return []
    except Exception as e:
        logger.error(f"Lỗi khi tải scheduled jobs: {str(e)}")
        return []

def get_scheduled_job_for_site(site):
    """Get scheduled job for a specific site"""
    for job in st.session_state.scheduled_jobs:
        if job.get('site') == site:
            return job
    return None

def remove_scheduled_job_for_site(site):
    """Remove scheduled job for a specific site"""
    st.session_state.scheduled_jobs = [job for job in st.session_state.scheduled_jobs if job.get('site') != site]
    save_scheduled_jobs()

# Initialize scheduled jobs
if 'scheduled_jobs' not in st.session_state:
    st.session_state.scheduled_jobs = load_scheduled_jobs()

# Re-create schedule from session state on each run
schedule.clear()
for job_config in st.session_state.scheduled_jobs:
    if os.path.exists(job_config["file_path"]):
        setup_schedule(
            file_path=job_config["file_path"],
            schedule_type=job_config["schedule_type"],
            schedule_time=job_config["schedule_time"],
            schedule_day=job_config["schedule_day"],
            test_name=job_config["test_name"],
            site=job_config["site"],
            api_url=job_config.get("api_url", st.session_state.get("schedule_api_url", "https://site1.com")),
            evaluate_api_url=job_config.get("evaluate_api_url", st.session_state.get("schedule_evaluate_api_url", "https://site2.com")),
            custom_interval=job_config.get("custom_interval"),
            custom_unit=job_config.get("custom_unit")
        )
    else:
        # If file is missing, mark the job for removal
        st.session_state.scheduled_jobs = [j for j in st.session_state.scheduled_jobs if j['job_id'] != job_config['job_id']]
        save_scheduled_jobs()  # Save updated list to file

# Giao diện Streamlit
st.title("🤖 Agent Testing")

# Tạo các tab
tab1, tab2, tab3, tab4 = st.tabs(["Test đơn lẻ", "Test hàng loạt", "Lập lịch test", "Quản lý test"])

with tab1:
    st.subheader("Nhập câu hỏi và câu trả lời chuẩn")
    question = st.text_area("Câu hỏi:", height=100)
    true_answer = st.text_area("Câu trả lời chuẩn:", height=200)
    
    if add_chat_history_global:
        if 'chat_history' not in st.session_state or st.session_state.chat_history is None:
            st.session_state.chat_history = [
                {"role": "apiMessage", "content": "Vui lòng cung cấp họ tên, số điện thoại, trường THPT và tỉnh thành sinh sống để tôi có thể tư vấn tốt nhất. Lưu ý, thông tin bạn cung cấp cần đảm bảo tính chính xác."},
                {"role": "userMessage", "content": "[Cung cấp thông tin]"}
            ]
        st.markdown("**Thiết lập chat history:**")
        
        # Sử dụng một list tạm để tránh lỗi khi xóa
        new_history = []
        for i, msg in enumerate(st.session_state.chat_history):
            cols = st.columns([2, 8, 1])
            role = cols[0].selectbox(f"Role {i+1}", ["apiMessage", "userMessage"], key=f"role_{i}", index=["apiMessage", "userMessage"].index(msg["role"]))
            content = cols[1].text_area(f"Nội dung {i+1}", value=msg["content"], key=f"content_{i}")
            if not cols[2].button("Xoá", key=f"delete_{i}"):
                new_history.append({"role": role, "content": content})
        st.session_state.chat_history = new_history

        if st.button("Thêm message"):
            st.session_state.chat_history.append({"role": "userMessage", "content": ""})
            st.rerun()

    if st.button("Test"):
        if question and true_answer:
            progress_container = st.empty()
            progress_container.text("Đang xử lý...")
            history = st.session_state.chat_history if (add_chat_history_global and st.session_state.chat_history) else None
            result = process_single_question(question, true_answer, 0, 1, add_chat_history=add_chat_history_global, custom_history=history, site=get_current_site())
            
            if isinstance(result, dict):
                progress_container.success("Xử lý thành công!")
                st.subheader("Kết quả")
                st.write("**Câu trả lời từ Agent:**")
                st.write(result["site_response"])
                st.write("**Đánh giá:**")
                scores = result["evaluate_result"]["scores"]
                for metric, score in scores.items():
                    st.write(f"- {metric}: {score}")
                st.write("**Nhận xét và góp ý cải thiện:**")
                st.write(result["evaluate_result"]["comments"])
            else:
                progress_container.error(f"Lỗi: {result}")
        else:
            st.warning("Vui lòng nhập cả câu hỏi và câu trả lời chuẩn")

with tab2:
    st.subheader("Test hàng loạt từ file Excel")
    
    if add_chat_history_global:
        # Tương tự tab 1, hiển thị và cho phép chỉnh sửa chat history
        if 'chat_history' not in st.session_state or st.session_state.chat_history is None:
            st.session_state.chat_history = [
                {"role": "apiMessage", "content": "Vui lòng cung cấp họ tên, số điện thoại, trường THPT và tỉnh thành sinh sống để tôi có thể tư vấn tốt nhất. Lưu ý, thông tin bạn cung cấp cần đảm bảo tính chính xác."},
                {"role": "userMessage", "content": "[Cung cấp thông tin]"}
            ]
        st.markdown("**Thiết lập chat history cho tất cả câu hỏi:**")
        new_history = []
        for i, msg in enumerate(st.session_state.chat_history):
            cols = st.columns([2, 8, 1])
            role = cols[0].selectbox(f"Role batch {i+1}", ["apiMessage", "userMessage"], key=f"role_batch_{i}", index=["apiMessage", "userMessage"].index(msg["role"]))
            content = cols[1].text_area(f"Nội dung batch {i+1}", value=msg["content"], key=f"content_batch_{i}")
            if not cols[2].button("Xoá", key=f"delete_batch_{i}"):
                new_history.append({"role": role, "content": content})
        st.session_state.chat_history = new_history

        if st.button("Thêm message", key="add_message_batch"):
            st.session_state.chat_history.append({"role": "userMessage", "content": ""})
            st.rerun()

    uploaded_file = st.file_uploader("Chọn file Excel", type=['xlsx', 'xls'])
    
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            df = df.dropna(subset=[df.columns[0], df.columns[1]])
            questions = df.iloc[:, 0].tolist()
            true_answers = df.iloc[:, 1].tolist()
            
            display_df = pd.DataFrame({'Câu hỏi': questions, 'Câu trả lời chuẩn': true_answers})
            edited_df = st.dataframe(display_df, use_container_width=True, selection_mode="multi-row", on_select="rerun", hide_index=True)
            
            selected_rows = edited_df['selection']['rows']
            
            if st.button("Test hàng loạt"):
                if selected_rows:
                    selected_questions = [questions[i] for i in selected_rows]
                    selected_true_answers = [true_answers[i] for i in selected_rows]
                    
                    history = st.session_state.chat_history if (add_chat_history_global and st.session_state.chat_history) else None
                    results, failed_questions = process_questions_batch(selected_questions, selected_true_answers, add_chat_history=add_chat_history_global, custom_history=history, test_name=uploaded_file.name, site=get_current_site())
                    
                    st.session_state.results = results
                    
                    data = {
                        'Question': [r["question"] for r in results],
                        'True Answer': [r["true_answer"] for r in results],
                        'Agent Answer': [r["site_response"] for r in results],
                        'Session ID': [r["chat_id"] for r in results],
                        'Relevance Score': [r["evaluate_result"]["scores"].get("relevance", 0) for r in results],
                        'Accuracy Score': [r["evaluate_result"]["scores"].get("accuracy", 0) for r in results],
                        'Completeness Score': [r["evaluate_result"]["scores"].get("completeness", 0) for r in results],
                        'Clarity Score': [r["evaluate_result"]["scores"].get("clarity", 0) for r in results],
                        'Tone Score': [r["evaluate_result"]["scores"].get("tone", 0) for r in results],
                        'Average Score': [r["evaluate_result"]["scores"].get("average", 0) for r in results],
                        'Comment': [r["evaluate_result"].get("comments", "") for r in results]
                    }
                    results_df = pd.DataFrame(data)
                    st.session_state.results_df = results_df
                    
                    st.subheader(f"Kết quả đánh giá ({len(results)} câu hỏi)")
                    st.dataframe(results_df, use_container_width=True)
                    
                    st.download_button(label="Tải xuống kết quả", data=results_df.to_csv(index=False).encode('utf-8'), file_name='evaluation_results.csv', mime='text/csv')
                    
                    if failed_questions:
                        st.warning(f"Có {len(failed_questions)} câu hỏi xử lý thất bại")
                    st.success(f"Đã hoàn thành đánh giá {len(results)} câu hỏi")
                else:
                    st.warning("Vui lòng chọn ít nhất một câu hỏi để test")
        except Exception as e:
            st.error(f"Lỗi khi đọc file Excel: {str(e)}")
    else:
        st.info("Vui lòng tải lên file Excel để bắt đầu")

with tab3:
    st.subheader("Lập lịch chạy test tự động")

    site = get_current_site()
    existing_job = get_scheduled_job_for_site(site)
    
    if existing_job:
        st.info(f"Site **{site}** đã có cấu hình lịch test. Bạn có thể chỉnh sửa hoặc xóa cấu hình hiện tại.")
        
        st.write("### Cấu hình hiện tại")
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.write(f"**Tên Test:** {existing_job['test_name']}")
            st.write(f"**Loại lịch:** {existing_job['schedule_type']}")
            st.write(f"**Thời gian:** {existing_job.get('schedule_time', 'N/A')}")
            if existing_job.get('schedule_day'):
                st.write(f"**Ngày:** {existing_job['schedule_day']}")
            if existing_job.get('custom_interval') and existing_job.get('custom_unit'):
                st.write(f"**Tùy chỉnh:** Mỗi {existing_job['custom_interval']} {existing_job['custom_unit']}")
            st.write(f"**API URL:** `{existing_job.get('api_url', 'Chưa cấu hình')}`")
            st.write(f"**Evaluate API URL:** `{existing_job.get('evaluate_api_url', 'Chưa cấu hình')}`")
            
            # Show next run time
            found_job = None
            for job in schedule.jobs:
                try:
                    if job.job_func.args[1] == existing_job['test_name'] and job.job_func.args[2] == existing_job['site']:
                        found_job = job
                        break
                except (IndexError, AttributeError):
                    continue
            
            if found_job:
                st.write(f"**Chạy lần tới:** {found_job.next_run.strftime('%Y-%m-%d %H:%M:%S') if found_job.next_run else 'N/A'}")
            else:
                st.warning("Không thể lấy thông tin chi tiết lịch chạy.")
        
        with col2:
            if st.button("Chỉnh sửa", key="edit_existing_job"):
                st.session_state.editing_existing_job = True
                st.rerun()
            
            if st.button("Xóa cấu hình", key="delete_existing_job"):
                # Remove the old file
                if os.path.exists(existing_job['file_path']):
                    os.remove(existing_job['file_path'])
                
                # Remove from scheduled jobs
                remove_scheduled_job_for_site(site)
                
                st.success(f"Đã xóa cấu hình lịch test cho site '{site}'.")
                st.rerun()
        
        # Show edit form if editing
        if st.session_state.get('editing_existing_job', False):
            st.write("### Chỉnh sửa cấu hình")
            
            # API URLs
            new_api_url = st.text_input("API URL", value=existing_job.get('api_url', "https://site1.com"), key="edit_api_url")
            new_eval_api_url = st.text_input("Evaluate API URL", value=existing_job.get('evaluate_api_url', "https://site2.com"), key="edit_eval_api_url")
            
            # Test file
            st.write("**File test hiện tại:**")
            if os.path.exists(existing_job['file_path']):
                try:
                    df_current = pd.read_excel(existing_job['file_path'])
                    st.write(f"File: `{os.path.basename(existing_job['file_path'])}` ({len(df_current)} dòng)")
                    st.write("**Preview 5 dòng đầu tiên:**")
                    st.dataframe(df_current.head(5), use_container_width=True)
                except Exception as e:
                    st.error(f"Lỗi khi đọc file hiện tại: {str(e)}")
            else:
                st.warning("File test hiện tại không tồn tại")
            
            st.write("**Upload file test mới (để trống nếu không thay đổi):**")
            new_test_file = st.file_uploader("File test mới", type=['xlsx', 'xls'], key="edit_test_file")
            
            # Hiển thị preview file mới nếu có
            if new_test_file is not None:
                try:
                    df_new_preview = pd.read_excel(new_test_file)
                    st.write("**Preview 5 dòng đầu tiên của file mới:**")
                    st.dataframe(df_new_preview.head(5), use_container_width=True)
                    
                    # Reset file pointer để có thể đọc lại sau này
                    new_test_file.seek(0)
                except Exception as e:
                    st.error(f"Lỗi khi đọc file Excel mới: {str(e)}")
                    new_test_file = None
            
            new_test_name = st.text_input("Tên test mới", value=existing_job['test_name'], key="edit_test_name")
            
            # Schedule settings
            current_schedule_type = existing_job.get('schedule_type', 'daily')
            if current_schedule_type is None:
                current_schedule_type = 'daily'
            schedule_type_index = ["minute", "hourly", "daily", "weekly", "custom"].index(current_schedule_type) if current_schedule_type in ["minute", "hourly", "daily", "weekly", "custom"] else 2
            new_schedule_type = st.selectbox("Loại lịch", ["minute", "hourly", "daily", "weekly", "custom"], 
                                            index=schedule_type_index, 
                                            key="edit_schedule_type")
            
            new_schedule_time = None
            new_schedule_day = None
            new_custom_interval = None
            new_custom_unit = None
            
            col1, col2 = st.columns(2)
            with col1:
                if new_schedule_type == "minute":
                    st.info("Test sẽ chạy mỗi phút")
                    
                elif new_schedule_type == "hourly":
                    # Safe parsing for hourly schedule
                    current_time = existing_job.get('schedule_time')
                    if current_time is None or current_time == '':
                        current_time = '00:00'
                    try:
                        time_parts = current_time.split(':')
                        if len(time_parts) >= 2:
                            current_minute = int(time_parts[1])
                        else:
                            current_minute = 0
                    except (ValueError, IndexError):
                        current_minute = 0
                    minute = st.number_input("Phút", 0, 59, current_minute, key="edit_schedule_minute")
                    new_schedule_time = f"00:{minute:02d}"
                    
                elif new_schedule_type == "custom":
                    # Safe parsing for custom schedule
                    current_interval = existing_job.get('custom_interval')
                    if current_interval is None:
                        current_interval = 2
                    new_custom_interval = st.number_input("Mỗi", 1, 100, current_interval, key="edit_custom_interval")
                    
                    current_custom_unit = existing_job.get('custom_unit')
                    if current_custom_unit is None or current_custom_unit not in ["phút", "giờ", "ngày", "tuần"]:
                        current_custom_unit = 'giờ'
                    unit_index = ["phút", "giờ", "ngày", "tuần"].index(current_custom_unit) if current_custom_unit in ["phút", "giờ", "ngày", "tuần"] else 1
                    new_custom_unit = st.selectbox("Đơn vị", ["phút", "giờ", "ngày", "tuần"], 
                                                 index=unit_index, 
                                                 key="edit_custom_unit")
                    
                else:  # daily or weekly
                    # Safe parsing for daily/weekly schedule
                    current_time = existing_job.get('schedule_time')
                    if current_time is None or current_time == '':
                        current_time = '00:00'
                    try:
                        time_parts = current_time.split(':')
                        if len(time_parts) >= 2:
                            hour = int(time_parts[0])
                            minute = int(time_parts[1])
                            time_obj = datetime.time(hour, minute)
                        else:
                            time_obj = datetime.time(0, 0)
                    except (ValueError, IndexError):
                        time_obj = datetime.time(0, 0)
                    schedule_time_input = st.time_input("Thời gian", value=time_obj, key="edit_schedule_time")
                    new_schedule_time = schedule_time_input.strftime("%H:%M")
            
            with col2:
                if new_schedule_type == "weekly":
                    current_day = existing_job.get('schedule_day')
                    if current_day is None or current_day not in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
                        current_day = 'Monday'
                    day_index = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].index(current_day)
                    new_schedule_day = st.selectbox("Ngày trong tuần", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], 
                                                 index=day_index, 
                                                 key="edit_schedule_day")
            
            col1, col2, col3 = st.columns([1, 1, 4])
            with col1:
                if st.button("Lưu thay đổi", key="save_edit_existing"):
                    # Update job config
                    job_index = next((i for i, job in enumerate(st.session_state.scheduled_jobs) if job['job_id'] == existing_job['job_id']), None)
                    if job_index is not None:
                        # Update file if new one provided
                        if new_test_file is not None:
                            # Remove old file
                            if os.path.exists(existing_job['file_path']):
                                try:
                                    os.remove(existing_job['file_path'])
                                    st.info(f"Đã xóa file test cũ: {os.path.basename(existing_job['file_path'])}")
                                except Exception as e:
                                    st.warning(f"Không thể xóa file cũ: {str(e)}")
                            
                            # Tạo thư mục cho site nếu chưa có
                            site_dir = os.path.join(SCHEDULED_TESTS_DIR, site)
                            os.makedirs(site_dir, exist_ok=True)
                            
                            # Save new file
                            saved_file_name = f"{new_test_name.replace(' ', '_')}_{datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.xlsx"
                            saved_file_path = os.path.join(site_dir, saved_file_name)
                            with open(saved_file_path, "wb") as f:
                                f.write(new_test_file.getbuffer())
                            
                            st.session_state.scheduled_jobs[job_index]['file_path'] = saved_file_path
                            st.info(f"Đã lưu file test mới: {saved_file_name}")
                        
                        # Update other fields
                        st.session_state.scheduled_jobs[job_index]['test_name'] = new_test_name
                        st.session_state.scheduled_jobs[job_index]['schedule_type'] = new_schedule_type
                        st.session_state.scheduled_jobs[job_index]['schedule_time'] = new_schedule_time
                        st.session_state.scheduled_jobs[job_index]['schedule_day'] = new_schedule_day
                        st.session_state.scheduled_jobs[job_index]['custom_interval'] = new_custom_interval
                        st.session_state.scheduled_jobs[job_index]['custom_unit'] = new_custom_unit
                        st.session_state.scheduled_jobs[job_index]['api_url'] = new_api_url
                        st.session_state.scheduled_jobs[job_index]['evaluate_api_url'] = new_eval_api_url
                        
                        save_scheduled_jobs()
                        
                        # Recreate schedule
                        schedule.clear()
                        for job_config in st.session_state.scheduled_jobs:
                            if os.path.exists(job_config["file_path"]):
                                setup_schedule(
                                    file_path=job_config["file_path"],
                                    schedule_type=job_config["schedule_type"],
                                    schedule_time=job_config["schedule_time"],
                                    schedule_day=job_config["schedule_day"],
                                    test_name=job_config["test_name"],
                                    site=job_config["site"],
                                    api_url=job_config.get("api_url", "https://site1.com"),
                                    evaluate_api_url=job_config.get("evaluate_api_url", "https://site2.com"),
                                    custom_interval=job_config.get("custom_interval"),
                                    custom_unit=job_config.get("custom_unit")
                                )
                        
                        st.session_state.editing_existing_job = False
                        st.success(f"Đã cập nhật cấu hình lịch test cho site '{site}'.")
                        st.rerun()
            
            with col2:
                if st.button("Hủy", key="cancel_edit_existing"):
                    st.session_state.editing_existing_job = False
                    st.rerun()
    
    else:
        st.write("### Tạo cấu hình lịch test mới")
        st.write(f"Site hiện tại: **{site}**")
        
        st.write("### Bước 1: Cấu hình API URLs cho lịch test")
        schedule_api_url = st.text_input("API URL cho lịch test", st.session_state.get("schedule_api_url", "https://site1.com"), key="schedule_api_url_input")
        schedule_evaluate_api_url = st.text_input("Evaluate API URL cho lịch test", st.session_state.get("schedule_evaluate_api_url", "https://site2.com"), key="schedule_evaluate_api_url_input")
        
        # Lưu vào session state
        st.session_state.schedule_api_url = schedule_api_url
        st.session_state.schedule_evaluate_api_url = schedule_evaluate_api_url

        st.write("### Bước 2: Chọn file test và đặt tên")
        test_file = st.file_uploader("Chọn file Excel chứa test cases", type=['xlsx', 'xls'], key="schedule_file_uploader")
        
        # Hiển thị preview 5 dòng đầu tiên khi upload file
        if test_file is not None:
            try:
                df_preview = pd.read_excel(test_file)
                st.write("**Preview 5 dòng đầu tiên của file:**")
                st.dataframe(df_preview.head(5), use_container_width=True)
                
                # Reset file pointer để có thể đọc lại sau này
                test_file.seek(0)
            except Exception as e:
                st.error(f"Lỗi khi đọc file Excel: {str(e)}")
                test_file = None
        
        test_name = st.text_input("Tên bộ test (để nhận diện trong lịch sử)", key="test_name_input")

        if test_file and test_name:
            st.write("### Bước 3: Thiết lập lịch chạy test")
            
            schedule_type = st.selectbox("Loại lịch", ["minute", "hourly", "daily", "weekly", "custom"], key="schedule_type_select")
            
            schedule_time = None
            schedule_day = None
            schedule_custom_interval = None
            schedule_custom_unit = None

            col1, col2 = st.columns(2)
            with col1:
                if schedule_type == "minute":
                    st.info("Test sẽ chạy mỗi phút")
                elif schedule_type == "hourly":
                    minute = st.number_input("Phút", 0, 59, 0, key="schedule_minute")
                    schedule_time = f"00:{minute:02d}"
                elif schedule_type == "custom":
                    schedule_custom_interval = st.number_input("Mỗi", 1, 100, 2, key="schedule_custom_interval")
                    schedule_custom_unit = st.selectbox("Đơn vị", ["phút", "giờ", "ngày", "tuần"], key="schedule_custom_unit")
                else:
                    schedule_time_input = st.time_input("Thời gian", key="schedule_time_input")
                    schedule_time = schedule_time_input.strftime("%H:%M")
            
            with col2:
                if schedule_type == "weekly":
                    schedule_day = st.selectbox("Ngày trong tuần", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], key="schedule_day_select")

            if st.button("Thiết lập lịch"):
                # Tạo thư mục cho site nếu chưa có
                site_dir = os.path.join(SCHEDULED_TESTS_DIR, site)
                os.makedirs(site_dir, exist_ok=True)
                
                saved_file_name = f"{test_name.replace(' ', '_')}_{datetime.datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.xlsx"
                saved_file_path = os.path.join(site_dir, saved_file_name)
                with open(saved_file_path, "wb") as f:
                    f.write(test_file.getbuffer())

                job_config = {
                    "file_path": saved_file_path,
                    "schedule_type": schedule_type,
                    "schedule_time": schedule_time,
                    "schedule_day": schedule_day,
                    "test_name": test_name,
                    "site": site,
                    "custom_interval": schedule_custom_interval,
                    "custom_unit": schedule_custom_unit,
                    "api_url": schedule_api_url,
                    "evaluate_api_url": schedule_evaluate_api_url,
                    "job_id": str(uuid4())
                }
                st.session_state.scheduled_jobs.append(job_config)
                save_scheduled_jobs()  # Save to file
                
                setup_schedule(
                    file_path=job_config["file_path"],
                    schedule_type=job_config["schedule_type"],
                    schedule_time=job_config["schedule_time"],
                    schedule_day=job_config["schedule_day"],
                    test_name=job_config["test_name"],
                    site=job_config["site"],
                    api_url=job_config["api_url"],
                    evaluate_api_url=job_config["evaluate_api_url"],
                    custom_interval=job_config["custom_interval"],
                    custom_unit=job_config["custom_unit"]
                )
                st.success(f"Đã thiết lập lịch chạy test '{test_name}' cho site '{site}'.")
                st.rerun()


with tab4:
    st.subheader("Quản lý test và cập nhật tập test")
    
    site = get_current_site()
    
    st.write("### Lịch sử test")
    if site in st.session_state.test_history and st.session_state.test_history[site]:
        history_df = pd.DataFrame(st.session_state.test_history[site])
        st.dataframe(history_df, use_container_width=True)
    else:
        st.info(f"Chưa có lịch sử test nào cho site {site}")
        
    st.write("### Test cases thất bại")
    if site in st.session_state.failed_tests and st.session_state.failed_tests[site]:
        failed_df = pd.DataFrame(st.session_state.failed_tests[site])
        st.dataframe(failed_df, use_container_width=True)
    else:
        st.info("Chưa có test case thất bại nào")

    st.write("### Kết quả đã lưu")
    site_results_dir = os.path.join(RESULTS_DIR, site)
    if os.path.exists(site_results_dir):
        try:
            all_files = [f for f in os.listdir(site_results_dir) if f.lower().endswith((".xlsx", ".xls"))]
        except Exception as e:
            all_files = []
            st.error(f"Lỗi khi liệt kê file kết quả: {str(e)}")

        if all_files:
            selected_file = st.selectbox("Chọn file kết quả để xem", sorted(all_files, reverse=True), key="saved_result_select")
            selected_path = os.path.join(site_results_dir, selected_file)
            cols = st.columns([1, 1])
            with cols[0]:
                if st.button("Xem preview 5 dòng đầu", key="preview_saved_result"):
                    try:
                        df_saved = pd.read_excel(selected_path)
                        st.write(f"File: `{selected_file}` ({len(df_saved)} dòng)")
                        st.dataframe(df_saved.head(5), use_container_width=True)
                    except Exception as e:
                        st.error(f"Lỗi khi đọc file kết quả: {str(e)}")
            with cols[1]:
                try:
                    with open(selected_path, "rb") as f:
                        st.download_button(
                            label="Tải xuống file kết quả",
                            data=f.read(),
                            file_name=selected_file,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="download_saved_result"
                        )
                except Exception as e:
                    st.error(f"Lỗi khi mở file để tải xuống: {str(e)}")
        else:
            st.info("Chưa có file kết quả nào được lưu cho site này.")
    else:
        st.info("Thư mục kết quả cho site này chưa được tạo.")

# Hiển thị hướng dẫn sử dụng
st.sidebar.subheader("Hướng dẫn sử dụng")
st.sidebar.markdown("""
### Test đơn lẻ
1. Nhập câu hỏi và câu trả lời chuẩn.
2. Nhấn "Test" để xem kết quả.

### Test hàng loạt
1. Tải file Excel.
2. Chọn các câu hỏi muốn test.
3. Nhấn "Test hàng loạt".

### Lập lịch test
1. Tải file test và đặt tên.
2. Thiết lập lịch và nhấn "Thiết lập lịch".

### Quản lý test
1. Xem lịch sử và các test case thất bại.
""")
