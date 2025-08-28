import streamlit as st
import json
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import boto3
from dotenv import load_dotenv
import os
from langfuse import Langfuse

# Cấu hình trang
st.set_page_config(
    page_title="Trace Analysis Demo",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS tùy chỉnh
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .trace-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
        border-left: 4px solid #1f77b4;
    }
    .tool-call {
        background-color: #e3f2fd;
        border-radius: 8px;
        padding: 0.8rem;
        margin: 0.5rem 0;
        border-left: 3px solid #2196f3;
    }
    .tool-result {
        background-color: #f3e5f5;
        border-radius: 8px;
        padding: 0.8rem;
        margin: 0.5rem 0;
        border-left: 3px solid #9c27b0;
    }
    .user-message {
        background-color: #e8f5e8;
        border-radius: 8px;
        padding: 0.8rem;
        margin: 0.5rem 0;
        border-left: 3px solid #4caf50;
    }
    .assistant-message {
        background-color: #fff3e0;
        border-radius: 8px;
        padding: 0.8rem;
        margin: 0.5rem 0;
        border-left: 3px solid #ff9800;
    }
    .metric-card {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Load environment variables
load_dotenv(".env")

AWS_ACCESS_KEY_ID = st.secrets["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]
AWS_REGION = st.secrets["AWS_REGION"]
LANGFUSE_PUBLIC_KEY = st.secrets["LANGFUSE_PUBLIC_KEY"]
LANGFUSE_SECRET_KEY = st.secrets["LANGFUSE_SECRET_KEY"]
LANGFUSE_HOST = st.secrets["LANGFUSE_HOST"]

class TokenCounter:
    def __init__(self, model_id, aws_access_key_id, aws_secret_access_key, region_name,
                 langfuse_public_key, langfuse_secret_key, langfuse_host):
        self.model_id = model_id
        self.client = boto3.client('bedrock-runtime',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name
        )
        self.langfuse = Langfuse(
            public_key=langfuse_public_key,
            secret_key=langfuse_secret_key,
            host=langfuse_host
        )

    def get_tracing_result(self, session_id):
        result = {"session_id": session_id, "traces": []}

        # Lấy thông tin session
        print(f"Session id: {session_id}")
        session = self.langfuse.api.sessions.get(session_id)
        session_json = json.loads(session.json())

        # Lấy trace id
        traces = session_json['traces']
        traces = sorted(traces, key=lambda x: x["timestamp"])
        print(f"Traces: {traces}")
        for trace in traces:
            trace_result = {
                "trace_id": trace['id'],
                "observations": []
            }
            print(f"\tGetting observation of trace id: {trace['id']}")
            # Lấy thông tin trace
            trace = self.langfuse.api.trace.get(trace['id'])
            trace_json = json.loads(trace.json())
            observations = trace_json['observations']
            observations = sorted([obs for obs in observations if obs['type'] == 'GENERATION'], key=lambda x: x["startTime"])
            for obs in observations:
                obs_result = {
                    "observation_id": obs['id'],
                    "messages": [],
                    "system": []
                }
                print("="*100)
                print(f"\t\tObservation id: {obs['id']}")
                obs_input = obs['input']
                
                current_tool_id = None
                for inp in obs_input:
                    message_temp = {}
                    system_temp = {"text": ""}
                    print('-'*100)
                    print("\t\t\t",inp)
                    if 'role' not in inp.keys():
                        if 'additional_kwargs' not in inp.keys():
                            system_temp["text"] = inp['content']
                            obs_result["system"].append(system_temp)
                            print("\t\t\tSystem temp:", system_temp)
                        else:
                            message_temp['role'] = "assistant"
                            if 'tool_calls' in inp['additional_kwargs']:
                                message_temp['content'] = {
                                    "toolUse": {
                                        "toolUseId": inp['additional_kwargs']['tool_calls'][0]['id'],
                                        "name": inp['additional_kwargs']['tool_calls'][0]['function']['name'],
                                        "input": json.loads(inp['additional_kwargs']['tool_calls'][0]['function']['arguments'])
                                    }
                                }
                                obs_result['messages'].append(message_temp)
                                print("\t\t\tMessage temp:", message_temp)
                                current_tool_id = inp['additional_kwargs']['tool_calls'][0]['id']
                            else:
                                tool_result = json.loads(inp['content'])[0]
                                if tool_result['type'] == "text":
                                    tool_result_content = tool_result['text']
                                else:
                                    tool_result_content = json.loads(tool_result['text'])
                                message_temp['role'] = 'user'
                                message_temp['content'] = {
                                    "toolResult": {
                                        "toolUseId": current_tool_id,
                                        "content": [{tool_result["type"]: tool_result_content}],
                                        "status": "success"
                                    }
                                }
                                obs_result['messages'].append(message_temp)
                                print("\t\t\tMessage temp:", message_temp)
                    else:
                        message_temp['role'] = inp['role']
                        message_temp['content'] = inp['content']
                        obs_result['messages'].append(message_temp)
                        print("\t\t\tMessage temp:", message_temp)
                trace_result['observations'].append(obs_result)
                print("\t\tObs result:", obs_result)
            result["traces"].append(trace_result)
            print("\tTrace result:", trace_result)
        return result

def load_trace_data(session_id):
    """Load trace data using TokenCounter.get_tracing_result()"""
    try:
        # Initialize TokenCounter
        token_counter = TokenCounter(
            model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
            langfuse_public_key=LANGFUSE_PUBLIC_KEY,
            langfuse_secret_key=LANGFUSE_SECRET_KEY,
            langfuse_host=LANGFUSE_HOST
        )
        
        # Get tracing result
        data = token_counter.get_tracing_result(session_id)
        return data
    except Exception as e:
        st.error(f"Lỗi khi lấy dữ liệu trace: {str(e)}")
        return None

def get_last_observation(trace):
    """Lấy observation cuối cùng của trace"""
    if not trace.get('observations'):
        return None
    return trace['observations'][-1]

def format_message_content(content):
    """Format message content for display"""
    if isinstance(content, str):
        return content
    elif isinstance(content, dict):
        if 'toolUse' in content:
            return f"🔧 Tool Call: {content['toolUse']['name']}"
        elif 'toolResult' in content:
            return f"📋 Tool Result: {content['toolResult']['status']}"
    return str(content)

def display_trace_analysis(trace_data):
    """Hiển thị phân tích trace"""
    
    # Header
    st.markdown('<h1 class="main-header">🔍 Trace Analysis Dashboard</h1>', unsafe_allow_html=True)
    
    # Thông tin session
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Session ID", trace_data['session_id'][:8] + "...")
    with col2:
        st.metric("Số Trace", len(trace_data['traces']))
    with col3:
        total_observations = sum(len(trace['observations']) for trace in trace_data['traces'])
        st.metric("Tổng Observations", total_observations)
    
    st.divider()
    
    # Hiển thị từng trace dưới dạng expander
    for i, trace in enumerate(trace_data['traces']):
        last_obs = get_last_observation(trace)
        if not last_obs:
            continue
            
        # Tạo expander cho trace
        with st.expander(f"📊 Trace {i+1}: {trace['trace_id'][:8]}...", expanded=False):
            
            # Hiển thị system prompt
            if last_obs.get('system'):
                st.markdown("#### 🎯 System Prompt:")
                for system_item in last_obs['system']:
                    st.markdown(f"""
                    <div style="background-color: #f0f8ff; border-radius: 8px; padding: 1rem; margin: 0.5rem 0; border-left: 3px solid #0066cc;">
                        <strong>System:</strong><br>
                        <pre style="background-color: #f5f5f5; padding: 0.5rem; border-radius: 4px; overflow-x: auto; white-space: pre-wrap;">
{system_item['text']}
                        </pre>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Tạo tabs cho trace
            tab1, tab2, tab3 = st.tabs(["💬 Messages", "📈 Analytics", "🔧 Tools"])
            
            with tab1:
                # Hiển thị messages
                st.markdown("#### Lịch sử hội thoại:")
                
                for j, message in enumerate(last_obs['messages']):
                    if message['role'] == 'user':
                        st.markdown(f"""
                        <div class="user-message">
                            <strong>👤 User:</strong><br>
                            {format_message_content(message['content'])}
                        </div>
                        """, unsafe_allow_html=True)
                    elif message['role'] == 'assistant':
                        st.markdown(f"""
                        <div class="assistant-message">
                            <strong>🤖 Assistant:</strong><br>
                            {format_message_content(message['content'])}
                        </div>
                        """, unsafe_allow_html=True)
            
            with tab2:
                # Analytics
                col1, col2 = st.columns(2)
                
                with col1:
                    # Thống kê messages
                    user_messages = [m for m in last_obs['messages'] if m['role'] == 'user']
                    assistant_messages = [m for m in last_obs['messages'] if m['role'] == 'assistant']
                    
                    fig = go.Figure(data=[
                        go.Bar(x=['User', 'Assistant'], 
                               y=[len(user_messages), len(assistant_messages)],
                               marker_color=['#4caf50', '#ff9800'])
                    ])
                    fig.update_layout(title="Số lượng messages", height=300)
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # Tool usage
                    tool_calls = [m for m in last_obs['messages'] 
                                if isinstance(m['content'], dict) and 'toolUse' in m['content']]
                    
                    if tool_calls:
                        tool_names = [m['content']['toolUse']['name'] for m in tool_calls]
                        tool_counts = pd.Series(tool_names).value_counts()
                        
                        fig = px.pie(values=tool_counts.values, 
                                   names=tool_counts.index,
                                   title="Tool Usage Distribution")
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Không có tool calls trong trace này")
            
            with tab3:
                # Tool calls và results
                st.markdown("#### Tool Calls và Results:")
                
                for j, message in enumerate(last_obs['messages']):
                    if isinstance(message['content'], dict) and 'toolUse' in message['content']:
                        tool_call = message['content']['toolUse']
                        
                        st.markdown(f"""
                        <div class="tool-call">
                            <strong>🔧 Tool Call {j+1}:</strong><br>
                            <strong>Tool:</strong> {tool_call['name']}<br>
                            <strong>ID:</strong> {tool_call['toolUseId']}<br>
                            <strong>Input:</strong> {json.dumps(tool_call['input'], indent=2, ensure_ascii=False)}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Tìm tool result tương ứng
                        for k, next_message in enumerate(last_obs['messages'][j+1:], j+1):
                            if (isinstance(next_message['content'], dict) and 
                                'toolResult' in next_message['content'] and
                                next_message['content']['toolResult']['toolUseId'] == tool_call['toolUseId']):
                                
                                tool_result = next_message['content']['toolResult']
                                result_content = tool_result['content'][0]['text'] if tool_result['content'] else "No content"
                                
                                st.markdown(f"""
                                <div class="tool-result">
                                    <strong>📋 Tool Result:</strong><br>
                                    <strong>Status:</strong> {tool_result['status']}<br>
                                    <strong>Content:</strong><br>
                                    <pre style="background-color: #f5f5f5; padding: 0.5rem; border-radius: 4px; overflow-x: auto;">
{result_content[:500]}{'...' if len(result_content) > 500 else ''}
                                    </pre>
                                </div>
                                """, unsafe_allow_html=True)
                                break

def main():
    st.sidebar.title("🎯 Trace Analysis")
    
    # Input session ID
    session_id = st.sidebar.text_input(
        "Nhập Session ID:",
        value="cd388252-6004-4fe1-b3eb-4113e0e986a2",
        help="Nhập session ID để phân tích trace"
    )
    
    if st.sidebar.button("🔍 Phân tích", type="primary"):
        if session_id:
            with st.spinner("Đang tải dữ liệu..."):
                trace_data = load_trace_data(session_id)
                
                if trace_data:
                    display_trace_analysis(trace_data)
                else:
                    st.error("Không thể tải dữ liệu trace")
        else:
            st.warning("Vui lòng nhập Session ID")
    
    # Thông tin thêm
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📋 Hướng dẫn")
    st.sidebar.markdown("""
    1. Nhập Session ID vào ô input
    2. Nhấn nút "Phân tích"
    3. Xem kết quả trong các tab:
       - **Messages**: Lịch sử hội thoại
       - **Analytics**: Thống kê và biểu đồ
       - **Tools**: Tool calls và results
    """)
    
    st.sidebar.markdown("### 📊 Metrics")
    st.sidebar.markdown("""
    - **Trace**: Một lần chat hoàn chỉnh
    - **Observation**: Các action của LLM trong một lần invoke
    - **Tool Call**: Lời gọi công cụ
    - **Tool Result**: Kết quả từ công cụ
    """)

if __name__ == "__main__":
    main()
