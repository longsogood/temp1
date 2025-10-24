import streamlit as st
import os
import shutil
import json
from pathlib import Path

st.set_page_config(
    layout="wide",
    page_title="Quản lý Sites",
    page_icon="🏢"
)

st.title("🏢 Quản lý Sites")

# Helper functions
def get_all_sites():
    """Lấy danh sách tất cả các site từ thư mục pages"""
    pages_dir = "pages"
    sites = []
    
    if os.path.exists(pages_dir):
        for file in os.listdir(pages_dir):
            if file.endswith(".py") and file != "Quản lý Sites.py":
                site_name = file.replace(".py", "")
                sites.append(site_name)
    
    return sorted(sites)

def get_site_info(site_name):
    """Lấy thông tin chi tiết của site"""
    info = {
        "prompts_exist": False,
        "backup_exist": False,
        "test_results_exist": False,
        "scheduled_test_exist": False
    }
    
    # Check prompts
    prompts_path = os.path.join("prompts", site_name)
    if os.path.exists(prompts_path):
        info["prompts_exist"] = True
        info["prompts_count"] = len([f for f in os.listdir(prompts_path) if f.endswith(".txt")])
    
    # Check backup
    backup_path = os.path.join("backup_prompts", site_name)
    if os.path.exists(backup_path):
        info["backup_exist"] = True
        info["backup_count"] = len([f for f in os.listdir(backup_path)])
    
    # Check test results
    results_path = os.path.join("test_results", site_name)
    if os.path.exists(results_path):
        info["test_results_exist"] = True
        info["results_count"] = len([f for f in os.listdir(results_path) if f.endswith(('.xlsx', '.xls'))])
    
    # Check scheduled tests - chỉ đánh dấu True nếu có file test
    scheduled_path = os.path.join("scheduled_tests", site_name)
    if os.path.exists(scheduled_path):
        scheduled_files = [f for f in os.listdir(scheduled_path) if f.endswith(('.xlsx', '.xls'))]
        if scheduled_files:
            info["scheduled_test_exist"] = True
            info["scheduled_count"] = len(scheduled_files)
    
    return info

def create_new_site(site_name):
    """Tạo site mới từ template"""
    try:
        # Copy original_site.py to pages/{site_name}.py
        source = "original_site.py"
        dest = os.path.join("pages", f"{site_name}.py")
        
        if os.path.exists(dest):
            return False, "Site đã tồn tại!"
        
        # Read template
        with open(source, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace SITE variable
        content = content.replace('SITE = "Agent HR Nội bộ"', f'SITE = "{site_name}"')
        
        # Write new file
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Tự động copy prompts từ original_prompts
        original_prompts_dir = "original_prompts"
        if os.path.exists(original_prompts_dir):
            # Create site prompts directory
            site_prompts_dir = os.path.join("prompts", site_name)
            os.makedirs(site_prompts_dir, exist_ok=True)
            
            # Copy prompts
            for prompt_file in ["system_prompt.txt", "human_prompt.txt"]:
                source_prompt = os.path.join(original_prompts_dir, prompt_file)
                if os.path.exists(source_prompt):
                    dest_prompt = os.path.join(site_prompts_dir, prompt_file)
                    shutil.copy2(source_prompt, dest_prompt)
            
            # Create utils directory and copy extract_sections
            site_utils_dir = os.path.join("utils", site_name)
            os.makedirs(site_utils_dir, exist_ok=True)
            
            source_extract = os.path.join(original_prompts_dir, "extract_sections.py")
            if os.path.exists(source_extract):
                dest_extract = os.path.join(site_utils_dir, "extract_sections.py")
                shutil.copy2(source_extract, dest_extract)
        
        # Initialize schedule config for the new site in schedule_config.json
        schedule_config_file = "schedule_config.json"
        try:
            # Load existing config
            if os.path.exists(schedule_config_file):
                with open(schedule_config_file, 'r', encoding='utf-8') as f:
                    schedule_config = json.load(f)
            else:
                schedule_config = {}
            
            # Initialize empty schedule for new site (only if not exists)
            if site_name not in schedule_config:
                schedule_config[site_name] = None
                
                # Save updated config
                with open(schedule_config_file, 'w', encoding='utf-8') as f:
                    json.dump(schedule_config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            # Log but don't fail site creation if schedule init fails
            print(f"Warning: Failed to initialize schedule config for {site_name}: {e}")
        
        return True, f"Đã tạo site mới: {site_name} (bao gồm prompts & extract sections)"
        
    except Exception as e:
        return False, f"Lỗi khi tạo site: {str(e)}"

def delete_site(site_name):
    """Xóa site và toàn bộ dữ liệu liên quan"""
    try:
        deleted_items = []
        
        # Delete page file
        page_file = os.path.join("pages", f"{site_name}.py")
        if os.path.exists(page_file):
            os.remove(page_file)
            deleted_items.append("Page file")
        
        # Delete prompts
        prompts_dir = os.path.join("prompts", site_name)
        if os.path.exists(prompts_dir):
            shutil.rmtree(prompts_dir)
            deleted_items.append("Prompts")
        
        # Delete backup
        backup_dir = os.path.join("backup_prompts", site_name)
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)
            deleted_items.append("Backup prompts")
        
        # Delete utils
        utils_dir = os.path.join("utils", site_name)
        if os.path.exists(utils_dir):
            shutil.rmtree(utils_dir)
            deleted_items.append("Utils")
        
        # Delete test results
        results_dir = os.path.join("test_results", site_name)
        if os.path.exists(results_dir):
            shutil.rmtree(results_dir)
            deleted_items.append("Test results")
        
        # Delete scheduled tests
        scheduled_dir = os.path.join("scheduled_tests", site_name)
        if os.path.exists(scheduled_dir):
            shutil.rmtree(scheduled_dir)
            deleted_items.append("Scheduled tests")
        
        # Remove schedule config from schedule_config.json
        schedule_config_file = "schedule_config.json"
        try:
            if os.path.exists(schedule_config_file):
                with open(schedule_config_file, 'r', encoding='utf-8') as f:
                    schedule_config = json.load(f)
                
                # Remove site's schedule if it exists
                if site_name in schedule_config:
                    del schedule_config[site_name]
                    deleted_items.append("Schedule config")
                    
                    # Save updated config
                    with open(schedule_config_file, 'w', encoding='utf-8') as f:
                        json.dump(schedule_config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            # Log but don't fail deletion if schedule cleanup fails
            print(f"Warning: Failed to remove schedule config for {site_name}: {e}")
        
        return True, f"Đã xóa: {', '.join(deleted_items)}"
        
    except Exception as e:
        return False, f"Lỗi khi xóa site: {str(e)}"

# Main UI
st.write("### 📊 Danh sách Sites")

sites = get_all_sites()

if not sites:
    st.info("Chưa có site nào. Hãy tạo site mới bên dưới.")
else:
    # Display sites in a table
    sites_data = []
    for site in sites:
        info = get_site_info(site)
        sites_data.append({
            "Site": site,
            "📝 Prompts": "✅" if info["prompts_exist"] else "❌",
            "📦 Backup": "✅" if info["backup_exist"] else "❌",
            "📊 Test Results": f"{info.get('results_count', 0)} files" if info["test_results_exist"] else "-",
            "⏰ Scheduled": "✅" if info["scheduled_test_exist"] else "❌"
        })
    
    import pandas as pd
    df = pd.DataFrame(sites_data)
    
    # Display with selection
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    st.write(f"**Tổng số sites:** {len(sites)}")

# Create new site section
st.write("---")
st.write("### ➕ Tạo Site Mới")

col1, col2 = st.columns([3, 1])

with col1:
    new_site_name = st.text_input(
        "Tên site mới",
        placeholder="Ví dụ: Customer Support, Sales Team, ...",
        help="Nhập tên site, không cần thêm số thứ tự"
    )

with col2:
    st.write("")  # Spacing
    st.write("")  # Spacing
    if st.button("🎯 Tạo Site", type="primary", use_container_width=True):
        if new_site_name:
            success, message = create_new_site(new_site_name)
            if success:
                st.success(message)
                st.info("💡 Site mới đã được tạo! Reload trang để thấy site mới trong menu.")
                st.rerun()
            else:
                st.error(message)
        else:
            st.warning("Vui lòng nhập tên site")

# Delete site section
st.write("---")
st.write("### 🗑️ Xóa Site")

st.warning("⚠️ **Cảnh báo**: Xóa site sẽ xóa toàn bộ dữ liệu liên quan (prompts, backup, test results, ...)")

if sites:
    col1, col2 = st.columns([3, 1])
    
    with col1:
        site_to_delete = st.selectbox(
            "Chọn site cần xóa",
            sites,
            help="Chọn site muốn xóa"
        )
        
        # Show info about what will be deleted
        if site_to_delete:
            info = get_site_info(site_to_delete)
            st.write("**Sẽ xóa:**")
            
            items_to_delete = []
            if info["prompts_exist"]:
                items_to_delete.append(f"📝 Prompts ({info.get('prompts_count', 0)} files)")
            if info["backup_exist"]:
                items_to_delete.append(f"📦 Backup ({info.get('backup_count', 0)} files)")
            if info["test_results_exist"]:
                items_to_delete.append(f"📊 Test Results ({info.get('results_count', 0)} files)")
            if info["scheduled_test_exist"]:
                items_to_delete.append(f"⏰ Scheduled Tests ({info.get('scheduled_count', 0)} files)")
            
            if items_to_delete:
                for item in items_to_delete:
                    st.write(f"- {item}")
            else:
                st.write("- Chỉ xóa page file (không có dữ liệu khác)")
    
    with col2:
        st.write("")  # Spacing
        st.write("")  # Spacing
        
        # Confirmation checkbox
        confirm_delete = st.checkbox("Xác nhận xóa", key="confirm_delete")
        
        if st.button("❌ Xóa Site", type="secondary", use_container_width=True, disabled=not confirm_delete):
            if confirm_delete:
                success, message = delete_site(site_to_delete)
                if success:
                    st.success(message)
                    st.info("💡 Site đã được xóa! Reload trang để cập nhật menu.")
                    st.rerun()
                else:
                    st.error(message)
else:
    st.info("Không có site nào để xóa")

# Site information section
st.write("---")
st.write("### 📋 Chi tiết Site")

if sites:
    selected_site = st.selectbox("Chọn site để xem chi tiết", sites, key="site_detail_select")
    
    if selected_site:
        info = get_site_info(selected_site)
        
        # Display in columns
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "📝 Prompts",
                "Có" if info["prompts_exist"] else "Không",
                f"{info.get('prompts_count', 0)} files" if info["prompts_exist"] else None
            )
        
        with col2:
            st.metric(
                "📦 Backup",
                "Có" if info["backup_exist"] else "Không",
                f"{info.get('backup_count', 0)} files" if info["backup_exist"] else None
            )
        
        with col3:
            st.metric(
                "📊 Test Results",
                info.get('results_count', 0) if info["test_results_exist"] else 0,
                "files"
            )
        
        with col4:
            st.metric(
                "⏰ Scheduled",
                "Có" if info["scheduled_test_exist"] else "Không",
                f"{info.get('scheduled_count', 0)} files" if info["scheduled_test_exist"] else None
            )
        
        # File paths
        st.write("**📁 Đường dẫn:**")
        
        paths = {
            "Page file": os.path.join("pages", f"{selected_site}.py"),
            "Prompts": os.path.join("prompts", selected_site),
            "Backup": os.path.join("backup_prompts", selected_site),
            "Utils": os.path.join("utils", selected_site),
            "Test Results": os.path.join("test_results", selected_site),
            "Scheduled Tests": os.path.join("scheduled_tests", selected_site)
        }
        
        for name, path in paths.items():
            exists = os.path.exists(path)
            status = "✅" if exists else "❌"
            st.write(f"{status} **{name}**: `{path}`")

# Instructions
st.write("---")
st.write("### 📖 Hướng dẫn")

with st.expander("💡 Cách tạo site mới", expanded=False):
    st.markdown("""
    **Bước 1:** Nhập tên site vào ô "Tên site mới"
    
    **Bước 2:** Nhấn nút "🎯 Tạo Site"
    
    **Bước 3:** Reload trang (Ctrl+R hoặc F5) để thấy site mới trong sidebar
    
    **Bước 4:** Vào site mới và cấu hình prompts trong tab "Quản lý Prompts"
    
    ---
    
    **Lưu ý:**
    - Site mới sẽ tự động copy prompts từ `original_prompts/`
    - Bạn có thể chỉnh sửa prompts sau khi tạo
    - Mỗi site có thư mục riêng cho prompts, backup, và test results
    """)

with st.expander("⚙️ Cấu trúc thư mục site", expanded=False):
    st.markdown("""
    Mỗi site sẽ có cấu trúc thư mục như sau:
    
    ```
    ├── pages/
    │   └── {Site Name}.py              # Page chính của site
    ├── prompts/
    │   └── {Site Name}/
    │       ├── system_prompt.txt       # System prompt
    │       └── human_prompt.txt        # Human prompt template
    ├── backup_prompts/
    │   └── {Site Name}/
    │       ├── system_prompt.txt       # Backup của system prompt
    │       ├── human_prompt.txt        # Backup của human prompt
    │       └── extract_sections.py     # Backup của extract code
    ├── utils/
    │   └── {Site Name}/
    │       └── extract_sections.py     # Code để extract kết quả đánh giá
    ├── test_results/
    │   └── {Site Name}/
    │       ├── test_*.xlsx             # File kết quả test
    │       ├── failed_tests.pkl        # Cache các test thất bại
    │       └── test_history.pkl        # Lịch sử test
    └── scheduled_tests/
        └── {Site Name}/
            └── *.xlsx                  # File test cho lịch test tự động
    ```
    """)

with st.expander("🗑️ Xóa site an toàn", expanded=False):
    st.markdown("""
    **Trước khi xóa site:**
    
    1. ✅ Backup dữ liệu quan trọng (nếu cần)
    2. ✅ Xem lại chi tiết site để biết sẽ xóa gì
    3. ✅ Tick vào "Xác nhận xóa"
    4. ✅ Nhấn nút "❌ Xóa Site"
    
    **Lưu ý:**
    - Xóa site sẽ xóa toàn bộ dữ liệu liên quan
    - Hành động này **KHÔNG THỂ HOÀN TÁC**
    - Test results và backup cũng sẽ bị xóa
    - Nếu site đang có scheduled job, hãy xóa job trước
    """)

# Sidebar info
st.sidebar.subheader("📊 Thống kê")
st.sidebar.metric("Tổng số sites", len(sites))

if sites:
    total_with_prompts = sum(1 for s in sites if get_site_info(s)["prompts_exist"])
    total_with_backup = sum(1 for s in sites if get_site_info(s)["backup_exist"])
    total_with_results = sum(1 for s in sites if get_site_info(s)["test_results_exist"])
    
    st.sidebar.metric("Sites có prompts", total_with_prompts)
    st.sidebar.metric("Sites có backup", total_with_backup)
    st.sidebar.metric("Sites có test results", total_with_results)
