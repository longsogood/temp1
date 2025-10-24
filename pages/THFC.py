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
from utils import extract_section
import warnings
import pytz
from schedule_manager import get_schedule_manager
warnings.filterwarnings("ignore")

## Cấu hình streamlit
st.set_page_config(
    layout="wide",
    page_title="THFC",
    page_icon="🤖"
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
SITE = "THFC"

# Config cứng cho số luồng xử lý đồng thời
MAX_WORKERS = 5

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
if 'scheduled_jobs' not in st.session_state:
    st.session_state.scheduled_jobs = []

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

def get_site_paths(site):
    site_dir = os.path.join(RESULTS_DIR, site)
    os.makedirs(site_dir, exist_ok=True)
    return {
        "failed_tests": os.path.join(site_dir, "failed_tests.pkl"),
        "test_history": os.path.join(site_dir, "test_history.pkl"),
        "test_changes": os.path.join(site_dir, "test_changes.pkl")
    }

def save_test_results(results, test_name, site):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
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
    if 'test_history' not in st.session_state:
        st.session_state.test_history = {}
    if site not in st.session_state.test_history:
        st.session_state.test_history[site] = []
    st.session_state.test_history[site].append(history_entry)

    try:
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
        levels = df.iloc[:, 2].tolist() if len(df.columns) > 2 else ["L1"] * len(questions)
        departments = df.iloc[:, 3].tolist() if len(df.columns) > 3 else ["Phòng kinh doanh (Sales)"] * len(questions)
        logger.info(f"Số câu hỏi đọc được: {len(questions)} | Số đáp án: {len(true_answers)}")

        results, failed_questions = process_questions_batch(
            questions, 
            true_answers, 
            levels,
            departments,
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

# --- Helper Functions ---
def get_criteria_from_prompt(system_prompt):
    """Lấy danh sách criteria từ system prompt để sử dụng cho fail criterion selection"""
    import re
    
    if not system_prompt:
        return ["accuracy", "relevance", "completeness", "clarity", "access_control", "average"]
    
    criteria = []
    lines = system_prompt.split('\n')
    
    for line in lines:
        line = line.strip()
        # Tìm pattern ### số. Tên tiêu chí (Mô tả)
        match = re.match(r'^###\s*\d+\.\s*([^(]+?)\s*\(([^)]+)\)\s*$', line, re.IGNORECASE)
        if match:
            criterion = match.group(1).strip()
            if criterion and len(criterion) < 50:
                criteria.append(criterion)
        else:
            # Thử pattern không có mô tả
            match = re.match(r'^###\s*\d+\.\s*([^(]+?)\s*$', line, re.IGNORECASE)
            if match:
                criterion = match.group(1).strip()
                if criterion and len(criterion) < 50:
                    criteria.append(criterion)
    
    # Nếu không tìm thấy, thử tìm với format khác (dấu -)
    if not criteria:
        for line in lines:
            line = line.strip()
            # Tìm pattern - Tên tiêu chí (Mô tả)
            match = re.match(r'^-\s*([^(]+?)\s*\(([^)]+)\)\s*$', line, re.IGNORECASE)
            if match:
                criterion = match.group(1).strip()
                if criterion and len(criterion) < 50:
                    criteria.append(criterion)
            else:
                # Thử pattern không có mô tả
                match = re.match(r'^-\s*([^(]+?)\s*$', line, re.IGNORECASE)
                if match:
                    criterion = match.group(1).strip()
                    if criterion and len(criterion) < 50:
                        criteria.append(criterion)
    
    # Chuẩn hóa tên criteria thành lowercase và thay khoảng trắng bằng _
    normalized_criteria = []
    for criterion in criteria:
        # Loại bỏ số thứ tự và ký tự đặc biệt
        clean_name = re.sub(r'^\d+\.?\s*', '', criterion)
        clean_name = re.sub(r'[^\w\s]', '', clean_name)
        clean_name = clean_name.strip().lower().replace(' ', '_')
        normalized_criteria.append(clean_name)
    
    # Loại bỏ duplicate và giữ thứ tự
    seen = set()
    unique_criteria = []
    for criterion in normalized_criteria:
        if criterion not in seen:
            seen.add(criterion)
            unique_criteria.append(criterion)
    
    # Thêm "average" nếu chưa có
    if "average" not in unique_criteria:
        unique_criteria.append("average")
    
    # Fallback nếu không tìm thấy criteria nào
    if not unique_criteria:
        unique_criteria = ["accuracy", "relevance", "completeness", "clarity", "access_control", "average"]
    
    return unique_criteria

# --- Prompt Management Functions ---
def get_prompt_paths(site):
    """Get prompt file paths for a specific site"""
    prompt_dir = os.path.join("prompts", site)
    return {
        "system_prompt": os.path.join(prompt_dir, "system_prompt.txt"),
        "human_prompt": os.path.join(prompt_dir, "human_prompt.txt")
    }

def get_original_prompt_paths():
    """Get original prompt file paths"""
    return {
        "system_prompt": os.path.join("original_prompts", "system_prompt.txt"),
        "human_prompt": os.path.join("original_prompts", "human_prompt.txt")
    }

def copy_original_prompts_to_site(site):
    """Copy prompts from original_prompts to site folder"""
    try:
        original_prompts = load_original_prompts()
        
        if original_prompts["system_prompt"] or original_prompts["human_prompt"]:
            # Save to site folder
            save_prompts_for_site(site, original_prompts["system_prompt"], original_prompts["human_prompt"])
            logger.info(f"Đã copy original prompts sang site {site}")
            return True
        else:
            logger.warning("Original prompts rỗng, không thể copy")
            return False
    except Exception as e:
        logger.error(f"Lỗi khi copy original prompts sang site {site}: {str(e)}")
        return False

def load_original_prompts():
    """Load prompts from original_prompts folder"""
    original_paths = get_original_prompt_paths()
    prompts = {}
    
    try:
        if os.path.exists(original_paths["system_prompt"]):
            with open(original_paths["system_prompt"], "r", encoding="utf-8") as f:
                prompts["system_prompt"] = f.read()
        else:
            prompts["system_prompt"] = ""
            logger.warning("Original system_prompt.txt không tồn tại")
            
        if os.path.exists(original_paths["human_prompt"]):
            with open(original_paths["human_prompt"], "r", encoding="utf-8") as f:
                prompts["human_prompt"] = f.read()
        else:
            prompts["human_prompt"] = ""
            logger.warning("Original human_prompt.txt không tồn tại")
            
    except Exception as e:
        logger.error(f"Lỗi khi đọc original prompts: {str(e)}")
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

def load_prompts_for_site(site):
    """Load prompts for a specific site, copy from original if not exists"""
    prompt_paths = get_prompt_paths(site)
    prompts = {}
    
    # Check if prompts exist for this site
    site_prompts_exist = os.path.exists(prompt_paths["system_prompt"]) and os.path.exists(prompt_paths["human_prompt"])
    
    # If not exist, copy from original_prompts
    if not site_prompts_exist:
        logger.info(f"Prompts cho site {site} chưa tồn tại, đang copy từ original_prompts")
        copy_original_prompts_to_site(site)
    
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

# --- Configuration Management Functions ---
def get_config_file_path(site):
    """Get configuration file path for a specific site"""
    config_dir = "config"
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, f"{site}_config.pkl")

def save_config_to_file(site, config):
    """Save configuration to file"""
    try:
        config_file = get_config_file_path(site)
        with open(config_file, "wb") as f:
            pickle.dump(config, f)
        logger.info(f"Đã lưu cấu hình cho site {site}")
        return True
    except Exception as e:
        logger.error(f"Lỗi khi lưu cấu hình cho site {site}: {str(e)}")
        return False

def load_config_from_file(site):
    """Load configuration from file"""
    try:
        config_file = get_config_file_path(site)
        if os.path.exists(config_file):
            with open(config_file, "rb") as f:
                config = pickle.load(f)
            logger.info(f"Đã tải cấu hình cho site {site}")
            return config
        else:
            logger.info(f"Chưa có file cấu hình cho site {site}")
            return None
    except Exception as e:
        logger.error(f"Lỗi khi tải cấu hình cho site {site}: {str(e)}")
        return None

def get_default_config():
    """Get default configuration"""
    return {
        "api_url": "https://site1.com",
        "evaluate_api_url": "https://site2.com",
        "fail_criterion": "accuracy",
        "fail_threshold": 8.0,
        "add_chat_history_global": False
    }

# Giao diện Streamlit
st.title("🤖 Agent Testing")

# --- Load configuration from file ---
def load_site_config():
    """Load configuration for current site"""
    site = get_current_site()
    config = load_config_from_file(site)
    
    if config:
        # Load từ file
        st.session_state.api_url = config.get("api_url", "https://site1.com")
        st.session_state.evaluate_api_url = config.get("evaluate_api_url", "https://site2.com")
        st.session_state.fail_criterion = config.get("fail_criterion", "accuracy")
        st.session_state.fail_threshold = config.get("fail_threshold", 8.0)
        st.session_state.add_chat_history_global = config.get("add_chat_history_global", False)
        logger.info(f"Đã load cấu hình từ file cho site {site}")
    else:
        # Sử dụng cấu hình mặc định
        default_config = get_default_config()
        st.session_state.api_url = default_config["api_url"]
        st.session_state.evaluate_api_url = default_config["evaluate_api_url"]
        st.session_state.fail_criterion = default_config["fail_criterion"]
        st.session_state.fail_threshold = default_config["fail_threshold"]
        st.session_state.add_chat_history_global = default_config["add_chat_history_global"]
        logger.info(f"Sử dụng cấu hình mặc định cho site {site}")

# Load cấu hình khi khởi động
if 'config_loaded' not in st.session_state:
    load_site_config()
    st.session_state.config_loaded = True

# --- Cấu hình và các biến toàn cục ---
with st.expander("⚙️ Cấu hình API và các tham số", expanded=False):
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Cấu hình API**")
        API_URL = st.text_input("API URL", value=st.session_state.get("api_url", "https://site1.com"), key="api_url_input")
        EVALUATE_API_URL = st.text_input("Evaluate API URL", value=st.session_state.get("evaluate_api_url", "https://site2.com"), key="evaluate_api_url_input")
    
    with col2:
        st.write("**Cấu hình Test**")
        add_chat_history_global = st.checkbox("Thêm chat history (giả lập đã cung cấp thông tin)", value=st.session_state.get("add_chat_history_global", False), key="add_chat_history_checkbox")
    
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write("**Tiêu chí đánh giá fail**")
        
        # Lấy criteria động từ system prompt
        current_system_prompt = st.session_state.get("current_system_prompt", "")
        if not current_system_prompt:
            # Load system prompt hiện tại nếu chưa có
            try:
                site = get_current_site()
                prompts = load_prompts_for_site(site)
                current_system_prompt = prompts.get("system_prompt", "")
                st.session_state.current_system_prompt = current_system_prompt
            except:
                current_system_prompt = ""
        
        # Lấy danh sách criteria từ prompt
        criterion_options = get_criteria_from_prompt(current_system_prompt)
        
        # Lấy tiêu chí hiện tại từ session state
        current_criterion = st.session_state.get("fail_criterion", criterion_options[0] if criterion_options else "accuracy")
        
        # Tìm index của tiêu chí hiện tại
        if current_criterion in criterion_options:
            criterion_index = criterion_options.index(current_criterion)
        else:
            criterion_index = 0
            # Cập nhật session state nếu tiêu chí hiện tại không có trong danh sách mới
            st.session_state.fail_criterion = criterion_options[0] if criterion_options else "accuracy"
        
        col1_1, col1_2 = st.columns([3, 1])
        with col1_1:
            fail_criterion = st.selectbox(
                "Chọn tiêu chí",
                criterion_options,
                index=criterion_index,
                help=f"Tiêu chí được sử dụng để xác định test case fail (tự động từ system prompt: {len(criterion_options)} tiêu chí)",
                key="fail_criterion_select"
            )
        with col1_2:
            if st.button("🔄", help="Refresh criteria từ system prompt hiện tại", key="refresh_criteria"):
                try:
                    site = get_current_site()
                    prompts = load_prompts_for_site(site)
                    new_system_prompt = prompts.get("system_prompt", "")
                    st.session_state.current_system_prompt = new_system_prompt
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi khi refresh criteria: {str(e)}")
    
    with col2:
        st.write("**Ngưỡng fail**")
        fail_threshold = st.number_input(
            "Ngưỡng điểm (< ngưỡng = fail)",
            min_value=0.0,
            max_value=10.0,
            value=st.session_state.get("fail_threshold", 8.0),
            step=0.5,
            help="Test case có điểm thấp hơn ngưỡng này sẽ được đánh dấu fail",
            key="fail_threshold_input"
        )
    
    with col3:
        st.write("**Tóm tắt cấu hình**")
        st.info(f"Fail nếu **{fail_criterion}** < {fail_threshold}")
        
        # Nút lưu cấu hình
        st.write("")  # Spacing
        if st.button("💾 Lưu cấu hình", type="primary", use_container_width=True, help="Lưu và áp dụng cấu hình cho tất cả test"):
            # Cập nhật session state
            st.session_state.api_url = API_URL
            st.session_state.evaluate_api_url = EVALUATE_API_URL
            st.session_state.fail_criterion = fail_criterion
            st.session_state.fail_threshold = fail_threshold
            st.session_state.add_chat_history_global = add_chat_history_global
            
            # Lưu vào file
            site = get_current_site()
            config = {
                "api_url": API_URL,
                "evaluate_api_url": EVALUATE_API_URL,
                "fail_criterion": fail_criterion,
                "fail_threshold": fail_threshold,
                "add_chat_history_global": add_chat_history_global
            }
            
            if save_config_to_file(site, config):
                st.success("✅ Đã lưu cấu hình vào file! Áp dụng cho tất cả test (đơn lẻ, hàng loạt, lập lịch)")
            else:
                st.error("❌ Lỗi khi lưu cấu hình vào file!")
            time.sleep(0.5)  # Delay để user thấy thông báo
            st.rerun()
    
    # Configuration đã được load từ file ở trên

# --- Prompt Management Functions ---
def get_prompt_paths(site):
    """Get prompt file paths for a specific site"""
    prompt_dir = os.path.join("prompts", site)
    return {
        "system_prompt": os.path.join(prompt_dir, "system_prompt.txt"),
        "human_prompt": os.path.join(prompt_dir, "human_prompt.txt")
    }

def get_original_prompt_paths():
    """Get original prompt file paths"""
    return {
        "system_prompt": os.path.join("original_prompts", "system_prompt.txt"),
        "human_prompt": os.path.join("original_prompts", "human_prompt.txt")
    }

def get_backup_prompt_paths(site):
    """Get backup prompt file paths for a specific site"""
    backup_dir = os.path.join("backup_prompts", site)
    return {
        "system_prompt": os.path.join(backup_dir, "system_prompt.txt"),
        "human_prompt": os.path.join(backup_dir, "human_prompt.txt")
    }

def get_backup_extract_sections_path(site):
    """Get backup extract_sections.py file path for a specific site"""
    backup_dir = os.path.join("backup_prompts", site)
    return os.path.join(backup_dir, "extract_sections.py")

def get_extract_sections_path(site):
    """Get extract_sections.py file path for a specific site"""
    utils_dir = os.path.join("utils", site)
    return os.path.join(utils_dir, "extract_sections.py")

def load_original_prompts():
    """Load prompts from original_prompts folder"""
    original_paths = get_original_prompt_paths()
    prompts = {}
    
    try:
        if os.path.exists(original_paths["system_prompt"]):
            with open(original_paths["system_prompt"], "r", encoding="utf-8") as f:
                prompts["system_prompt"] = f.read()
        else:
            prompts["system_prompt"] = ""
            logger.warning("Original system_prompt.txt không tồn tại")
            
        if os.path.exists(original_paths["human_prompt"]):
            with open(original_paths["human_prompt"], "r", encoding="utf-8") as f:
                prompts["human_prompt"] = f.read()
        else:
            prompts["human_prompt"] = ""
            logger.warning("Original human_prompt.txt không tồn tại")
            
    except Exception as e:
        logger.error(f"Lỗi khi đọc original prompts: {str(e)}")
        prompts = {"system_prompt": "", "human_prompt": ""}
    
    return prompts

def backup_prompts_for_site(site):
    """Backup current prompts to backup_prompts folder"""
    try:
        # Load current prompts
        current_prompts = load_prompts_for_site(site)
        
        if not (current_prompts["system_prompt"] or current_prompts["human_prompt"]):
            logger.warning(f"Prompts hiện tại của site {site} rỗng, không thể backup")
            return False
        
        # Create backup directory
        backup_paths = get_backup_prompt_paths(site)
        os.makedirs(os.path.dirname(backup_paths["system_prompt"]), exist_ok=True)
        
        # Save to backup folder
        with open(backup_paths["system_prompt"], "w", encoding="utf-8") as f:
            f.write(current_prompts["system_prompt"])
        with open(backup_paths["human_prompt"], "w", encoding="utf-8") as f:
            f.write(current_prompts["human_prompt"])
        
        logger.info(f"Đã backup prompts cho site {site}")
        return True
        
    except Exception as e:
        logger.error(f"Lỗi khi backup prompts cho site {site}: {str(e)}")
        return False

def backup_extract_sections_for_site(site):
    """Backup current extract_sections to backup_prompts folder"""
    try:
        # Load current extract sections
        current_code = load_extract_sections_for_site(site)
        
        if not current_code:
            logger.warning(f"Extract sections hiện tại của site {site} rỗng, không thể backup")
            return False
        
        # Create backup directory
        backup_path = get_backup_extract_sections_path(site)
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        
        # Save to backup folder
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(current_code)
        
        logger.info(f"Đã backup extract_sections cho site {site}")
        return True
        
    except Exception as e:
        logger.error(f"Lỗi khi backup extract_sections cho site {site}: {str(e)}")
        return False

def restore_prompts_from_backup(site):
    """Restore prompts from backup, fallback to original if backup not exists"""
    try:
        backup_paths = get_backup_prompt_paths(site)
        
        # Check if backup exists
        if os.path.exists(backup_paths["system_prompt"]) and os.path.exists(backup_paths["human_prompt"]):
            # Load from backup
            with open(backup_paths["system_prompt"], "r", encoding="utf-8") as f:
                system_prompt = f.read()
            with open(backup_paths["human_prompt"], "r", encoding="utf-8") as f:
                human_prompt = f.read()
            
            # Save to site folder
            save_prompts_for_site(site, system_prompt, human_prompt)
            logger.info(f"Đã restore prompts từ backup cho site {site}")
            return "backup"
        else:
            # Fallback to original
            original_prompts = load_original_prompts()
            if original_prompts["system_prompt"] or original_prompts["human_prompt"]:
                save_prompts_for_site(site, original_prompts["system_prompt"], original_prompts["human_prompt"])
                logger.info(f"Không tìm thấy backup, đã restore prompts từ original cho site {site}")
                return "original"
            else:
                logger.warning("Cả backup và original prompts đều rỗng")
                return False
                
    except Exception as e:
        logger.error(f"Lỗi khi restore prompts cho site {site}: {str(e)}")
        return False

def restore_extract_sections_from_backup(site):
    """Restore extract_sections from backup, fallback to original if backup not exists"""
    try:
        backup_path = get_backup_extract_sections_path(site)
        
        # Check if backup exists
        if os.path.exists(backup_path):
            # Load from backup
            with open(backup_path, "r", encoding="utf-8") as f:
                extract_code = f.read()
            
            # Save to site folder
            save_extract_sections_for_site(site, extract_code)
            logger.info(f"Đã restore extract_sections từ backup cho site {site}")
            return "backup"
        else:
            # Fallback to original
            original_code = load_original_extract_sections()
            if original_code:
                save_extract_sections_for_site(site, original_code)
                logger.info(f"Không tìm thấy backup, đã restore extract_sections từ original cho site {site}")
                return "original"
            else:
                logger.warning("Cả backup và original extract_sections đều rỗng")
                return False
                
    except Exception as e:
        logger.error(f"Lỗi khi restore extract_sections cho site {site}: {str(e)}")
        return False

def copy_original_prompts_to_site(site):
    """Copy prompts from original_prompts to site folder"""
    try:
        original_prompts = load_original_prompts()
        
        if original_prompts["system_prompt"] or original_prompts["human_prompt"]:
            # Save to site folder
            save_prompts_for_site(site, original_prompts["system_prompt"], original_prompts["human_prompt"])
            logger.info(f"Đã copy original prompts sang site {site}")
            return True
        else:
            logger.warning("Original prompts rỗng, không thể copy")
            return False
    except Exception as e:
        logger.error(f"Lỗi khi copy original prompts sang site {site}: {str(e)}")
        return False

def load_prompts_for_site(site):
    """Load prompts for a specific site, copy from original if not exists"""
    prompt_paths = get_prompt_paths(site)
    prompts = {}
    
    # Check if prompts exist for this site
    site_prompts_exist = os.path.exists(prompt_paths["system_prompt"]) and os.path.exists(prompt_paths["human_prompt"])
    
    # If not exist, copy from original_prompts
    if not site_prompts_exist:
        logger.info(f"Prompts cho site {site} chưa tồn tại, đang copy từ original_prompts")
        copy_original_prompts_to_site(site)
    
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

def get_original_extract_sections_path():
    """Get original extract_sections.py file path"""
    return os.path.join("original_prompts", "extract_sections.py")

def load_original_extract_sections():
    """Load extract_sections from original_prompts folder"""
    original_path = get_original_extract_sections_path()
    
    try:
        if os.path.exists(original_path):
            with open(original_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            logger.warning("Original extract_sections.py không tồn tại")
            return ""
    except Exception as e:
        logger.error(f"Lỗi khi đọc original extract_sections: {str(e)}")
        return ""

def copy_original_extract_sections_to_site(site):
    """Copy extract_sections from original_prompts to site folder"""
    try:
        original_code = load_original_extract_sections()
        
        if original_code:
            # Save to site folder
            save_extract_sections_for_site(site, original_code)
            logger.info(f"Đã copy original extract_sections sang site {site}")
            return True
        else:
            logger.warning("Original extract_sections rỗng, không thể copy")
            return False
    except Exception as e:
        logger.error(f"Lỗi khi copy original extract_sections sang site {site}: {str(e)}")
        return False

def load_extract_sections_for_site(site):
    """Load extract_sections.py for a specific site, copy from original if not exists"""
    extract_path = get_extract_sections_path(site)
    
    # If not exist, copy from original_prompts
    if not os.path.exists(extract_path):
        logger.info(f"Extract sections cho site {site} chưa tồn tại, đang copy từ original_prompts")
        copy_original_extract_sections_to_site(site)
    
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

# --- Test Cases Management Functions ---
def get_test_cases_dir(site):
    """Get test cases directory for a specific site"""
    test_cases_dir = os.path.join("test_cases", site)
    os.makedirs(test_cases_dir, exist_ok=True)
    return test_cases_dir

def get_test_cases_file_path(site):
    """Get the single test cases file path for a site"""
    test_cases_dir = get_test_cases_dir(site)
    return os.path.join(test_cases_dir, f"{site}_test_cases.xlsx")

def save_test_cases(site, test_cases_df):
    """Save test cases to file (overwrites existing)"""
    try:
        filepath = get_test_cases_file_path(site)
        test_cases_df.to_excel(filepath, index=False)
        logger.info(f"Đã lưu test cases cho site {site}")
        return filepath
    except Exception as e:
        logger.error(f"Lỗi khi lưu test cases cho site {site}: {str(e)}")
        return None

def load_test_cases(site):
    """Load test cases for a specific site"""
    try:
        filepath = get_test_cases_file_path(site)
        
        if os.path.exists(filepath):
            df = pd.read_excel(filepath)
            return df
        else:
            return None
    except Exception as e:
        logger.error(f"Lỗi khi load test cases cho site {site}: {str(e)}")
        return None

def test_cases_exists(site):
    """Check if test cases exist for a site"""
    filepath = get_test_cases_file_path(site)
    return os.path.exists(filepath)

def delete_test_cases(site):
    """Delete test cases file for a site"""
    try:
        filepath = get_test_cases_file_path(site)
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Đã xóa test cases cho site {site}")
            return True
        return False
    except Exception as e:
        logger.error(f"Lỗi khi xóa test cases cho site {site}: {str(e)}")
        return False

def delete_site_completely(site):
    """Delete all data related to a site"""
    import shutil
    
    try:
        deleted_items = []
        
        # 1. Delete prompts folder
        prompts_dir = os.path.join("prompts", site)
        if os.path.exists(prompts_dir):
            shutil.rmtree(prompts_dir)
            deleted_items.append(f"prompts/{site}")
        
        # 2. Delete backup prompts folder
        backup_dir = os.path.join("backup_prompts", site)
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)
            deleted_items.append(f"backup_prompts/{site}")
        
        # 3. Delete utils folder (extract_sections)
        utils_dir = os.path.join("utils", site)
        if os.path.exists(utils_dir):
            shutil.rmtree(utils_dir)
            deleted_items.append(f"utils/{site}")
        
        # 4. Delete test_cases folder
        test_cases_dir = get_test_cases_dir(site)
        if os.path.exists(test_cases_dir):
            shutil.rmtree(test_cases_dir)
            deleted_items.append(f"test_cases/{site}")
        
        # 5. Delete test_results folder
        test_results_dir = os.path.join("test_results", site)
        if os.path.exists(test_results_dir):
            shutil.rmtree(test_results_dir)
            deleted_items.append(f"test_results/{site}")
        
        # 6. Delete scheduled_tests folder
        scheduled_tests_dir = os.path.join("scheduled_tests", site)
        if os.path.exists(scheduled_tests_dir):
            shutil.rmtree(scheduled_tests_dir)
            deleted_items.append(f"scheduled_tests/{site}")
        
        # 7. Delete config file
        config_file = get_config_file_path(site)
        if os.path.exists(config_file):
            os.remove(config_file)
            deleted_items.append(f"config/{site}_config.pkl")
        
        # 8. Remove scheduled job
        remove_scheduled_job_for_site(site)
        
        # 9. Clear session state
        if site in st.session_state.get('test_history', {}):
            del st.session_state.test_history[site]
        if site in st.session_state.get('failed_tests', {}):
            del st.session_state.failed_tests[site]
        if site in st.session_state.get('schedule_enabled', {}):
            del st.session_state.schedule_enabled[site]
        if site in st.session_state.get('schedule_thread', {}):
            del st.session_state.schedule_thread[site]
        
        logger.info(f"Đã xóa site '{site}' hoàn toàn. Các mục đã xóa: {', '.join(deleted_items)}")
        return True, deleted_items
        
    except Exception as e:
        logger.error(f"Lỗi khi xóa site '{site}': {str(e)}")
        return False, []

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
        '    print(f"JSON data:\\n{json_data}")',
        '    results = {}',
        '    if json_data:',
        '        results["scores"] = {}',
    ]
    
    # Thêm các dòng extract cho từng criteria
    for criterion in unique_criteria:
        code_lines.append(f'        {criterion} = json_data["{criterion}"]')
        code_lines.append(f'        results["scores"]["{criterion}"] = {criterion}')
    
    # Tính average
    criteria_list = ' + '.join(unique_criteria)
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
        'code': '\n'.join(code_lines),
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
        except Exception as e:
            st.error(f"Lỗi khi cập nhật tiến trình: {str(e)}")
            break


def process_single_question(question, true_answer, level, department, index, total_questions, add_chat_history=False, custom_history=None, site=None, api_url=None, evaluate_api_url=None):
    try:
        chat_id = str(uuid4())
        site_payload = {
            "chat_id": chat_id,
            "question": question,
            "site": site or get_current_site(),
            "overrideConfig":
                {
                    "stateMemory": [
                        {
                            "Key": "level",
                            "Operation": "Replace",
                            "Default Value": level
                        },
                        {
                            "Key": "department",
                            "Operation": "Replace",
                            "Default Value": department
                        }
                    ]
                }
            }
        if add_chat_history and custom_history:
            site_payload["chat_history"] = custom_history

        request_api_url = api_url or API_URL
        request_evaluate_api_url = evaluate_api_url or EVALUATE_API_URL

        response = requests.post(request_api_url, json=site_payload)
        if not response.ok:
            return f"Lỗi API: {response.text}"
        
        site_response = response.json()["text"]
        
        # Load human prompt for current site
        site_prompts = load_prompts_for_site(site or get_current_site())
        human_prompt_template = site_prompts["human_prompt"]
        
        # Format human prompt with actual values
        evaluate_human_prompt = human_prompt_template.format(
            question=question,
            level=level,
            department=department,
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
            "level": level,
            "department": department,
            "site_response": site_response,
            "evaluate_result": evaluate_result,
        }
    except requests.exceptions.RequestException as e:
        return f"Lỗi API: {str(e)}"
    except Exception as e:
        return f"Lỗi khi xử lý câu hỏi {index + 1}: {str(e)}"

def process_questions_batch(questions, true_answers, levels, departments, add_chat_history=False, custom_history=None, test_name=None, is_scheduled=False, site=None, api_url=None, evaluate_api_url=None, progress_bar=None, status_text=None, current_question_text=None):
    results = []
    failed_questions = []
    
    # Tạo progress container với styling đẹp hơn (chỉ khi không có progress bar từ bên ngoài)
    if not is_scheduled and progress_bar is None:
        progress_container = st.container()
        with progress_container:
            st.markdown("### ⏳ Tiến trình xử lý")
            progress_bar = st.progress(0)
            status_text = st.empty()
            current_question_text = st.empty()
    elif is_scheduled:
        progress_container = None
        progress_bar = None
        status_text = None
        current_question_text = None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_single_question, q, ta, l, d, i, len(questions), add_chat_history, custom_history, site, api_url, evaluate_api_url): (q, ta, l, d) for i, (q, ta, l, d) in enumerate(zip(questions, true_answers, levels, departments))}
        
        completed_count = 0
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            question, true_answer, level, department = futures[future]
            completed_count += 1
            
            # Cập nhật progress bar và thông báo
            if not is_scheduled and progress_bar and status_text and current_question_text:
                progress = completed_count / len(questions)
                progress_bar.progress(progress)
                status_text.text(f"📊 Đã xử lý: {completed_count}/{len(questions)} câu hỏi ({progress*100:.1f}%)")
                
                # Hiển thị câu hỏi đang được xử lý (rút gọn nếu quá dài)
                display_question = question[:100] + "..." if len(question) > 100 else question
                current_question_text.text(f"🔄 Đang xử lý: {display_question}")
            
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
                                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
                            "level": level, "department": department,
                            "site_response": result.get("site_response", "[Lỗi khi xử lý]"),
                            "evaluate_result": {"scores": {}, "comments": "Lỗi: evaluate_result không hợp lệ"},
                            "failed_details": {"timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "test_name": test_name, "reason": "Lỗi evaluate_result", "error_message": "evaluate_result is None or invalid"}
                        }
                        results.append(error_result)
                        failed_questions.append((question, "Lỗi evaluate_result", "evaluate_result is None or invalid"))
                else:
                    error_result = {
                        "chat_id": str(uuid4()), "question": question, "true_answer": true_answer,
                        "level": level, "department": department,
                        "site_response": "[Lỗi khi xử lý]",
                        "evaluate_result": {"scores": {}, "comments": f"Lỗi: {result}"},
                        "failed_details": {"timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "test_name": test_name, "reason": "Lỗi xử lý API", "error_message": str(result)}
                    }
                    results.append(error_result)
                    failed_questions.append((question, "Lỗi xử lý API", result))
            except Exception as e:
                error_message = f"Lỗi: {str(e)}"
                error_result = {
                    "chat_id": str(uuid4()), "question": question, "true_answer": true_answer,
                    "level": level, "department": department,
                    "site_response": "[Lỗi khi xử lý]",
                    "evaluate_result": {"scores": {}, "comments": error_message},
                    "failed_details": {"timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "test_name": test_name, "reason": "Exception", "error_message": str(e)}
                }
                results.append(error_result)
                failed_questions.append((question, "Exception", str(e)))
    
    # Hiển thị thông báo hoàn thành
    if not is_scheduled and status_text and current_question_text:
        status_text.text(f"✅ Hoàn thành: {len(questions)} câu hỏi đã được xử lý")
        current_question_text.text("🎉 Tất cả câu hỏi đã được xử lý thành công!")

    if failed_questions and (is_scheduled or test_name):
        failed_results = [r for r in results if "failed_details" in r]
        if failed_results:
            save_failed_test_details(failed_results, site)
    
    return results, failed_questions

# Tải lịch sử test, test case thất bại và lịch sử thay đổi

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
    if schedule_manager:
        return schedule_manager.get_schedule_config(site)
    return None

def remove_scheduled_job_for_site(site):
    """Remove scheduled job for a specific site"""
    st.session_state.scheduled_jobs = [job for job in st.session_state.scheduled_jobs if job.get('site') != site]
    save_scheduled_jobs()

# Initialize Persistent Schedule Manager (Global, thread-safe)
# Chỉ khởi tạo một lần, schedule manager sẽ tự load từ JSON
try:
    schedule_manager = get_schedule_manager()
    logger.info("Schedule Manager initialized successfully")
except Exception as e:
    logger.error(f"Error initializing Schedule Manager: {e}")
    schedule_manager = None

# Tạo các tab
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Test hàng loạt", "Lập lịch test", "Quản lý test", "Quản lý Test Cases", "Quản lý Prompts"])

with tab3:
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
    else:
        # Empty state cho Dashboard
        st.markdown("""
        <div style="text-align: center; padding: 30px; background: #f8f9fa; border-radius: 10px; border: 2px dashed #ddd;">
            <h3 style="color: #999; margin-bottom: 10px;">📊 Dashboard sẽ xuất hiện ở đây</h3>
            <p style="color: #666; font-size: 14px;">Sau khi bạn chạy test, metrics và biểu đồ thống kê sẽ được hiển thị tại đây</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.write("---")  # Divider
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
        # Empty state với hướng dẫn chi tiết
        st.markdown("""
        <div style="text-align: center; padding: 40px 20px; background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%); border-radius: 10px; margin: 20px 0;">
            <h2 style="color: #667eea; margin-bottom: 20px;">📊 Chưa có lịch sử test</h2>
            <p style="font-size: 16px; color: #666; margin-bottom: 30px;">
                Để xem dashboard và lịch sử test, bạn cần chạy test trước.
            </p>
            <div style="text-align: left; max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <h4 style="color: #333; margin-bottom: 15px;">🚀 Hướng dẫn nhanh:</h4>
                <ol style="color: #555; line-height: 1.8;">
                    <li><strong>Vào Tab "Test hàng loạt"</strong> ở phía trên</li>
                    <li>Upload file Excel chứa câu hỏi và câu trả lời chuẩn</li>
                    <li>Chọn các câu hỏi muốn test</li>
                    <li>Nhấn nút <strong>"▶️ Chạy test"</strong></li>
                    <li>Quay lại tab này để xem kết quả và thống kê</li>
                </ol>
            </div>
            <p style="margin-top: 30px; color: #888; font-size: 14px;">
                💡 Tip: Bạn cũng có thể lập lịch test tự động ở Tab "Lập lịch test"
            </p>
        </div>
        """, unsafe_allow_html=True)
        
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
    #             st.write(f"- **Level:** {selected_failed_test.get('level', 'N/A')}")
    #             st.write(f"- **Department:** {selected_failed_test.get('department', 'N/A')}")
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

with tab4:
    st.subheader("📋 Quản lý Test Cases")
    
    site = get_current_site()
    st.write(f"**Site hiện tại:** {site}")
    
    # Hiển thị thông báo nếu có
    if 'test_cases_action_message' in st.session_state:
        msg_type = st.session_state.test_cases_action_message.get('type', 'info')
        msg_text = st.session_state.test_cases_action_message.get('text', '')
        
        if msg_type == 'success':
            st.success(msg_text)
        elif msg_type == 'error':
            st.error(msg_text)
        elif msg_type == 'warning':
            st.warning(msg_text)
        else:
            st.info(msg_text)
        
        # Clear message sau khi hiển thị
        del st.session_state.test_cases_action_message
    
    # Upload và chỉnh sửa test cases
    st.write("### 📤 Upload và chỉnh sửa Test Cases")
    
    uploaded_file = st.file_uploader("Chọn file Excel chứa test cases", type=['xlsx', 'xls'], key="test_cases_uploader")
    
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            
            # Kiểm tra file rỗng
            if df.empty:
                st.error("❌ File Excel rỗng! Vui lòng tải lên file có dữ liệu.")
            else:
                # Kiểm tra có ít nhất 4 cột (câu hỏi, câu trả lời chuẩn, level, department)
                if len(df.columns) < 4:
                    st.error("❌ File Excel phải có ít nhất 4 cột (Câu hỏi, Câu trả lời chuẩn, Level, Department)!")
                else:
                    # Lấy 4 cột đầu tiên
                    questions = df.iloc[:, 0].tolist()
                    true_answers = df.iloc[:, 1].tolist()
                    levels = df.iloc[:, 2].tolist()
                    departments = df.iloc[:, 3].tolist()
                    
                    # Loại bỏ các dòng có dữ liệu rỗng
                    valid_data = []
                    for q, ta, l, d in zip(questions, true_answers, levels, departments):
                        if pd.notna(q) and pd.notna(ta) and pd.notna(l) and pd.notna(d) and \
                           str(q).strip() and str(ta).strip() and str(l).strip() and str(d).strip():
                            valid_data.append({
                                'Câu hỏi': str(q).strip(), 
                                'Câu trả lời chuẩn': str(ta).strip(),
                                'Level': str(l).strip(),
                                'Department': str(d).strip()
                            })
                    
                    if not valid_data:
                        st.error("❌ Không có dữ liệu hợp lệ trong file!")
                    else:
                        # Tạo DataFrame từ dữ liệu hợp lệ
                        test_cases_df = pd.DataFrame(valid_data)
                        
                        st.write("### 📝 Chỉnh sửa Test Cases")
                        st.info("💡 Bạn có thể chỉnh sửa trực tiếp trong bảng dưới đây. Thêm/xóa dòng bằng các nút bên dưới.")
                        
                        # Sử dụng st.data_editor để chỉnh sửa
                        edited_df = st.data_editor(
                            test_cases_df,
                            use_container_width=True,
                            hide_index=True,
                            num_rows="dynamic",
                            column_config={
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
                                "Level": st.column_config.TextColumn(
                                    "Level",
                                    help="Cấp độ câu hỏi",
                                    width="medium",
                                    required=True
                                ),
                                "Department": st.column_config.TextColumn(
                                    "Department",
                                    help="Phòng ban liên quan",
                                    width="medium",
                                    required=True
                                ),
                            },
                            key="test_cases_editor"
                        )
                        
                        # Nút lưu test cases
                        col1, col2 = st.columns([1, 3])
                        
                        with col1:
                            if st.button("💾 Lưu Test Cases", type="primary", use_container_width=True):
                                filepath = save_test_cases(site, edited_df)
                                if filepath:
                                    st.session_state.test_cases_action_message = {
                                        'type': 'success',
                                        'text': f'✅ Đã lưu test cases cho site "{site}" thành công!'
                                    }
                                else:
                                    st.session_state.test_cases_action_message = {
                                        'type': 'error',
                                        'text': '❌ Lỗi khi lưu test cases!'
                                    }
                                st.rerun()
                        
                        with col2:
                            st.metric("📊 Số test cases", len(edited_df))
        
        except Exception as e:
            st.error(f"❌ Lỗi khi đọc file Excel: {str(e)}")
    
    # Hiển thị test cases hiện tại
    st.write("### 📚 Test Cases hiện tại")
    
    if test_cases_exists(site):
        # Load test cases
        test_cases_df = load_test_cases(site)
        
        if test_cases_df is not None:
            # Kiểm tra xem có đang ở chế độ chỉnh sửa không
            editing_mode = st.session_state.get('editing_test_cases', False)
            
            if not editing_mode:
                # Chế độ xem
                st.write(f"**Số test cases:** {len(test_cases_df)}")
                
                # Hiển thị preview
                st.dataframe(test_cases_df.head(10), use_container_width=True)
                
                if len(test_cases_df) > 10:
                    st.caption(f"Hiển thị 10/{len(test_cases_df)} test cases đầu tiên")
                
                # Các nút action
                col1, col2, col3 = st.columns([1, 1, 1])
                
                with col1:
                    if st.button("✏️ Chỉnh sửa", key="edit_test_cases_btn", type="primary", use_container_width=True):
                        st.session_state.editing_test_cases = True
                        st.rerun()
                
                with col2:
                    # Nút tải xuống
                    try:
                        filepath = get_test_cases_file_path(site)
                        with open(filepath, "rb") as f:
                            st.download_button(
                                label="📥 Tải xuống",
                                data=f.read(),
                                file_name=f"{site}_test_cases.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key="download_test_cases",
                                use_container_width=True
                            )
                    except Exception as e:
                        st.error(f"Lỗi khi tải xuống file: {str(e)}")
                
                with col3:
                    if st.button("🗑️ Xóa", key="delete_test_cases_btn", type="secondary", use_container_width=True):
                        if delete_test_cases(site):
                            st.session_state.test_cases_action_message = {
                                'type': 'success',
                                'text': f'✅ Đã xóa test cases cho site "{site}"'
                            }
                        else:
                            st.session_state.test_cases_action_message = {
                                'type': 'error',
                                'text': '❌ Lỗi khi xóa test cases!'
                            }
                        st.rerun()
            
            else:
                # Chế độ chỉnh sửa
                st.info("💡 Bạn đang ở chế độ chỉnh sửa. Thêm/xóa/sửa dòng trực tiếp trong bảng dưới đây.")
                
                # Sử dụng st.data_editor để chỉnh sửa
                edited_df = st.data_editor(
                    test_cases_df,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="dynamic",
                    column_config={
                        test_cases_df.columns[0]: st.column_config.TextColumn(
                            test_cases_df.columns[0],
                            help="Nội dung câu hỏi",
                            width="large",
                            required=True
                        ),
                        test_cases_df.columns[1]: st.column_config.TextColumn(
                            test_cases_df.columns[1],
                            help="Câu trả lời mẫu để so sánh",
                            width="large",
                            required=True
                        ),
                        test_cases_df.columns[2]: st.column_config.TextColumn(
                            test_cases_df.columns[2],
                            help="Cấp độ câu hỏi",
                            width="medium",
                            required=True
                        ),
                        test_cases_df.columns[3]: st.column_config.TextColumn(
                            test_cases_df.columns[3],
                            help="Phòng ban liên quan",
                            width="medium",
                            required=True
                        ),
                    },
                    key="edit_existing_test_cases_editor"
                )
                
                # Nút lưu và hủy
                col1, col2, col3 = st.columns([1, 1, 4])
                
                with col1:
                    if st.button("💾 Lưu", type="primary", use_container_width=True, key="save_edited_test_cases"):
                        filepath = save_test_cases(site, edited_df)
                        if filepath:
                            st.session_state.test_cases_action_message = {
                                'type': 'success',
                                'text': f'✅ Đã cập nhật test cases cho site "{site}" thành công!'
                            }
                            st.session_state.editing_test_cases = False
                        else:
                            st.session_state.test_cases_action_message = {
                                'type': 'error',
                                'text': '❌ Lỗi khi lưu test cases!'
                            }
                        st.rerun()
                
                with col2:
                    if st.button("❌ Hủy", use_container_width=True, key="cancel_edit_test_cases"):
                        st.session_state.editing_test_cases = False
                        st.rerun()
                
                with col3:
                    st.metric("📊 Số test cases", len(edited_df))
    else:
        # Empty state với hướng dẫn chi tiết
        st.markdown("""
        <div style="text-align: center; padding: 40px 20px; background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%); border-radius: 10px; margin: 20px 0;">
            <h2 style="color: #667eea; margin-bottom: 20px;">📚 Chưa có Test Cases</h2>
            <p style="font-size: 16px; color: #666; margin-bottom: 30px;">
                Test cases giúp bạn quản lý và tái sử dụng bộ câu hỏi test.
            </p>
            <div style="text-align: left; max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                <h4 style="color: #333; margin-bottom: 15px;">🎯 Để tạo Test Cases:</h4>
                <ol style="color: #555; line-height: 1.8;">
                    <li>Cuộn lên phía trên tab này</li>
                    <li>Tìm phần <strong>"📤 Upload và chỉnh sửa Test Cases"</strong></li>
                    <li>Upload file Excel chứa test cases (4 cột: Câu hỏi, Câu trả lời chuẩn, Level, Department)</li>
                    <li>Chỉnh sửa nếu cần thiết</li>
                    <li>Đặt tên và nhấn <strong>"💾 Lưu Test Cases"</strong></li>
                </ol>
                <div style="margin-top: 20px; padding: 15px; background: #f8f9fa; border-left: 4px solid #667eea; border-radius: 4px;">
                    <strong style="color: #667eea;">💡 Lợi ích:</strong><br>
                    <span style="color: #666; font-size: 14px;">
                        • Dễ dàng chọn test cases cho lập lịch test tự động<br>
                        • Quản lý nhiều bộ test khác nhau<br>
                        • Tái sử dụng test cases cho nhiều lần chạy
                    </span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

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
    
    # Hiển thị thông báo nếu có trong session state
    if 'prompt_action_message' in st.session_state:
        msg_type = st.session_state.prompt_action_message.get('type', 'info')
        msg_text = st.session_state.prompt_action_message.get('text', '')
        
        if msg_type == 'success':
            st.success(msg_text)
        elif msg_type == 'error':
            st.error(msg_text)
        elif msg_type == 'warning':
            st.warning(msg_text)
        else:
            st.info(msg_text)
        
        # Clear message sau khi hiển thị
        del st.session_state.prompt_action_message
    
    # Load current prompts - Force reload nếu có flag reset
    if 'force_reload_prompts' in st.session_state and st.session_state.force_reload_prompts:
        # Clear text area keys để force reload
        if 'system_prompt_editor' in st.session_state:
            del st.session_state.system_prompt_editor
        if 'human_prompt_editor' in st.session_state:
            del st.session_state.human_prompt_editor
        st.session_state.force_reload_prompts = False
    
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
    
    # Save/Backup/Reset buttons - xử lý cả prompts và extract sections
    st.write("")  # Spacing
    col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
    with col1:
        if st.button("💾 Lưu", key="save_all", use_container_width=True, help="Lưu cả Prompts và Extract Sections"):
            success_prompts = save_prompts_for_site(site, system_prompt, human_prompt)
            
            # Tự động sinh và lưu extract sections từ system prompt
            if system_prompt:
                result = auto_generate_extract_sections_from_prompt(system_prompt)
                if result and result.get('code'):
                    success_extract = save_extract_sections_for_site(site, result['code'])
                else:
                    success_extract = False
            else:
                success_extract = True  # Không có lỗi nếu không có prompt
            
            # Refresh criteria từ system prompt mới
            if system_prompt:
                st.session_state.current_system_prompt = system_prompt
                # Cập nhật fail_criterion nếu cần
                new_criteria = get_criteria_from_prompt(system_prompt)
                current_criterion = st.session_state.get("fail_criterion", "accuracy")
                if current_criterion not in new_criteria and new_criteria:
                    st.session_state.fail_criterion = new_criteria[0]
            
            if success_prompts and success_extract:
                st.session_state.prompt_action_message = {
                    'type': 'success',
                    'text': '✅ Đã lưu prompts & extract sections! Criteria đã được cập nhật.'
                }
            elif success_prompts:
                st.session_state.prompt_action_message = {
                    'type': 'warning',
                    'text': '⚠️ Đã lưu prompts nhưng có lỗi khi lưu extract sections!'
                }
            else:
                st.session_state.prompt_action_message = {
                    'type': 'error',
                    'text': '❌ Lỗi khi lưu!'
                }
            time.sleep(0.5)  # Delay nhỏ để user thấy button được click
            st.rerun()
    
    with col2:
        if st.button("📦 Backup", key="backup_all", use_container_width=True, help="Backup cả Prompts và Extract Sections"):
            success_prompts = backup_prompts_for_site(site)
            success_extract = backup_extract_sections_for_site(site)
            
            if success_prompts and success_extract:
                st.session_state.prompt_action_message = {
                    'type': 'success',
                    'text': f'✅ Đã backup prompts & extract sections!\n💡 Backup được lưu tại: backup_prompts/{site}/'
                }
            elif success_prompts or success_extract:
                st.session_state.prompt_action_message = {
                    'type': 'warning',
                    'text': '⚠️ Đã backup một phần, vui lòng kiểm tra!'
                }
            else:
                st.session_state.prompt_action_message = {
                    'type': 'error',
                    'text': '❌ Lỗi khi backup!'
                }
            time.sleep(0.5)
            st.rerun()
    
    with col3:
        if st.button("🔄 Reset", key="reset_all", use_container_width=True, help="Reset cả Prompts và Extract Sections"):
            # Restore prompts
            result_prompts = restore_prompts_from_backup(site)
            # Restore extract sections
            result_extract = restore_extract_sections_from_backup(site)
            
            # Set flag để force reload prompts
            st.session_state.force_reload_prompts = True
            
            if result_prompts == "backup" and result_extract == "backup":
                st.session_state.prompt_action_message = {
                    'type': 'success',
                    'text': '✅ Đã reset từ backup!'
                }
            elif result_prompts == "original" or result_extract == "original":
                st.session_state.prompt_action_message = {
                    'type': 'info',
                    'text': '📄 Đã reset (một phần từ backup, một phần từ original)!'
                }
            elif result_prompts and result_extract:
                st.session_state.prompt_action_message = {
                    'type': 'success',
                    'text': '✅ Đã reset thành công!'
                }
            else:
                st.session_state.prompt_action_message = {
                    'type': 'warning',
                    'text': '⚠️ Không thể reset. Vui lòng kiểm tra backup hoặc original_prompts'
                }
            time.sleep(0.5)
            st.rerun()
    
    st.write("")  # Spacing
    
    # Extract Sections Management Section
    st.write("### 🔧 Preview Extract Sections")
    # st.info("💡 Extract sections sẽ tự động được tạo và lưu khi bạn nhấn nút **💾 Lưu** ở trên")
    
    # Tự động phân tích prompt và hiển thị mapping
    if system_prompt:
        # Tự động phân tích prompt hiện tại
        result = auto_generate_extract_sections_from_prompt(system_prompt)
        
        # Hiển thị mapping preview
        st.write("**Mapping sẽ được tạo từ System Prompt:**")
        
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
            
            # Hiển thị preview code
            with st.expander("👁️ Xem preview Extract Sections code", expanded=False):
                st.code(result['code'], language='python')
        else:
            st.warning("Không tìm thấy tiêu chí nào trong System Prompt")
    else:
        st.info("⚠️ Vui lòng nhập System Prompt để xem preview Extract Sections")
    
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
    
    # # Instructions
    # st.write("### 📋 Hướng dẫn")
    # st.markdown("""
    # **Quản lý Prompts:**
    # - System Prompt: Định nghĩa vai trò và tiêu chí đánh giá cho LLM
    # - Human Prompt: Template cho input được gửi đến LLM
    # - Sử dụng `{question}`, `{true_answer}`, `{agent_answer}`, `{level}`, `{department}` làm placeholders
    
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


with tab1:
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
            
            # Kiểm tra file rỗng
            if df.empty:
                st.error("❌ File Excel rỗng! Vui lòng tải lên file có dữ liệu.")
                st.stop()
            
            df = df.dropna(subset=[df.columns[0], df.columns[1]])
            
            # Kiểm tra sau khi dropna
            if df.empty:
                st.error("❌ File Excel không có dữ liệu hợp lệ! Vui lòng kiểm tra lại file.")
                st.stop()
            
            questions = df.iloc[:, 0].tolist()
            true_answers = df.iloc[:, 1].tolist()
            levels = df.iloc[:, 2].tolist() if len(df.columns) > 2 else ["L1"] * len(questions)
            departments = df.iloc[:, 3].tolist() if len(df.columns) > 3 else ["Phòng kinh doanh (Sales)"] * len(questions)
            
            # Khởi tạo edited test cases trong session state nếu chưa có
            if 'test_cases_df_thfc' not in st.session_state or st.session_state.get('current_file_thfc') != uploaded_file.name:
                st.session_state.test_cases_df_thfc = pd.DataFrame({
                    'Chọn': [True] * len(questions),
                    'Câu hỏi': questions,
                    'Câu trả lời chuẩn': true_answers,
                    'Level': levels,
                    'Department': departments
                })
                st.session_state.current_file_thfc = uploaded_file.name
            
            st.write("### 📋 Danh sách test cases")
            st.info("💡 Tip: Chọn các dòng bạn muốn chạy test bằng cách click vào checkbox ở đầu mỗi dòng.")
            
            # Sử dụng st.dataframe với selection
            selected_df = st.dataframe(
                st.session_state.test_cases_df_thfc,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="multi-row",
                key="test_cases_selection_thfc"
            )
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                st.metric("📊 Tổng test cases", len(st.session_state.test_cases_df_thfc))
            with col2:
                # Lấy số dòng được chọn từ selection
                selected_count = len(selected_df.selection.rows) if selected_df.selection.rows else 0
                st.metric("✅ Test cases được chọn", selected_count)
            with col3:
                if st.button("▶️ Chạy test", type="primary", use_container_width=True, key="run_batch_test_thfc"):
                    if selected_df.selection.rows:
                        # Lấy các dòng được chọn
                        selected_indices = selected_df.selection.rows
                        selected_questions = [st.session_state.test_cases_df_thfc.iloc[i]['Câu hỏi'] for i in selected_indices]
                        selected_true_answers = [st.session_state.test_cases_df_thfc.iloc[i]['Câu trả lời chuẩn'] for i in selected_indices]
                        selected_levels = [st.session_state.test_cases_df_thfc.iloc[i]['Level'] for i in selected_indices]
                        selected_departments = [st.session_state.test_cases_df_thfc.iloc[i]['Department'] for i in selected_indices]
                        
                        # Tạo progress container toàn màn hình
                        st.markdown("---")
                        progress_container = st.container()
                        with progress_container:
                            st.markdown("### ⏳ Tiến trình xử lý")
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            current_question_text = st.empty()
                        
                        history = st.session_state.chat_history if (add_chat_history_global and st.session_state.chat_history) else None
                        results, failed_questions = process_questions_batch(
                            selected_questions, 
                            selected_true_answers, 
                            selected_levels, 
                            selected_departments, 
                            add_chat_history=add_chat_history_global, 
                            custom_history=history, 
                            test_name=uploaded_file.name, 
                            site=get_current_site(),
                            progress_bar=progress_bar,
                            status_text=status_text,
                            current_question_text=current_question_text
                        )
                        
                        st.session_state.results = results
                        
                        data = {
                            'Question': [r["question"] for r in results],
                            'True Answer': [r["true_answer"] for r in results],
                            'Level': [r["level"] for r in results],
                            'Department': [r["department"] for r in results],
                            'Agent Answer': [r["site_response"] for r in results],
                            'Session ID': [r["chat_id"] for r in results],
                            'Relevance Score': [r["evaluate_result"]["scores"].get("relevance", 0) for r in results],
                            'Accuracy Score': [r["evaluate_result"]["scores"].get("accuracy", 0) for r in results],
                            'Completeness Score': [r["evaluate_result"]["scores"].get("completeness", 0) for r in results],
                            'Access Control Score': [r["evaluate_result"]["scores"].get("access_control", 0) for r in results],
                            'Clarity Score': [r["evaluate_result"]["scores"].get("clarity", 0) for r in results],
                            'Average Score': [r["evaluate_result"]["scores"].get("average", 0) for r in results],
                            'Comment': [r["evaluate_result"].get("comments", "") for r in results]
                        }
                        results_df = pd.DataFrame(data)
                        st.session_state.results_df = results_df
                        st.rerun()  # Reload để hiển thị kết quả bên ngoài
                    else:
                        st.warning("⚠️ Vui lòng chọn ít nhất một test case để chạy")
        except Exception as e:
            st.error(f"Lỗi khi đọc file Excel: {str(e)}")
            
        # Hiển thị kết quả test hàng loạt (toàn màn hình) - di chuyển ra ngoài column
        if 'results' in st.session_state and st.session_state.results:
            results = st.session_state.results
            results_df = st.session_state.results_df
            
            st.write("---")
            st.subheader(f"📊 Kết quả đánh giá ({len(results)} câu hỏi)")
            
            # Hiển thị metrics tổng quan với styling đẹp hơn
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
            
            # Grid metrics với styling đẹp
            passed_count = sum(1 for r in results if "failed_details" not in r)
            failed_count = sum(1 for r in results if "failed_details" in r)
            avg_score = sum(r["evaluate_result"]["scores"].get("average", 0) for r in results) / len(results) if results else 0
            pass_rate = (passed_count / len(results) * 100) if results else 0
            
            st.markdown(f"""
            <div class="dashboard-grid">
                <div class="metric-card metric-card-success">
                    <div class="metric-label">✅ Passed</div>
                    <div class="metric-value">{passed_count}</div>
                </div>
                <div class="metric-card metric-card-danger">
                    <div class="metric-label">❌ Failed</div>
                    <div class="metric-value">{failed_count}</div>
                </div>
                <div class="metric-card metric-card-info">
                    <div class="metric-label">📈 Điểm TB</div>
                    <div class="metric-value">{avg_score:.2f}</div>
                </div>
                <div class="metric-card metric-card-info">
                    <div class="metric-label">📊 Tỷ lệ pass</div>
                    <div class="metric-value">{pass_rate:.1f}%</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Hiển thị dataframe với styling tốt hơn
            st.write("### 📋 Chi tiết kết quả")
            st.dataframe(
                results_df, 
                use_container_width=True, 
                hide_index=True,
                height=400  # Tăng chiều cao để hiển thị nhiều dòng hơn
            )
            
            # Nút tải xuống và thông báo
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
                if failed_count > 0:
                    st.warning(f"⚠️ Có {failed_count} câu hỏi xử lý thất bại")
                else:
                    st.success(f"✅ Đã hoàn thành đánh giá {len(results)} câu hỏi")
    else:
        st.info("Vui lòng tải lên file Excel để bắt đầu")

with tab2:
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
            
            # Show next run time - Dùng Schedule Manager
            if schedule_manager:
                # Thử lấy thời gian từ schedule job trước
                next_run_vn = schedule_manager.get_next_run(site)
                
                # Nếu không có, tính toán từ config
                if not next_run_vn:
                    next_run_vn = schedule_manager.calculate_next_run_time(site)
                
                if next_run_vn:
                    st.write(f"**Chạy lần tới:** {next_run_vn.strftime('%Y-%m-%d %H:%M:%S')} (GMT+7)")
                    st.caption("⏰ Thời gian được tính toán tự động và persistent qua các lần reload")
                    
                    # Tự động save config sau khi hiển thị
                    try:
                        schedule_manager.save_schedules(schedule_manager.get_all_schedule_configs())
                        st.caption("💾 Cấu hình đã được lưu tự động")
                    except Exception as e:
                        logger.warning(f"Không thể lưu config: {e}")
                else:
                    # Fallback: Hiển thị thông tin lịch
                    schedule_type = existing_job.get('schedule_type', 'N/A')
                    schedule_time = existing_job.get('schedule_time', 'N/A')
                    schedule_day = existing_job.get('schedule_day', 'N/A')
                    
                    if schedule_type == "minute":
                        st.write(f"**Chạy lần tới:** Mỗi phút")
                    elif schedule_type == "hourly":
                        st.write(f"**Chạy lần tới:** Mỗi giờ tại phút {schedule_time.split(':')[1] if ':' in schedule_time else '00'}")
                    elif schedule_type == "daily":
                        st.write(f"**Chạy lần tới:** Mỗi ngày lúc {schedule_time}")
                    elif schedule_type == "weekly":
                        st.write(f"**Chạy lần tới:** Mỗi {schedule_day} lúc {schedule_time}")
                    elif schedule_type == "custom":
                        interval = existing_job.get('custom_interval', 'N/A')
                        unit = existing_job.get('custom_unit', 'N/A')
                        st.write(f"**Chạy lần tới:** Mỗi {interval} {unit}")
                    else:
                        st.write(f"**Chạy lần tới:** {schedule_type} - {schedule_time}")
            else:
                st.warning("⚠️ Schedule Manager chưa khởi tạo")
        
        with col2:
            if st.button("Chỉnh sửa", key="edit_existing_job"):
                st.session_state.editing_existing_job = True
                st.rerun()
            
            if st.button("Xóa cấu hình", key="delete_existing_job"):
                # Sử dụng Schedule Manager để xóa
                if schedule_manager:
                    if schedule_manager.remove_schedule(site):
                        st.success(f"✅ Đã xóa lịch test cho site '{site}'. Test cases và kết quả test vẫn được giữ lại.")
                    else:
                        st.error("❌ Lỗi khi xóa lịch test!")
                else:
                    st.error("❌ Schedule Manager chưa khởi tạo!")
                
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
                        
                        # Xóa job cũ và tạo lại với cấu hình mới
                        jobs_to_remove = []
                        for job in schedule.jobs:
                            try:
                                if len(job.job_func.args) >= 3 and job.job_func.args[1] == existing_job['test_name'] and job.job_func.args[2] == existing_job['site']:
                                    jobs_to_remove.append(job)
                            except (IndexError, AttributeError):
                                continue
                        
                        for job in jobs_to_remove:
                            schedule.cancel_job(job)
                        
                        # Tạo lại job với cấu hình mới
                        setup_schedule(
                            file_path=st.session_state.scheduled_jobs[job_index]['file_path'],
                            schedule_type=new_schedule_type,
                            schedule_time=new_schedule_time,
                            schedule_day=new_schedule_day,
                            test_name=new_test_name,
                            site=site,
                            api_url=new_api_url,
                            evaluate_api_url=new_eval_api_url,
                            custom_interval=new_custom_interval,
                            custom_unit=new_custom_unit
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

        st.write("### Bước 2: Kiểm tra test cases và đặt tên")
        
        # Check if test cases exist
        if not test_cases_exists(site):
            st.warning("⚠️ Chưa có test cases cho site này. Vui lòng tạo test cases trong tab 'Quản lý Test Cases' trước.")
            st.stop()
        
        # Load test cases
        test_cases_df = load_test_cases(site)
        
        if test_cases_df is not None:
            st.write(f"**Test cases hiện tại:** {len(test_cases_df)} test cases")
            st.write("**Preview 5 test cases đầu tiên:**")
            st.dataframe(test_cases_df.head(5), use_container_width=True)
        else:
            st.error("❌ Lỗi khi đọc test cases!")
            st.stop()
        
        test_name = st.text_input("Tên bộ test (để nhận diện trong lịch sử)", key="test_name_input")

        if test_name:
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
                # Lấy đường dẫn file test cases của site
                saved_file_path = get_test_cases_file_path(site)

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
                
                # Sử dụng Schedule Manager để lưu
                if schedule_manager:
                    if schedule_manager.update_schedule(site, job_config):
                        st.success(f"Đã thiết lập lịch chạy test '{test_name}' cho site '{site}'.")
                    else:
                        st.error("❌ Lỗi khi lưu lịch test!")
                else:
                    st.error("❌ Schedule Manager chưa khởi tạo!")
                
                st.rerun()

# Hiển thị hướng dẫn sử dụng
st.sidebar.subheader("Hướng dẫn sử dụng")
st.sidebar.markdown("""
### Test hàng loạt
1. Tải file Excel.
2. Chọn các câu hỏi muốn test.
3. Nhấn "Test hàng loạt".

### Lập lịch test
1. Chọn test cases đã lưu và đặt tên.
2. Thiết lập lịch và nhấn "Thiết lập lịch".

### Quản lý test
1. Xem lịch sử và các test case thất bại.

### Quản lý Test Cases
1. Upload file Excel chứa test cases.
2. Chỉnh sửa và lưu test cases.
3. Quản lý các bộ test cases đã lưu.

### Quản lý Prompts
1. Chỉnh sửa system prompt và human prompt.
2. Cập nhật extract sections code.
3. Lưu để áp dụng thay đổi.
""")