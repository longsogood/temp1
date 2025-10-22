import streamlit as st
import os
import shutil
import json

st.set_page_config(page_title="Quản lý Sites", page_icon="⚙️", layout="wide")

st.title("⚙️ Quản lý Sites")

# File để lưu danh sách sites
SITES_CONFIG_FILE = "sites_config.json"

def load_sites_config():
    """Load danh sách sites từ file"""
    if os.path.exists(SITES_CONFIG_FILE):
        with open(SITES_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        # Mặc định có 2 sites ban đầu
        return {
            "sites": [
                {"name": "Agent HR Nội bộ", "created_date": "2025-01-01"},
                {"name": "THFC", "created_date": "2025-01-01"}
            ]
        }

def save_sites_config(config):
    """Lưu danh sách sites vào file"""
    with open(SITES_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def create_site_structure(site_name):
    """Tạo cấu trúc thư mục và file cho site mới"""
    # Tạo thư mục prompts
    prompts_dir = os.path.join("prompts", site_name)
    os.makedirs(prompts_dir, exist_ok=True)
    
    # Tạo thư mục utils
    utils_dir = os.path.join("utils", site_name)
    os.makedirs(utils_dir, exist_ok=True)
    
    # Tạo thư mục test_results
    results_dir = os.path.join("test_results", site_name)
    os.makedirs(results_dir, exist_ok=True)
    
    # Tạo thư mục scheduled_tests
    scheduled_dir = os.path.join("scheduled_tests", site_name)
    os.makedirs(scheduled_dir, exist_ok=True)
    
    # Copy prompt templates từ Agent HR Nội bộ
    hr_prompts_dir = os.path.join("prompts", "Agent HR Nội bộ")
    if os.path.exists(hr_prompts_dir):
        for file in ["system_prompt.txt", "human_prompt.txt"]:
            src = os.path.join(hr_prompts_dir, file)
            dst = os.path.join(prompts_dir, file)
            if os.path.exists(src):
                shutil.copy2(src, dst)
    
    # Copy extract_sections.py từ Agent HR Nội bộ
    hr_utils_dir = os.path.join("utils", "Agent HR Nội bộ")
    if os.path.exists(hr_utils_dir):
        src = os.path.join(hr_utils_dir, "extract_sections.py")
        dst = os.path.join(utils_dir, "extract_sections.py")
        if os.path.exists(src):
            shutil.copy2(src, dst)
    
    # Tạo file Python cho site mới (copy từ Agent HR Nội bộ)
    template_file = "pages/Agent HR Nội bộ.py"
    new_site_file = f"pages/{site_name}.py"
    
    if os.path.exists(template_file):
        with open(template_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Thay đổi SITE variable
        content = content.replace(
            'SITE = "Agent HR Nội bộ"',
            f'SITE = "{site_name}"'
        )
        
        with open(new_site_file, "w", encoding="utf-8") as f:
            f.write(content)
    
    return True

def delete_site_structure(site_name):
    """Xóa cấu trúc thư mục và file của site"""
    # Xóa thư mục prompts
    prompts_dir = os.path.join("prompts", site_name)
    if os.path.exists(prompts_dir):
        shutil.rmtree(prompts_dir)
    
    # Xóa thư mục utils
    utils_dir = os.path.join("utils", site_name)
    if os.path.exists(utils_dir):
        shutil.rmtree(utils_dir)
    
    # KHÔNG xóa test_results để giữ lại dữ liệu test
    
    # Xóa file Python của site
    site_file = f"pages/{site_name}.py"
    if os.path.exists(site_file):
        os.remove(site_file)

# Load config
sites_config = load_sites_config()

# Hiển thị danh sách sites hiện có
st.write("### 📋 Danh sách Sites hiện có")

col1, col2 = st.columns([3, 1])

with col1:
    st.dataframe(
        sites_config["sites"],
        use_container_width=True,
        hide_index=True
    )

with col2:
    st.metric("Tổng số Sites", len(sites_config["sites"]))

st.divider()

# Thêm site mới
st.write("### ➕ Thêm Site mới")

with st.form("add_site_form"):
    col1, col2 = st.columns([3, 1])
    
    with col1:
        new_site_name = st.text_input(
            "Tên Site mới",
            placeholder="Ví dụ: Agent Marketing",
            help="Tên site sẽ được sử dụng để tạo trang và thư mục"
        )
    
    with col2:
        st.write("")  # Spacer
        st.write("")  # Spacer
        submit_add = st.form_submit_button("➕ Thêm Site", use_container_width=True)
    
    if submit_add and new_site_name:
        # Kiểm tra xem site đã tồn tại chưa
        existing_sites = [s["name"] for s in sites_config["sites"]]
        if new_site_name in existing_sites:
            st.error(f"❌ Site '{new_site_name}' đã tồn tại!")
        else:
            try:
                # Tạo cấu trúc cho site mới
                create_site_structure(new_site_name)
                
                # Thêm vào config
                from datetime import datetime
                sites_config["sites"].append({
                    "name": new_site_name,
                    "created_date": datetime.now().strftime("%Y-%m-%d")
                })
                save_sites_config(sites_config)
                
                st.success(f"✅ Đã tạo site '{new_site_name}' thành công!")
                st.info("🔄 Vui lòng refresh trang để thấy site mới trong menu.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Lỗi khi tạo site: {str(e)}")
    elif submit_add:
        st.warning("⚠️ Vui lòng nhập tên site!")

st.divider()

# Xóa site
st.write("### 🗑️ Xóa Site")

with st.form("delete_site_form"):
    col1, col2 = st.columns([3, 1])
    
    with col1:
        existing_sites = [s["name"] for s in sites_config["sites"]]
        # Không cho xóa 2 site mặc định
        deletable_sites = [s for s in existing_sites if s not in ["Agent HR Nội bộ", "THFC"]]
        
        if deletable_sites:
            site_to_delete = st.selectbox(
                "Chọn Site để xóa",
                deletable_sites,
                help="Chỉ xóa code và cấu hình, dữ liệu test sẽ được giữ lại"
            )
        else:
            st.info("📝 Chưa có site nào có thể xóa (không thể xóa 2 site mặc định)")
            site_to_delete = None
    
    with col2:
        st.write("")  # Spacer
        st.write("")  # Spacer
        submit_delete = st.form_submit_button("🗑️ Xóa Site", use_container_width=True, type="primary")
    
    if submit_delete and site_to_delete:
        try:
            # Xóa cấu trúc
            delete_site_structure(site_to_delete)
            
            # Xóa khỏi config
            sites_config["sites"] = [s for s in sites_config["sites"] if s["name"] != site_to_delete]
            save_sites_config(sites_config)
            
            st.success(f"✅ Đã xóa site '{site_to_delete}' thành công!")
            st.info("🔄 Vui lòng refresh trang để cập nhật menu.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Lỗi khi xóa site: {str(e)}")

st.divider()

# Hướng dẫn
st.write("### 📖 Hướng dẫn")

# st.markdown("""
# **Thêm Site mới:**
# 1. Nhập tên site mới vào ô text input
# 2. Nhấn "Thêm Site"
# 3. Hệ thống sẽ tự động:
#    - Tạo cấu trúc thư mục (prompts, utils, test_results, scheduled_tests)
#    - Copy template từ Agent HR Nội bộ
#    - Tạo file Python cho site mới
# 4. Refresh trang để thấy site mới trong menu

# **Xóa Site:**
# 1. Chọn site muốn xóa từ dropdown
# 2. Nhấn "Xóa Site"
# 3. Hệ thống sẽ xóa code và cấu hình, nhưng giữ lại dữ liệu test

# **Lưu ý:**
# - Không thể xóa 2 site mặc định: "Agent HR Nội bộ" và "THFC"
# - Dữ liệu test trong thư mục `test_results` sẽ được giữ lại khi xóa site
# - Sau khi thêm/xóa site, cần refresh trang để cập nhật menu
# """)

