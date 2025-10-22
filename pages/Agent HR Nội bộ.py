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

## Cấu hình streamlit
st.set_page_config(
    layout="wide",
    page_title="Agent HR Nội bộ",
    page_icon="✨"
)


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

# Global site variable - được set dựa trên trang hiện tại
SITE = "Agent HR Nội bộ"

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

# Đường dẫn file
RESULTS_DIR = "test_results"
FAILED_TESTS_FILE = os.path.join(RESULTS_DIR, "failed_tests.pkl")
TEST_HISTORY_FILE = os.path.join(RESULTS_DIR, "test_history.pkl")
TEST_CHANGES_FILE = os.path.join(RESULTS_DIR, "test_changes.pkl")

# Tạo thư mục nếu chưa có
os.makedirs(RESULTS_DIR, exist_ok=True)

# --- Các hàm xử lý ---
def get_current_site():
    """Get current site from global variable"""
    return SITE

def filter_results(results, threshold, criterion, filter_type):
    filtered_data = []
    for result in results:
        score = result["evaluate_result"]["scores"].get(criterion, 0)
        if (filter_type == "greater" and score >= threshold) or \
           (filter_type == "less" and score <= threshold):
            filtered_data.append(result)
    return filtered_data

def save_test_results(results, test_name, site):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filename = f"{test_name}_{timestamp}.xlsx"
    filepath = os.path.join(RESULTS_DIR, site, filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    df = pd.DataFrame(results)
    df.to_excel(filepath, index=False)

    # Phân loại kết quả chi tiết
    fail_criterion = st.session_state.get("fail_criterion", "accuracy")
    fail_threshold = st.session_state.get("fail_threshold", 8.0)
    
    num_passed = 0
    num_failed_api = 0
    num_failed_extract = 0
    num_failed_accuracy = 0
    
    for r in results:
        if "failed_details" in r:
            reason = r["failed_details"].get("reason", "")
            if "API" in reason or "Exception" in reason:
                num_failed_api += 1
            elif "evaluate_result" in reason:
                num_failed_extract += 1
            else:
                num_failed_accuracy += 1
        else:
            # Kiểm tra tiêu chí fail
            criterion_score = r["evaluate_result"]["scores"].get(fail_criterion, 0)
            if criterion_score >= fail_threshold:
                num_passed += 1
            else:
                num_failed_accuracy += 1
    
    num_failed = num_failed_api + num_failed_extract + num_failed_accuracy

    history_entry = {
        "timestamp": timestamp,
        "test_name": test_name,
        "num_questions": len(results),
        "num_passed": num_passed,
        "num_failed": num_failed,
        "num_failed_api": num_failed_api,
        "num_failed_extract": num_failed_extract,
        "num_failed_accuracy": num_failed_accuracy,
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
with st.expander("⚙️ Cấu hình API và các tham số", expanded=False):
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Cấu hình API**")
        API_URL = st.text_input("API URL", st.session_state.get("api_url", "https://site1.com"))
        EVALUATE_API_URL = st.text_input("Evaluate API URL", st.session_state.get("evaluate_api_url", "https://site2.com"))
    
    with col2:
        st.write("**Cấu hình Test**")
        MAX_WORKERS = st.slider("Số luồng xử lý đồng thời", 1, 20, 5)
        add_chat_history_global = st.checkbox("Thêm chat history (giả lập đã cung cấp thông tin)", value=False)
    
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write("**Tiêu chí đánh giá fail**")
        fail_criterion = st.selectbox(
            "Chọn tiêu chí",
            ["accuracy", "relevance", "completeness", "clarity", "tone", "average"],
            index=0,
            help="Tiêu chí được sử dụng để xác định test case fail"
        )
    
    with col2:
        st.write("**Ngưỡng fail**")
        fail_threshold = st.number_input(
            "Ngưỡng điểm (< ngưỡng = fail)",
            min_value=0.0,
            max_value=10.0,
            value=8.0,
            step=0.5,
            help="Test case có điểm thấp hơn ngưỡng này sẽ được đánh dấu fail"
        )
    
    with col3:
        st.write("**Tóm tắt cấu hình**")
        st.info(f"Fail nếu **{fail_criterion}** < {fail_threshold}")
    
    st.session_state.api_url = API_URL
    st.session_state.evaluate_api_url = EVALUATE_API_URL
    st.session_state.fail_criterion = fail_criterion
    st.session_state.fail_threshold = fail_threshold

# --- Prompt Management Functions ---
def get_prompt_paths(site):
    """Get prompt file paths for a specific site"""
    prompt_dir = os.path.join("prompts", site)
    return {
        "system_prompt": os.path.join(prompt_dir, "system_prompt.txt"),
        "human_prompt": os.path.join(prompt_dir, "human_prompt.txt")
    }

def get_extract_sections_path(site):
    """Get extract_sections.py file path for a specific site"""
    utils_dir = os.path.join("utils", site)
    return os.path.join(utils_dir, "extract_sections.py")

def load_prompts_for_site(site):
    """Load prompts for a specific site"""
    prompt_paths = get_prompt_paths(site)
    prompts = {}
    
    try:
        if os.path.exists(prompt_paths["system_prompt"]):
            with open(prompt_paths["system_prompt"], "r", encoding="utf-8") as f:
                prompts["system_prompt"] = f.read()
        else:
            prompts["system_prompt"] = ""
            
        if os.path.exists(prompt_paths["human_prompt"]):
            with open(prompt_paths["human_prompt"], "r", encoding="utf-8") as f:
                prompts["human_prompt"] = f.read()
        else:
            prompts["human_prompt"] = ""
            
    except Exception as e:
        logger.error(f"Lỗi khi đọc prompts cho site {site}: {str(e)}")
        prompts = {"system_prompt": "", "human_prompt": ""}
    
    return prompts

def save_prompts_for_site(site, system_prompt, human_prompt):
    """Save prompts for a specific site"""
    prompt_paths = get_prompt_paths(site)
    
    try:
        # Create directory if not exists
        os.makedirs(os.path.dirname(prompt_paths["system_prompt"]), exist_ok=True)
        
        # Save system prompt
        with open(prompt_paths["system_prompt"], "w", encoding="utf-8") as f:
            f.write(system_prompt)
            
        # Save human prompt
        with open(prompt_paths["human_prompt"], "w", encoding="utf-8") as f:
            f.write(human_prompt)
            
        logger.info(f"Đã lưu prompts cho site {site}")
        return True
        
    except Exception as e:
        logger.error(f"Lỗi khi lưu prompts cho site {site}: {str(e)}")
        return False

def load_extract_sections_for_site(site):
    """Load extract_sections.py for a specific site"""
    extract_path = get_extract_sections_path(site)
    
    try:
        if os.path.exists(extract_path):
            with open(extract_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            return ""
    except Exception as e:
        logger.error(f"Lỗi khi đọc extract_sections cho site {site}: {str(e)}")
        return ""

def save_extract_sections_for_site(site, extract_code):
    """Save extract_sections.py for a specific site"""
    extract_path = get_extract_sections_path(site)
    
    try:
        # Create directory if not exists
        os.makedirs(os.path.dirname(extract_path), exist_ok=True)
        
        with open(extract_path, "w", encoding="utf-8") as f:
            f.write(extract_code)
            
        logger.info(f"Đã lưu extract_sections cho site {site}")
        return True
        
    except Exception as e:
        logger.error(f"Lỗi khi lưu extract_sections cho site {site}: {str(e)}")
        return False

def get_default_extract_sections_template(site):
    """Get default extract_sections template based on site"""
    if site == "THFC":
        return '''import requests
import re
from datetime import datetime
import json
import json_repair

def query(API_URL, payload):
    response = requests.post(API_URL, json=payload)
    return response

def extract_json(response_text):
    pattern = r"```json\\s*([\\[{].*?[\\]}])\\s*```"
    match = re.search(pattern, response_text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(1))
        except:
            obj = json_repair.loads(match.group(1))
        return obj
    else:
        obj = json_repair.loads(response_text)
        return obj
    return None

def extract_section(text):
    json_data = extract_json(text)
    print(f"JSON data:\\n{json_data}")
    results = {}
    if json_data:
        results["scores"] = {}
        relevance = json_data["relevance"]
        accuracy = json_data["accuracy"]
        completeness = json_data["completeness"]
        access_control = json_data["access_control"]
        clarity = json_data["clarity"]
        results["scores"]["relevance"] = relevance
        results["scores"]["accuracy"] = accuracy
        results["scores"]["completeness"] = completeness
        results["scores"]["access_control"] = access_control
        results["scores"]["clarity"] = clarity
        results["scores"]["average"] = (relevance + accuracy + completeness + access_control + clarity) / 5
        results["comments"] = json_data["comments"]
        print(f"Extracted: {results}")
        return results
    else:
        return None'''
    else:  # Agent HR Nội bộ
        return '''import requests
import re
from datetime import datetime
import json
import json_repair

def query(API_URL, payload):
    response = requests.post(API_URL, json=payload)
    return response

def extract_json(response_text):
    pattern = r"```json\\s*([\\[{].*?[\\]}])\\s*```"
    match = re.search(pattern, response_text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(1))
        except:
            obj = json_repair.loads(match.group(1))
        return obj
    else:
        obj = json_repair.loads(response_text)
        return obj
    return None

def extract_section(text):
    json_data = extract_json(text)
    print(f"JSON data:\\n{json_data}")
    results = {}
    if json_data:
        results["scores"] = {}
        relevance = json_data["relevance"]
        accuracy = json_data["accuracy"]
        completeness = json_data["completeness"]
        clarity = json_data["clarity"]
        tone = json_data["tone"]
        results["scores"]["relevance"] = relevance
        results["scores"]["accuracy"] = accuracy
        results["scores"]["completeness"] = completeness
        results["scores"]["clarity"] = clarity
        results["scores"]["tone"] = tone
        results["scores"]["average"] = (relevance + accuracy + completeness + clarity + tone) / 5
        results["comments"] = json_data["comments"]
        return results
    else:
        return None'''

def auto_generate_extract_sections_from_prompt(system_prompt):
    """Tự động tạo extract sections code dựa trên system prompt"""
    import re
    
    # Tìm các tiêu chí đánh giá trong system prompt - Có bắt cả mô tả trong ngoặc
    criteria = []
    criteria_descriptions = []
    lines = system_prompt.split('\n')
    
    for line in lines:
        line = line.strip()
        # Tìm pattern ### số. Tên tiêu chí (Mô tả)
        match = re.match(r'^###\s*\d+\.\s*([^(]+?)\s*\(([^)]+)\)\s*$', line, re.IGNORECASE)
        if match:
            criterion = match.group(1).strip()
            description = match.group(2).strip()
            if criterion and len(criterion) < 50:  # Chỉ lấy tên ngắn
                criteria.append(criterion)
                criteria_descriptions.append(description)
        else:
            # Thử pattern không có mô tả
            match = re.match(r'^###\s*\d+\.\s*([^(]+?)\s*$', line, re.IGNORECASE)
            if match:
                criterion = match.group(1).strip()
                if criterion and len(criterion) < 50:
                    criteria.append(criterion)
                    criteria_descriptions.append("")
    
    # Nếu không tìm thấy, thử tìm với format khác (dấu -)
    if not criteria:
        for line in lines:
            line = line.strip()
            # Tìm pattern - Tên tiêu chí (Mô tả)
            match = re.match(r'^-\s*([^(]+?)\s*\(([^)]+)\)\s*$', line, re.IGNORECASE)
            if match:
                criterion = match.group(1).strip()
                description = match.group(2).strip()
                if criterion and len(criterion) < 50:
                    criteria.append(criterion)
                    criteria_descriptions.append(description)
            else:
                # Thử pattern không có mô tả
                match = re.match(r'^-\s*([^(]+?)\s*$', line, re.IGNORECASE)
                if match:
                    criterion = match.group(1).strip()
                    if criterion and len(criterion) < 50:
                        criteria.append(criterion)
                        criteria_descriptions.append("")
    
    # Chuẩn hóa tên criteria thành lowercase và thay khoảng trắng bằng _
    normalized_criteria = []
    for criterion in criteria:
        # Loại bỏ số thứ tự và ký tự đặc biệt
        clean_name = re.sub(r'^\d+\.?\s*', '', criterion)
        clean_name = re.sub(r'[^\w\s]', '', clean_name)
        clean_name = clean_name.strip().lower().replace(' ', '_')
        normalized_criteria.append(clean_name)
    
    # Loại bỏ duplicate và giữ thứ tự, đồng thời giữ cả description
    seen = set()
    unique_criteria = []
    unique_descriptions = []
    for i, criterion in enumerate(normalized_criteria):
        if criterion not in seen:
            seen.add(criterion)
            unique_criteria.append(criterion)
            unique_descriptions.append(criteria_descriptions[i] if i < len(criteria_descriptions) else "")
    
    # Tạo code extract sections
    code_lines = [
        'import requests',
        'import re',
        'from datetime import datetime',
        'import json',
        'import json_repair',
        '',
        'def query(API_URL, payload):',
        '    response = requests.post(API_URL, json=payload)',
        '    return response',
        '',
        'def extract_json(response_text):',
        '    pattern = r"```json\\\\s*([\\\\[{].*?[\\\\]}])\\\\s*```"',
        '    match = re.search(pattern, response_text, re.DOTALL)',
        '    if match:',
        '        try:',
        '            obj = json.loads(match.group(1))',
        '        except:',
        '            obj = json_repair.loads(match.group(1))',
        '        return obj',
        '    else:',
        '        obj = json_repair.loads(response_text)',
        '        return obj',
        '    return None',
        '',
        'def extract_section(text):',
        '    json_data = extract_json(text)',
        '    print(f"JSON data:\\\\n{json_data}")',
        '    results = {}',
        '    if json_data:',
        '        results["scores"] = {}',
    ]
    
    # Thêm các dòng extract cho từng criteria
    for criterion in unique_criteria:
        code_lines.append(f'        {criterion} = json_data["{criterion}"]')
        code_lines.append(f'        results["scores"]["{criterion}"] = {criterion}')
    
    # Tính average
    criteria_list = ', '.join(unique_criteria)
    code_lines.extend([
        f'        results["scores"]["average"] = ({criteria_list}) / {len(unique_criteria)}',
        '        results["comments"] = json_data["comments"]',
        '        print(f"Extracted: {results}")',
        '        return results',
        '    else:',
        '        return None'
    ])
    
    # Return cả code và mapping info để hiển thị
    return {
        'code': '\\n'.join(code_lines),
        'criteria': criteria,
        'normalized_criteria': unique_criteria,
        'descriptions': unique_descriptions
    }


# Tải prompts
def load_prompts():
    global evaluate_system_prompt
    try:
        site = get_current_site()
        prompts = load_prompts_for_site(site)
        evaluate_system_prompt = prompts["system_prompt"]
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
        
        # Load human prompt for current site
        site_prompts = load_prompts_for_site(site or get_current_site())
        human_prompt_template = site_prompts["human_prompt"]
        
        # Format human prompt with actual values
        evaluate_human_prompt = human_prompt_template.format(
            question=question,
            true_answer=true_answer,
            agent_answer=site_response
        )
        
        evaluate_payload = {
            "question": "Đánh giá câu trả lời từ agent so với câu trả lời chuẩn (true_answer)",
            "overrideConfig": {
                "systemMessagePrompt": evaluate_system_prompt,
                "humanMessagePrompt": evaluate_human_prompt
            }
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
                
            # Import site-specific extract_section function
            import sys
            import importlib.util
            
            site = site or get_current_site()
            extract_path = get_extract_sections_path(site)
            
            if os.path.exists(extract_path):
                spec = importlib.util.spec_from_file_location("extract_sections", extract_path)
                extract_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(extract_module)
                evaluate_result = extract_module.extract_section(evaluate_response_text)
            else:
                # Fallback to default extract_section
                evaluate_result = extract_section(evaluate_response_text)
                
            # Đảm bảo evaluate_result không phải None
            if evaluate_result is None:
                evaluate_result = {"scores": {}, "comments": "Lỗi: Không thể trích xuất kết quả đánh giá"}
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
                    # Kiểm tra evaluate_result có tồn tại và không phải None
                    if (result.get("evaluate_result") and 
                        isinstance(result["evaluate_result"], dict) and 
                        result["evaluate_result"].get("scores") and
                        isinstance(result["evaluate_result"]["scores"], dict)):
                        
                        # Kiểm tra tiêu chí fail
                        fail_criterion = st.session_state.get("fail_criterion", "accuracy")
                        fail_threshold = st.session_state.get("fail_threshold", 8.0)
                        criterion_score = result["evaluate_result"]["scores"].get(fail_criterion, 0)
                        
                        if criterion_score < fail_threshold:
                            result["failed_details"] = {
                                "timestamp": datetime.datetime.now().isoformat(),
                                "test_name": test_name,
                                "reason": f"{fail_criterion} thấp (< {fail_threshold})",
                                "expected_output": result["true_answer"],
                                "actual_output": result["site_response"],
                                "scores": result["evaluate_result"]["scores"],
                                f"{fail_criterion}_score": criterion_score
                            }
                            failed_questions.append((question, f"{fail_criterion} thấp", result))
                        results.append(result)
                    else:
                        # evaluate_result không hợp lệ hoặc None
                        error_result = {
                            "chat_id": str(uuid4()), "question": question, "true_answer": true_answer,
                            "site_response": result.get("site_response", "[Lỗi khi xử lý]"),
                            "evaluate_result": {"scores": {}, "comments": "Lỗi: evaluate_result không hợp lệ"},
                            "failed_details": {"timestamp": datetime.datetime.now().isoformat(), "test_name": test_name, "reason": "Lỗi evaluate_result", "error_message": "evaluate_result is None or invalid"}
                        }
                        results.append(error_result)
                        failed_questions.append((question, "Lỗi evaluate_result", "evaluate_result is None or invalid"))
                else:
                    error_result = {
                        "chat_id": str(uuid4()), "question": question, "true_answer": true_answer,
                        "site_response": "[Lỗi khi xử lý]",
                        "evaluate_result": {"scores": {}, "comments": f"Lỗi: {result}"},
                        "failed_details": {"timestamp": datetime.datetime.now().isoformat("%Y-%m-%d %H:%M:%S"), "test_name": test_name, "reason": "Lỗi xử lý API", "error_message": str(result)}
                    }
                    results.append(error_result)
                    failed_questions.append((question, "Lỗi xử lý API", result))
            except Exception as e:
                error_message = f"Lỗi: {str(e)}"
                error_result = {
                    "chat_id": str(uuid4()), "question": question, "true_answer": true_answer,
                    "site_response": "[Lỗi khi xử lý]",
                    "evaluate_result": {"scores": {}, "comments": error_message},
                    "failed_details": {"timestamp": datetime.datetime.now().isoformat("%Y-%m-%d %H:%M:%S"), "test_name": test_name, "reason": "Exception", "error_message": str(e)}
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

# Initialize schedule_initialized flag
if 'schedule_initialized' not in st.session_state:
    st.session_state.schedule_initialized = False

# Only setup schedule once when app starts, not on every rerun
# This prevents schedule from being reset every time user interacts with the page
if not st.session_state.schedule_initialized:
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
    
    st.session_state.schedule_initialized = True

# Giao diện Streamlit
st.title("🤖 Agent Testing")

# Tạo các tab
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Test đơn lẻ", "Test hàng loạt", "Lập lịch test", "Quản lý test", "Quản lý Prompts"])

with tab1:
    st.subheader("✏️ Test đơn lẻ")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        question = st.text_area("📝 Câu hỏi:", height=150, placeholder="Nhập câu hỏi test...")
    
    with col2:
        true_answer = st.text_area("✅ Câu trả lời chuẩn:", height=150, placeholder="Nhập câu trả lời mẫu...")
    
    if add_chat_history_global:
        with st.expander("💬 Thiết lập chat history", expanded=False):
            if 'chat_history' not in st.session_state or st.session_state.chat_history is None:
                st.session_state.chat_history = [
                    {"role": "apiMessage", "content": "Vui lòng cung cấp họ tên, số điện thoại, trường THPT và tỉnh thành sinh sống để tôi có thể tư vấn tốt nhất. Lưu ý, thông tin bạn cung cấp cần đảm bảo tính chính xác."},
                    {"role": "userMessage", "content": "[Cung cấp thông tin]"}
                ]
            
            # Sử dụng một list tạm để tránh lỗi khi xóa
            new_history = []
            for i, msg in enumerate(st.session_state.chat_history):
                cols = st.columns([2, 8, 1])
                role = cols[0].selectbox(f"Role {i+1}", ["apiMessage", "userMessage"], key=f"role_{i}", index=["apiMessage", "userMessage"].index(msg["role"]))
                content = cols[1].text_area(f"Nội dung {i+1}", value=msg["content"], key=f"content_{i}")
                if not cols[2].button("🗑️", key=f"delete_{i}", help="Xóa message này"):
                    new_history.append({"role": role, "content": content})
            st.session_state.chat_history = new_history

            if st.button("➕ Thêm message"):
                st.session_state.chat_history.append({"role": "userMessage", "content": ""})
                st.rerun()

    col1, col2, col3 = st.columns([1, 1, 2])
    with col2:
        if st.button("▶️ Chạy Test", type="primary", use_container_width=True):
            if question and true_answer:
                with st.spinner("⏳ Đang xử lý..."):
                    history = st.session_state.chat_history if (add_chat_history_global and st.session_state.chat_history) else None
                    result = process_single_question(question, true_answer, 0, 1, add_chat_history=add_chat_history_global, custom_history=history, site=get_current_site())
                
                if isinstance(result, dict):
                    st.success("✅ Xử lý thành công!")
                    
                    st.write("---")
                    st.subheader("📊 Kết quả")
                    
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        st.write("**💬 Câu trả lời từ Agent:**")
                        st.info(result["site_response"])
                    
                    with col2:
                        st.write("**📈 Điểm đánh giá:**")
                        scores = result["evaluate_result"]["scores"]
                        for metric, score in scores.items():
                            st.metric(metric.capitalize(), f"{score}/10")
                    
                    st.write("**💭 Nhận xét và góp ý cải thiện:**")
                    st.text_area("Comments", value=result["evaluate_result"]["comments"], height=150, disabled=True)
                else:
                    st.error(f"❌ Lỗi: {result}")
            else:
                st.warning("⚠️ Vui lòng nhập đầy đủ câu hỏi và câu trả lời chuẩn")

with tab2:
    st.subheader("📝 Test hàng loạt từ file Excel")
    
    if add_chat_history_global:
        with st.expander("💬 Thiết lập chat history", expanded=False):
            # Tương tự tab 1, hiển thị và cho phép chỉnh sửa chat history
            if 'chat_history' not in st.session_state or st.session_state.chat_history is None:
                st.session_state.chat_history = [
                    {"role": "apiMessage", "content": "Vui lòng cung cấp họ tên, số điện thoại, trường THPT và tỉnh thành sinh sống để tôi có thể tư vấn tốt nhất. Lưu ý, thông tin bạn cung cấp cần đảm bảo tính chính xác."},
                    {"role": "userMessage", "content": "[Cung cấp thông tin]"}
                ]
            
            new_history = []
            for i, msg in enumerate(st.session_state.chat_history):
                cols = st.columns([2, 8, 1])
                role = cols[0].selectbox(f"Role {i+1}", ["apiMessage", "userMessage"], key=f"role_batch_{i}", index=["apiMessage", "userMessage"].index(msg["role"]))
                content = cols[1].text_area(f"Nội dung {i+1}", value=msg["content"], key=f"content_batch_{i}")
                if not cols[2].button("🗑️", key=f"delete_batch_{i}", help="Xóa message này"):
                    new_history.append({"role": role, "content": content})
            st.session_state.chat_history = new_history

            if st.button("➕ Thêm message", key="add_message_batch"):
                st.session_state.chat_history.append({"role": "userMessage", "content": ""})
                st.rerun()

    col1, col2 = st.columns([3, 1])
    with col1:
        uploaded_file = st.file_uploader("📁 Chọn file Excel chứa test cases", type=['xlsx', 'xls'])
    
    with col2:
        st.write("")  # Spacer
        st.write("")  # Spacer
        if uploaded_file:
            st.success("✅ File đã tải lên")
    
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            df = df.dropna(subset=[df.columns[0], df.columns[1]])
            questions = df.iloc[:, 0].tolist()
            true_answers = df.iloc[:, 1].tolist()
            
            # Khởi tạo edited test cases trong session state nếu chưa có
            if 'test_cases_df' not in st.session_state or st.session_state.get('current_file') != uploaded_file.name:
                st.session_state.test_cases_df = pd.DataFrame({
                    'Chọn': [True] * len(questions),  # Checkbox column
                    'Câu hỏi': questions, 
                    'Câu trả lời chuẩn': true_answers
                })
                st.session_state.current_file = uploaded_file.name
            
            st.write("### 📋 Danh sách test cases (có thể chỉnh sửa)")
            st.info("💡 Tip: Bạn có thể click vào ô để chỉnh sửa trực tiếp câu hỏi và câu trả lời. Tick ✓ vào cột 'Chọn' để chọn test case muốn chạy.")
            
            # Sử dụng st.data_editor để có thể chỉnh sửa
            edited_df = st.data_editor(
                st.session_state.test_cases_df,
                use_container_width=True,
                hide_index=True,
                num_rows="dynamic",  # Cho phép thêm/xóa dòng
                column_config={
                    "Chọn": st.column_config.CheckboxColumn(
                        "Chọn",
                        help="Tick để chọn test case này",
                        default=True,
                        width="small"
                    ),
                    "Câu hỏi": st.column_config.TextColumn(
                        "Câu hỏi",
                        help="Nội dung câu hỏi",
                        width="large",
                        required=True
                    ),
                    "Câu trả lời chuẩn": st.column_config.TextColumn(
                        "Câu trả lời chuẩn",
                        help="Câu trả lời mẫu để so sánh",
                        width="large",
                        required=True
                    ),
                },
                key="test_cases_editor"
            )
            
            # Cập nhật session state với dữ liệu đã chỉnh sửa
            st.session_state.test_cases_df = edited_df
            
            # Lọc các dòng được chọn
            selected_df = edited_df[edited_df['Chọn'] == True]
            selected_rows = selected_df.index.tolist()
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                st.metric("📊 Tổng test cases", len(edited_df))
            with col2:
                st.metric("✅ Test cases được chọn", len(selected_df))
            with col3:
                if st.button("▶️ Chạy test", type="primary", use_container_width=True):
                    if len(selected_df) > 0:
                        selected_questions = selected_df['Câu hỏi'].tolist()
                        selected_true_answers = selected_df['Câu trả lời chuẩn'].tolist()
                        
                        with st.spinner("⏳ Đang xử lý test cases..."):
                            history = st.session_state.chat_history if (add_chat_history_global and st.session_state.chat_history) else None
                            results, failed_questions = process_questions_batch(
                                selected_questions, 
                                selected_true_answers, 
                                add_chat_history=add_chat_history_global, 
                                custom_history=history, 
                                test_name=uploaded_file.name, 
                                site=get_current_site()
                            )
                        
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
                        
                        st.write("---")
                        st.subheader(f"📊 Kết quả đánh giá ({len(results)} câu hỏi)")
                        
                        # Hiển thị metrics tổng quan
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("✅ Passed", sum(1 for r in results if "failed_details" not in r))
                        with col2:
                            st.metric("❌ Failed", sum(1 for r in results if "failed_details" in r))
                        with col3:
                            avg_score = sum(r["evaluate_result"]["scores"].get("average", 0) for r in results) / len(results) if results else 0
                            st.metric("📈 Điểm TB", f"{avg_score:.2f}")
                        with col4:
                            pass_rate = (sum(1 for r in results if "failed_details" not in r) / len(results) * 100) if results else 0
                            st.metric("📊 Tỷ lệ pass", f"{pass_rate:.1f}%")
                        
                        st.dataframe(results_df, use_container_width=True, hide_index=True)
                        
                        col1, col2 = st.columns([1, 1])
                        with col1:
                            st.download_button(
                                label="📥 Tải xuống kết quả (CSV)", 
                                data=results_df.to_csv(index=False).encode('utf-8'), 
                                file_name=f'evaluation_results_{uploaded_file.name}.csv', 
                                mime='text/csv',
                                use_container_width=True
                            )
                        with col2:
                            if failed_questions:
                                st.warning(f"⚠️ Có {len(failed_questions)} câu hỏi xử lý thất bại")
                            else:
                                st.success(f"✅ Đã hoàn thành đánh giá {len(results)} câu hỏi")
                    else:
                        st.warning("⚠️ Vui lòng chọn ít nhất một test case để chạy")
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
                # Chỉ xóa file test (không phải kết quả test)
                if os.path.exists(existing_job['file_path']):
                    # Kiểm tra xem có phải file test hay file kết quả
                    if 'scheduled_tests' in existing_job['file_path']:
                        # Đây là file test cho scheduled job - có thể xóa
                        os.remove(existing_job['file_path'])
                        st.info(f"Đã xóa file test: {os.path.basename(existing_job['file_path'])}")
                    else:
                        st.warning("File này có thể chứa kết quả test quan trọng. Không xóa.")
                
                # Remove from scheduled jobs
                remove_scheduled_job_for_site(site)
                
                # Reset schedule initialization flag to recreate schedule
                st.session_state.schedule_initialized = False
                
                st.success(f"Đã xóa cấu hình lịch test cho site '{site}'. Kết quả test trước đó vẫn được giữ lại.")
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
                        
                        # Reset schedule initialization flag to recreate schedule
                        st.session_state.schedule_initialized = False
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
                
                # Reset schedule initialization flag to recreate schedule
                st.session_state.schedule_initialized = False
                
                st.success(f"Đã thiết lập lịch chạy test '{test_name}' cho site '{site}'.")
                st.rerun()


with tab4:
    st.subheader("Quản lý test và cập nhật tập test")
    
    site = get_current_site()
    
    # Dashboard tổng quan
    st.write("### 📊 Dashboard Tổng Quan")
    
    if site in st.session_state.test_history and st.session_state.test_history[site]:
        # Tính toán thống kê tổng quan
        total_tests = len(st.session_state.test_history[site])
        total_questions = sum(test.get('num_questions', 0) for test in st.session_state.test_history[site])
        total_passed = sum(test.get('num_passed', 0) for test in st.session_state.test_history[site])
        total_failed = sum(test.get('num_failed', 0) for test in st.session_state.test_history[site])
        total_api_errors = sum(test.get('num_failed_api', 0) for test in st.session_state.test_history[site])
        total_extract_errors = sum(test.get('num_failed_extract', 0) for test in st.session_state.test_history[site])
        total_accuracy_errors = sum(test.get('num_failed_accuracy', 0) for test in st.session_state.test_history[site])
        
        overall_pass_rate = (total_passed / total_questions) * 100 if total_questions > 0 else 0
        api_error_rate = (total_api_errors / total_failed) * 100 if total_failed > 0 else 0
        
        # Dashboard với HTML/CSS đẹp hơn
        st.markdown(""" 
        <style>
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            color: white;
            text-align: center;
            margin: 5px;
        }
        .metric-card-success {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }
        .metric-card-danger {
            background: linear-gradient(135deg, #ee0979 0%, #ff6a00 100%);
        }
        .metric-card-warning {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        .metric-card-info {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }
        .metric-label {
            font-size: 14px;
            font-weight: 500;
            opacity: 0.9;
            margin-bottom: 5px;
        }
        .metric-value {
            font-size: 32px;
            font-weight: bold;
            margin: 10px 0;
        }
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }
        @media (max-width: 1200px) {
            .dashboard-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }
        @media (max-width: 600px) {
            .dashboard-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Grid 1: Thống kê chính
        st.markdown(f"""
        <div class="dashboard-grid">
            <div class="metric-card metric-card-info">
                <div class="metric-label">📈 Tổng số test</div>
                <div class="metric-value">{total_tests}</div>
            </div>
            <div class="metric-card metric-card-info">
                <div class="metric-label">❓ Tổng câu hỏi</div>
                <div class="metric-value">{total_questions}</div>
            </div>
            <div class="metric-card metric-card-success">
                <div class="metric-label">✅ Tổng passed</div>
                <div class="metric-value">{total_passed}</div>
            </div>
            <div class="metric-card metric-card-danger">
                <div class="metric-label">❌ Tổng failed</div>
                <div class="metric-value">{total_failed}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Grid 2: Phân loại lỗi và tỷ lệ
        st.markdown(f"""
        <div class="dashboard-grid">
            <div class="metric-card">
                <div class="metric-label">📊 Tỷ lệ pass tổng</div>
                <div class="metric-value">{overall_pass_rate:.1f}%</div>
            </div>
            <div class="metric-card metric-card-danger">
                <div class="metric-label">🔴 API Errors</div>
                <div class="metric-value">{total_api_errors}</div>
            </div>
            <div class="metric-card metric-card-warning">
                <div class="metric-label">🟡 Extract Errors</div>
                <div class="metric-value">{total_extract_errors}</div>
            </div>
            <div class="metric-card metric-card-warning">
                <div class="metric-label">🟠 Accuracy Errors</div>
                <div class="metric-value">{total_accuracy_errors}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Biểu đồ phân bố lỗi
        if total_failed > 0:
            st.write("### 📈 Phân bố lỗi")
            error_data = {
                'Loại lỗi': ['API Error', 'Extract Error', 'Accuracy < 8'],
                'Số lượng': [total_api_errors, total_extract_errors, total_accuracy_errors],
                'Tỷ lệ %': [
                    (total_api_errors / total_failed) * 100,
                    (total_extract_errors / total_failed) * 100,
                    (total_accuracy_errors / total_failed) * 100
                ]
            }
            error_df = pd.DataFrame(error_data)
            st.dataframe(error_df, use_container_width=True)
    
    st.write("### 📋 Lịch sử test")
    if site in st.session_state.test_history and st.session_state.test_history[site]:
        history_df = pd.DataFrame(st.session_state.test_history[site])
        
        # Hiển thị dataframe với khả năng chọn dòng
        selected_history = st.dataframe(
            history_df, 
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="history_selection"
        )
        
        # Hiển thị chi tiết kết quả nếu có dòng được chọn
        if selected_history.selection.rows:
            selected_row_index = selected_history.selection.rows[0]
            selected_test = st.session_state.test_history[site][selected_row_index]
            
            st.write("### Chi tiết kết quả test")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Tên test", selected_test.get('test_name', 'N/A'))
                st.metric("Số câu hỏi", selected_test.get('num_questions', 0))
            
            with col2:
                st.metric("✅ Passed", selected_test.get('num_passed', 0))
                st.metric("❌ Failed", selected_test.get('num_failed', 0))
            
            with col3:
                st.metric("Thời gian", selected_test.get('timestamp', 'N/A'))
                pass_rate = (selected_test.get('num_passed', 0) / selected_test.get('num_questions', 1)) * 100
                st.metric("Tỷ lệ pass", f"{pass_rate:.1f}%")
            
            # Hiển thị phân loại lỗi chi tiết
            st.write("### 📊 Phân loại lỗi chi tiết")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("🔴 API Error", selected_test.get('num_failed_api', 0))
            with col2:
                st.metric("🟡 Extract Error", selected_test.get('num_failed_extract', 0))
            with col3:
                st.metric("🟠 Accuracy < 8", selected_test.get('num_failed_accuracy', 0))
            with col4:
                total_failed = selected_test.get('num_failed', 0)
                if total_failed > 0:
                    api_rate = (selected_test.get('num_failed_api', 0) / total_failed) * 100
                    st.metric("API Error %", f"{api_rate:.1f}%")
            
            # Hiển thị file kết quả nếu có
            if 'filename' in selected_test:
                st.write("### File kết quả")
                result_file_path = os.path.join(RESULTS_DIR, site, selected_test['filename'])
                
                if os.path.exists(result_file_path):
                    try:
                        result_df = pd.read_excel(result_file_path)
                        st.write(f"**File:** `{selected_test['filename']}` ({len(result_df)} dòng)")
                        
                        # Hiển thị preview 10 dòng đầu tiên
                        st.write("**Preview kết quả:**")
                        st.dataframe(result_df.head(10), use_container_width=True)
                        
                        # Nút tải xuống
                        with open(result_file_path, "rb") as f:
                            st.download_button(
                                label="📥 Tải xuống file kết quả",
                                data=f.read(),
                                file_name=selected_test['filename'],
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"download_{selected_test['timestamp']}"
                            )
                        
                        # Hiển thị bảng các câu fail với phân loại
                        st.write("### 🔍 Chi tiết các câu fail")
                        
                        # Đọc file kết quả để lấy chi tiết
                        try:
                            result_df = pd.read_excel(result_file_path)
                            
                            # Tạo bảng fail với phân loại
                            failed_rows = []
                            for idx, row in result_df.iterrows():
                                if 'failed_details' in str(row.to_dict()):
                                    # Parse failed_details từ string nếu cần
                                    failed_details = row.get('failed_details', {})
                                    if isinstance(failed_details, str):
                                        try:
                                            import ast
                                            failed_details = ast.literal_eval(failed_details)
                                        except:
                                            failed_details = {}
                                    
                                    reason = failed_details.get('reason', 'Unknown')
                                    error_type = "🔴 API Error" if "API" in reason or "Exception" in reason else \
                                               "🟡 Extract Error" if "evaluate_result" in reason else \
                                               "🟠 Accuracy < 8" if "Accuracy" in reason else "❓ Unknown"
                                    
                                    failed_rows.append({
                                        'Câu hỏi': row.get('question', 'N/A')[:100] + '...' if len(str(row.get('question', ''))) > 100 else row.get('question', 'N/A'),
                                        'Loại lỗi': error_type,
                                        'Lý do': reason,
                                        'Accuracy': row.get('accuracy', 0) if 'accuracy' in str(row) else 'N/A',
                                        'Average': row.get('average', 0) if 'average' in str(row) else 'N/A'
                                    })
                            
                            if failed_rows:
                                failed_df = pd.DataFrame(failed_rows)
                                st.dataframe(failed_df, use_container_width=True)
                            else:
                                st.info("Không có câu nào fail trong test này")
                                
                        except Exception as e:
                            st.error(f"Lỗi khi đọc chi tiết fail: {str(e)}")
                            
                    except Exception as e:
                        st.error(f"Lỗi khi đọc file kết quả: {str(e)}")
                else:
                    st.warning("File kết quả không tồn tại")
    else:
        st.info(f"Chưa có lịch sử test nào cho site {site}")
        
    # st.write("### Test cases thất bại")
    # if site in st.session_state.failed_tests and st.session_state.failed_tests[site]:
    #     failed_df = pd.DataFrame(st.session_state.failed_tests[site])
        
    #     # Hiển thị dataframe với khả năng chọn dòng
    #     selected_failed = st.dataframe(
    #         failed_df, 
    #         use_container_width=True,
    #         hide_index=True,
    #         on_select="rerun",
    #         selection_mode="single-row",
    #         key="failed_selection"
    #     )
        
    #     # Hiển thị chi tiết test case thất bại nếu có dòng được chọn
    #     if selected_failed.selection.rows:
    #         selected_row_index = selected_failed.selection.rows[0]
    #         selected_failed_test = st.session_state.failed_tests[site][selected_row_index]
            
    #         st.write("### Chi tiết test case thất bại")
            
    #         # Hiển thị thông tin cơ bản
    #         col1, col2 = st.columns(2)
            
    #         with col1:
    #             st.write("**Thông tin test:**")
    #             st.write(f"- **Câu hỏi:** {selected_failed_test.get('question', 'N/A')}")
    #             st.write(f"- **Chat ID:** {selected_failed_test.get('chat_id', 'N/A')}")
            
    #         with col2:
    #             st.write("**Kết quả đánh giá:**")
    #             scores = selected_failed_test.get('evaluate_result', {}).get('scores', {})
    #             for metric, score in scores.items():
    #                 st.write(f"- **{metric}:** {score}")
            
    #         # Hiển thị câu trả lời
    #         st.write("**Câu trả lời chuẩn:**")
    #         st.text_area("True Answer", value=selected_failed_test.get('true_answer', ''), height=100, disabled=True)
            
    #         st.write("**Câu trả lời từ Agent:**")
    #         st.text_area("Agent Answer", value=selected_failed_test.get('site_response', ''), height=100, disabled=True)
            
    #         # Hiển thị nhận xét
    #         comments = selected_failed_test.get('evaluate_result', {}).get('comments', '')
    #         if comments:
    #             st.write("**Nhận xét và góp ý:**")
    #             st.text_area("Comments", value=comments, height=100, disabled=True)
            
    #         # Hiển thị thông tin lỗi nếu có
    #         failed_details = selected_failed_test.get('failed_details', {})
    #         if failed_details:
    #             st.write("**Chi tiết lỗi:**")
    #             st.write(f"- **Thời gian:** {failed_details.get('timestamp', 'N/A')}")
    #             st.write(f"- **Tên test:** {failed_details.get('test_name', 'N/A')}")
    #             st.write(f"- **Lý do:** {failed_details.get('reason', 'N/A')}")
    #             if 'error_message' in failed_details:
    #                 st.write(f"- **Thông báo lỗi:** {failed_details['error_message']}")
    # else:
    #     st.info("Chưa có test case thất bại nào")

    # st.write("### Kết quả đã lưu")
    # site_results_dir = os.path.join(RESULTS_DIR, site)
    # if os.path.exists(site_results_dir):
    #     try:
    #         all_files = [f for f in os.listdir(site_results_dir) if f.lower().endswith((".xlsx", ".xls"))]
    #     except Exception as e:
    #         all_files = []
    #         st.error(f"Lỗi khi liệt kê file kết quả: {str(e)}")

    #     if all_files:
    #         selected_file = st.selectbox("Chọn file kết quả để xem", sorted(all_files, reverse=True), key="saved_result_select")
    #         selected_path = os.path.join(site_results_dir, selected_file)
    #         cols = st.columns([1, 1])
    #         with cols[0]:
    #             if st.button("Xem preview 5 dòng đầu", key="preview_saved_result"):
    #                 try:
    #                     df_saved = pd.read_excel(selected_path)
    #                     st.write(f"File: `{selected_file}` ({len(df_saved)} dòng)")
    #                     st.dataframe(df_saved.head(5), use_container_width=True)
    #                 except Exception as e:
    #                     st.error(f"Lỗi khi đọc file kết quả: {str(e)}")
    #         with cols[1]:
    #             try:
    #                 with open(selected_path, "rb") as f:
    #                     st.download_button(
    #                         label="Tải xuống file kết quả",
    #                         data=f.read(),
    #                         file_name=selected_file,
    #                         mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    #                         key="download_saved_result"
    #                     )
    #             except Exception as e:
    #                 st.error(f"Lỗi khi mở file để tải xuống: {str(e)}")
    #     else:
    #         st.info("Chưa có file kết quả nào được lưu cho site này.")
    # else:
    #     st.info("Thư mục kết quả cho site này chưa được tạo.")

with tab5:
    # Custom CSS cho tab Quản lý Prompts
    st.markdown("""
    <style>
    /* Styling cho buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
        border: 1px solid #e0e0e0;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
    
    /* Styling cho text areas */
    .stTextArea textarea {
        border-radius: 8px;
        border: 2px solid #e0e0e0;
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        font-size: 13px;
    }
    
    .stTextArea textarea:focus {
        border-color: #4CAF50;
        box-shadow: 0 0 0 2px rgba(76, 175, 80, 0.2);
    }
    
    /* Spacing cho columns */
    .row-widget.stHorizontal {
        gap: 15px;
    }
    
    /* Styling cho headers */
    h3 {
        color: #1f77b4;
        border-bottom: 2px solid #1f77b4;
        padding-bottom: 8px;
        margin-top: 20px;
    }
    
    /* Card-like containers */
    .stExpander {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        margin-bottom: 10px;
    }
    
    /* Info boxes */
    .stAlert {
        border-radius: 8px;
    }
    
    /* Dataframe styling */
    .dataframe {
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* Button container spacing */
    div[data-testid="column"] {
        padding: 5px;
    }
    
    /* Primary button highlight */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
    }
    
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.subheader("Quản lý Prompts và Extract Sections")
    
    site = get_current_site()
    st.write(f"**Site hiện tại:** {site}")
    
    # Load current prompts
    # Check if we need to force reload from file (reset button was clicked)
    if st.session_state.get('prompt_reset_trigger', False):
        prompts = load_prompts_for_site(site)
        st.session_state.prompt_reset_trigger = False
    else:
        prompts = load_prompts_for_site(site)
    
    current_extract_code = load_extract_sections_for_site(site)
    
    # Prompt Management Section
    st.write("### 📝 Quản lý Prompts")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**System Prompt**")
        system_prompt = st.text_area(
            "System Prompt", 
            value=prompts["system_prompt"], 
            height=300,
            key="system_prompt_editor"
        )
    
    with col2:
        st.write("**Human Prompt**")
        human_prompt = st.text_area(
            "Human Prompt", 
            value=prompts["human_prompt"], 
            height=300,
            key="human_prompt_editor"
        )
    
    # Save prompts button với styling đẹp hơn
    st.write("")  # Spacing
    col1, col2, col3, col4 = st.columns([1, 1, 1, 3])
    with col1:
        if st.button("💾 Lưu Prompts", key="save_prompts", use_container_width=True):
            if save_prompts_for_site(site, system_prompt, human_prompt):
                st.success("✅ Đã lưu prompts thành công!")
                # Clear any cached values
                if 'prompt_reset_trigger' in st.session_state:
                    del st.session_state.prompt_reset_trigger
                st.rerun()
            else:
                st.error("❌ Lỗi khi lưu prompts!")
    
    with col2:
        if st.button("🔄 Reset Prompts", key="reset_prompts", use_container_width=True):
            # Set a flag to trigger reload from file
            st.session_state.prompt_reset_trigger = True
            st.rerun()
    
    st.write("")  # Spacing
    
    # Extract Sections Management Section
    st.write("### 🔧 Quản lý Extract Sections")
    
    # Tự động phân tích prompt và hiển thị mapping
    if system_prompt:
        # Tự động phân tích prompt hiện tại
        result = auto_generate_extract_sections_from_prompt(system_prompt)
        
        # Hiển thị mapping preview
        st.write("**Mapping được phát hiện từ System Prompt:**")
        
        # Hiển thị mapping table
        if result and result.get('normalized_criteria'):
            mapping_data = []
            for i, criterion in enumerate(result['normalized_criteria']):
                original_criterion = result['criteria'][i] if i < len(result['criteria']) else criterion
                description = result['descriptions'][i] if i < len(result['descriptions']) else ""
                
                # Nếu không có description từ prompt, dùng mô tả mặc định
                if not description:
                    if 'relevance' in criterion:
                        description = 'Mức độ liên quan đến câu hỏi'
                    elif 'accuracy' in criterion:
                        description = 'Độ chính xác của thông tin'
                    elif 'completeness' in criterion:
                        description = 'Tính đầy đủ của câu trả lời'
                    elif 'access_control' in criterion:
                        description = 'Kiểm soát truy cập và bảo mật'
                    elif 'clarity' in criterion:
                        description = 'Tính rõ ràng và dễ hiểu'
                    elif 'tone' in criterion:
                        description = 'Giọng điệu và thái độ'
                    else:
                        description = 'Tiêu chí khác'
                
                mapping_data.append({
                    'Tiêu chí trong Prompt': original_criterion,
                    'Key trong JSON': criterion,
                    'Mô tả': description
                })
            
            mapping_df = pd.DataFrame(mapping_data)
            st.dataframe(mapping_df, use_container_width=True)
        else:
            st.warning("Không tìm thấy tiêu chí nào trong System Prompt")
        
        st.write("")  # Spacing
        col1, col2, col3, col4 = st.columns([1, 1, 1, 3])
        with col1:
            if st.button("💾 Lưu Extract Code", key="save_extract", use_container_width=True):
                extract_code = result['code']
                # Lưu luôn vào file
                if save_extract_sections_for_site(site, extract_code):
                    st.success("✅ Đã lưu extract sections thành công!")
                    st.rerun()
                else:
                    st.error("❌ Lỗi khi lưu extract sections!")
        with col2:
            if st.button("🔄 Reset Extract Code", key="reset_extract", use_container_width=True):
                current_extract_code = load_extract_sections_for_site(site)
                st.rerun()
    else:
        st.info("⚠️ Vui lòng nhập System Prompt để tự động tạo Extract Sections")
    
    # Preview Section
    st.write("### 👁️ Preview")
    
    with st.container():
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**System Prompt Preview**")
            if system_prompt:
                preview_text = system_prompt[:500] + "..." if len(system_prompt) > 500 else system_prompt
                st.text_area("Preview", value=preview_text, height=150, disabled=True, key="system_preview", label_visibility="collapsed")
                st.caption(f"📝 {len(system_prompt)} ký tự")
            else:
                st.info("Chưa có system prompt")
        
        with col2:
            st.write("**Human Prompt Preview**")
            if human_prompt:
                preview_text = human_prompt[:500] + "..." if len(human_prompt) > 500 else human_prompt
                st.text_area("Preview", value=preview_text, height=150, disabled=True, key="human_preview", label_visibility="collapsed")
                st.caption(f"📝 {len(human_prompt)} ký tự")
            else:
                st.info("Chưa có human prompt")
    
    # # File Information
    # st.write("### 📁 Thông tin Files")
    
    # prompt_paths = get_prompt_paths(site)
    # extract_path = get_extract_sections_path(site)
    
    # col1, col2, col3 = st.columns(3)
    
    # with col1:
    #     st.write("**System Prompt**")
    #     st.code(f"📄 {prompt_paths['system_prompt']}")
    #     if os.path.exists(prompt_paths["system_prompt"]):
    #         file_size = os.path.getsize(prompt_paths["system_prompt"])
    #         st.write(f"📊 Kích thước: {file_size} bytes")
    #     else:
    #         st.warning("⚠️ File không tồn tại")
    
    # with col2:
    #     st.write("**Human Prompt**")
    #     st.code(f"📄 {prompt_paths['human_prompt']}")
    #     if os.path.exists(prompt_paths["human_prompt"]):
    #         file_size = os.path.getsize(prompt_paths["human_prompt"])
    #         st.write(f"📊 Kích thước: {file_size} bytes")
    #     else:
    #         st.warning("⚠️ File không tồn tại")
    
    # with col3:
    #     st.write("**Extract Sections**")
    #     st.code(f"🐍 {extract_path}")
    #     if os.path.exists(extract_path):
    #         file_size = os.path.getsize(extract_path)
    #         st.write(f"📊 Kích thước: {file_size} bytes")
    #     else:
    #         st.warning("⚠️ File không tồn tại")
    
    # # Instructions
    # st.write("### 📋 Hướng dẫn")
    # st.markdown("""
    # **Quản lý Prompts:**
    # - System Prompt: Định nghĩa vai trò và tiêu chí đánh giá cho LLM
    # - Human Prompt: Template cho input được gửi đến LLM
    # - Sử dụng `{question}`, `{true_answer}`, `{agent_answer}` làm placeholders
    
    # **Quản lý Extract Sections:**
    # - Code Python để trích xuất kết quả từ response của LLM
    # - Phải có function `extract_section(text)` trả về dict với keys: `scores` và `comments`
    # - `scores` phải chứa các metrics phù hợp với site (THFC có access_control, HR có tone)
    # - **🤖 Tự động tạo**: Nhấn "Tự động tạo từ Prompt" để AI phân tích system prompt và tạo code phù hợp
    
    # **Lưu ý:**
    # - Sau khi lưu, các thay đổi sẽ có hiệu lực ngay lập tức
    # - Backup files trước khi chỉnh sửa để tránh mất dữ liệu
    # - Kiểm tra syntax Python trước khi lưu extract sections
    # - Tính năng tự động tạo sẽ phân tích các tiêu chí trong system prompt và tạo code tương ứng
    # """)

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

### Quản lý Prompts
1. Chỉnh sửa system prompt và human prompt.
2. Cập nhật extract sections code.
3. Lưu để áp dụng thay đổi.
""")
