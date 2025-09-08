import streamlit as st
import json
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import boto3
from botocore.config import Config as BotoConfig
from dotenv import load_dotenv
import os
import time
import random
from collections import deque
import traceback
from langfuse import Langfuse
import json_repair

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

# AWS credentials từ environment hoặc secrets
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID") or st.secrets.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY") or st.secrets.get("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_REGION") or st.secrets.get("AWS_REGION", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST") or st.secrets.get("LANGFUSE_HOST", "")

class TokenCounter:
    def __init__(self, model_id, aws_access_key_id, aws_secret_access_key, region_name,
                 langfuse_public_key, langfuse_secret_key, langfuse_host,
                 max_requests_per_minute: int = 60):
        self.model_id = model_id
        self.client = boto3.client('bedrock-runtime',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
            config=BotoConfig(
                read_timeout=360,
                connect_timeout=10,
                retries={"max_attempts": 3, "mode": "standard"}
            )
        )
        self.langfuse = Langfuse(
            public_key=langfuse_public_key,
            secret_key=langfuse_secret_key,
            host=langfuse_host
        )
        self._rate_limit_window_seconds = 60.0
        self._max_requests_per_minute = max_requests_per_minute
        self._request_timestamps = deque()
        # Delay cố định mỗi request để né rate limit burst (2-3s)
        self._per_request_delay_min_seconds = 0.1
        self._per_request_delay_max_seconds = 1

    def _acquire_rate_limit_slot(self):
        now = time.time()
        # Loại bỏ các request cũ hơn cửa sổ 60s
        while self._request_timestamps and now - self._request_timestamps[0] > self._rate_limit_window_seconds:
            self._request_timestamps.popleft()
        # Nếu đạt ngưỡng, ngủ tới khi đủ chỗ trống
        if len(self._request_timestamps) >= self._max_requests_per_minute:
            sleep_for = self._rate_limit_window_seconds - (now - self._request_timestamps[0]) + 0.01
            if sleep_for > 0:
                time.sleep(sleep_for)
        # Ghi nhận request
        self._request_timestamps.append(time.time())

    def _call_with_retries(self, func, *args, **kwargs):
        delay_seconds = 0.5
        max_attempts = 8
        for attempt in range(max_attempts):
            self._acquire_rate_limit_slot()
            # Thêm delay cố định 2-3s trước mỗi request
            fixed_delay = random.uniform(self._per_request_delay_min_seconds, self._per_request_delay_max_seconds)
            print(f"[RATE] Waiting fixed delay {fixed_delay:.2f}s before calling {getattr(func, '__name__', str(func))}, attempt {attempt+1}/{max_attempts}")
            time.sleep(fixed_delay)
            try:
                print(f"[CALL] -> {getattr(func, '__name__', str(func))} args={str(args)[:120]} kwargs={{{', '.join(list(kwargs)[:3])}}}")
                result = func(*args, **kwargs)
                print(f"[CALL] <- {getattr(func, '__name__', str(func))} OK")
                return result
            except Exception as e:
                message = str(e)
                lower = message.lower()
                is_rate = ('429' in message) or ('rate' in lower) or ('too many requests' in lower)
                is_timeout = ('timed out' in lower) or ('timeout' in lower)
                if is_rate and attempt < max_attempts - 1:
                    sleep_for = delay_seconds + random.uniform(0.0, 0.3)
                    print(f"[RETRY] Rate limited: {message}. Backoff {sleep_for:.2f}s (attempt {attempt+1})")
                    time.sleep(sleep_for)
                    delay_seconds = min(delay_seconds * 2.0, 8.0)
                    continue
                if is_timeout and attempt < max_attempts - 1:
                    sleep_for = delay_seconds + random.uniform(0.2, 0.6)
                    print(f"[RETRY] Timeout: {message}. Backoff {sleep_for:.2f}s (attempt {attempt+1})")
                    time.sleep(sleep_for)
                    delay_seconds = min(delay_seconds * 2.0, 10.0)
                    continue
                raise

    def get_tracing_result(self, session_id):
        result = {"session_id": session_id, "traces": []}

        # Lấy thông tin session
        print(f"Session id: {session_id}")
        print(f"[SESSION] Fetching session {session_id}")
        session = self._call_with_retries(self.langfuse.api.sessions.get, session_id)
        # Parse JSON an toàn: hỗ trợ khi .json() trả về dict hoặc chuỗi rỗng
        try:
            session_raw = session.json() if hasattr(session, "json") else session
            if isinstance(session_raw, (dict, list)):
                session_json = session_raw
            else:
                session_json = json_repair.loads(session_raw or "{}")
        except Exception as e:
            raise ValueError(f"Không parse được session JSON: {e}")

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
            print(f"[TRACE] Fetching trace {trace['id']}")
            try:
                trace = self._call_with_retries(self.langfuse.api.trace.get, trace['id'])
            except Exception as e:
                print(f"[TRACE] Skip trace {trace['id']} due to error: {e}")
                continue
            try:
                trace_raw = trace.json() if hasattr(trace, "json") else trace
                if isinstance(trace_raw, (dict, list)):
                    trace_json = trace_raw
                else:
                    trace_json = json_repair.loads(trace_raw or "{}")
            except Exception as e:
                raise ValueError(f"Không parse được trace JSON: {e}")
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
                                        "input": (
                                            json_repair.loads(inp['additional_kwargs']['tool_calls'][0]['function']['arguments'])
                                            if isinstance(inp['additional_kwargs']['tool_calls'][0]['function']['arguments'], str)
                                            else inp['additional_kwargs']['tool_calls'][0]['function']['arguments']
                                        )
                                    }
                                }
                                obs_result['messages'].append(message_temp)
                                print("\t\t\tMessage temp:", message_temp)
                                current_tool_id = inp['additional_kwargs']['tool_calls'][0]['id']
                            else:
                                # Parse tool result linh hoạt: hỗ trợ string/dict/list và list rỗng
                                try:
                                    content_raw = inp.get('content') if isinstance(inp, dict) else inp
                                    parsed = None
                                    if isinstance(content_raw, str):
                                        # Thử parse JSON; nếu không phải JSON hợp lệ, giữ nguyên string
                                        try:
                                            parsed = json_repair.loads(content_raw)
                                        except Exception:
                                            parsed = content_raw
                                    else:
                                        parsed = content_raw

                                    # Chuẩn hóa thành dict tool_result
                                    tool_result = None
                                    if isinstance(parsed, list):
                                        if len(parsed) > 0:
                                            tool_result = parsed[0]
                                            # Nếu phần tử đầu là chuỗi → bọc thành dict kiểu text
                                            if isinstance(tool_result, str):
                                                tool_result = {"type": "text", "text": tool_result}
                                            # Nếu là dict nhưng thiếu 'type' → mặc định 'text'
                                            elif isinstance(tool_result, dict) and 'type' not in tool_result:
                                                tool_result = {"type": "text", "text": tool_result.get('text', str(tool_result))}
                                        else:
                                            # Không có nội dung → bỏ qua block này
                                            continue
                                    elif isinstance(parsed, dict):
                                        tool_result = parsed
                                    elif isinstance(parsed, str):
                                        # Quấn string thành block kiểu text
                                        tool_result = {"type": "text", "text": parsed}
                                    else:
                                        # Kiểu không hỗ trợ → bỏ qua
                                        continue
                                except Exception as e:
                                    raise ValueError(f"Không parse được tool result content: {e}")

                                # Lấy nội dung hiển thị theo type
                                if tool_result.get('type') == "text":
                                    tool_result_content = tool_result.get('text', '')
                                else:
                                    # Có thể 'text' là JSON string hoặc đã là object; nếu không có 'text', dùng toàn bộ tool_result
                                    tr_text = tool_result.get('text')
                                    if tr_text is None:
                                        tool_result_content = tool_result
                                    else:
                                        try:
                                            tool_result_content = json_repair.loads(tr_text) if isinstance(tr_text, str) else tr_text
                                        except Exception:
                                            tool_result_content = tr_text
                                message_temp['role'] = 'user'
                                message_temp['content'] = {
                                    "toolResult": {
                                        "toolUseId": current_tool_id,
                                        "content": [{tool_result.get("type", "text"): tool_result_content}],
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

    def count_tokens_for_observation(self, observation):
        """Tính số tokens cho một observation"""
        try:
            system = [{"text": ""}]
            messages = []
            
            # Tạo system prompt
            for system_text in observation["system"]:
                system[0]["text"] += f"{system_text['text']}\n"
            
            # Tạo messages
            for message_text in observation["messages"]:
                message_temp = {"role": message_text["role"]}

                if isinstance(message_text["content"], str):
                    message_temp.update({
                        "content": [
                            {"text": message_text["content"]}
                        ]
                    })
                else:
                    message_temp.update({
                        "content": [message_text["content"]]
                    })

                messages.append(message_temp)
            
            # Đếm tokens
            try:
                obs_id = observation['observation_id'] if isinstance(observation, dict) and 'observation_id' in observation else 'unknown'
            except Exception:
                obs_id = 'unknown'
            print(f"[TOKENS] Counting tokens for observation {obs_id}")
            response = self._call_with_retries(
                self.client.count_tokens,
                modelId=self.model_id.replace("us.", ""),
                input={
                    "converse": {
                        "messages": messages,
                        "system": system
                    }
                }
            )
            return response["inputTokens"]
        except Exception as e:
            print(f"Error counting tokens: {e}")
            return 0

def load_trace_data(session_id, langfuse_public_key, langfuse_secret_key, max_traces: int = None, max_obs_per_trace: int = None):
    """Load trace data using TokenCounter.get_tracing_result()"""
    try:
        # Initialize TokenCounter
        token_counter = TokenCounter(
            model_id="anthropic.claude-sonnet-4-20250514-v1:0",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
            langfuse_public_key=langfuse_public_key,
            langfuse_secret_key=langfuse_secret_key,
            langfuse_host=LANGFUSE_HOST
        )
        
        # Get tracing result
        data = token_counter.get_tracing_result(session_id)
        
        # Tính tokens cho mỗi observation
        for t_idx, trace in enumerate(data["traces"]):
            if max_traces is not None and t_idx >= max_traces:
                break
            for o_idx, observation in enumerate(trace["observations"]):
                if max_obs_per_trace is not None and o_idx >= max_obs_per_trace:
                    break
                observation["input_tokens"] = token_counter.count_tokens_for_observation(observation)
        
        return data
    except Exception as e:
        # Hiển thị lỗi rõ ràng hơn trên UI kèm traceback để xác định vị trí lỗi
        st.error(f"Lỗi khi lấy dữ liệu trace: {type(e).__name__}: {str(e)}")
        with st.expander("Chi tiết lỗi (traceback)", expanded=False):
            st.code(traceback.format_exc())
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

def display_trace_analysis(trace_data, session_label=""):
    """Hiển thị phân tích trace"""
    
    # Header
    if session_label:
        st.markdown(f'<h1 class="main-header">🔍 Trace Analysis Dashboard - {session_label}</h1>', unsafe_allow_html=True)
    else:
        st.markdown('<h1 class="main-header">🔍 Trace Analysis Dashboard</h1>', unsafe_allow_html=True)
    
    # Thông tin session
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Session ID", trace_data['session_id'][:8] + "...")
    with col2:
        st.metric("Số Trace", len(trace_data['traces']))
    with col3:
        total_observations = sum(len(trace['observations']) for trace in trace_data['traces'])
        st.metric("Tổng Observations", total_observations)
    with col4:
        total_tokens = sum(
            sum(obs.get('input_tokens', 0) for obs in trace['observations']) 
            for trace in trace_data['traces']
        )
        st.metric("Tổng Input Tokens", f"{total_tokens:,}")
    
    st.divider()
    
    # Biểu đồ tổng quan tokens cho toàn bộ session
    st.markdown("### 📊 Token Usage Overview")
    
    # Chuẩn bị dữ liệu cho biểu đồ
    trace_tokens = []
    trace_labels = []
    for i, trace in enumerate(trace_data['traces']):
        total_trace_tokens = sum(obs.get('input_tokens', 0) for obs in trace['observations'])
        trace_tokens.append(total_trace_tokens)
        trace_labels.append(f"Trace {i+1}")
    
    # Biểu đồ cột tokens theo trace
    col1, col2 = st.columns(2)
    
    with col1:
        fig = go.Figure(data=[
            go.Bar(x=trace_labels, y=trace_tokens, marker_color='lightcoral')
        ])
        fig.update_layout(
            title="Input Tokens per Trace",
            xaxis_title="Trace",
            yaxis_title="Input Tokens",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True, key=f"overview_tokens_{trace_data['session_id']}")
    
    with col2:
        # Thống kê tổng quan
        st.markdown("#### 📊 Thống kê tổng quan:")
        if sum(trace_tokens) > 0:
            col2_1, col2_2 = st.columns(2)
            with col2_1:
                st.metric("Tổng tokens", f"{sum(trace_tokens):,}")
                st.metric("Trung bình/trace", f"{sum(trace_tokens)/len(trace_tokens):.0f}")
            with col2_2:
                st.metric("Cao nhất", f"{max(trace_tokens):,}")
                st.metric("Thấp nhất", f"{min(trace_tokens):,}")
        else:
            st.info("Không có dữ liệu tokens để hiển thị")
    
    st.divider()
    
    # Hiển thị từng trace dưới dạng expander
    for i, trace in enumerate(trace_data['traces']):
        last_obs = get_last_observation(trace)
        if not last_obs:
            continue
            
        # Tạo expander cho trace
        with st.expander(f"📊 Trace {i+1}: {trace['trace_id'][:8]}... (Tokens: {sum(obs.get('input_tokens', 0) for obs in trace['observations']):,})", expanded=False):
            
            # Hiển thị system prompt trong expander
            if last_obs.get('system'):
                with st.expander("🎯 System Prompt", expanded=False):
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
            tab1, tab2, tab3, tab4 = st.tabs(["💬 Messages", "📈 Analytics", "🔧 Tools", "🎯 Tokens"])
            
            with tab1:
                # Hiển thị messages trong expander
                with st.expander("💬 Lịch sử hội thoại", expanded=False):
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
                    st.plotly_chart(fig, use_container_width=True, key=f"msg_count_{trace['trace_id']}")
                
                with col2:
                    # Tool usage summary
                    tool_calls = [m for m in last_obs['messages'] 
                                if isinstance(m['content'], dict) and 'toolUse' in m['content']]
                    
                    if tool_calls:
                        tool_names = [m['content']['toolUse']['name'] for m in tool_calls]
                        tool_counts = pd.Series(tool_names).value_counts()
                        
                        st.markdown("#### 🔧 Tool Usage Summary:")
                        for tool_name, count in tool_counts.items():
                            st.metric(f"{tool_name}", count)
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
            
            with tab4:
                # Token analysis
                st.markdown("#### 🎯 Token Analysis:")
                
                # Hiển thị tokens cho observation cuối cùng
                if last_obs.get('input_tokens'):
                    st.metric("Input Tokens (Last Observation)", f"{last_obs['input_tokens']:,}")
                
                # Hiển thị tokens cho tất cả observations trong trace
                if trace['observations']:
                    obs_tokens = []
                    obs_ids = []
                    for obs in trace['observations']:
                        tokens = obs.get('input_tokens', 0)
                        obs_tokens.append(tokens)
                        obs_ids.append(f"Obs {obs['observation_id'][:8]}...")
                    
                    # Biểu đồ tokens theo observation
                    fig = go.Figure(data=[
                        go.Bar(x=obs_ids, y=obs_tokens, marker_color='lightblue')
                    ])
                    fig.update_layout(
                        title="Input Tokens per Observation",
                        xaxis_title="Observation",
                        yaxis_title="Input Tokens",
                        height=400
                    )
                    st.plotly_chart(fig, use_container_width=True, key=f"obs_tokens_{trace['trace_id']}")
                    
                    # Thống kê tokens
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Tổng Tokens", f"{sum(obs_tokens):,}")
                    with col2:
                        st.metric("Trung bình", f"{sum(obs_tokens)/len(obs_tokens):.0f}")
                    with col3:
                        st.metric("Cao nhất", f"{max(obs_tokens):,}")

def display_comparison(session1_data, session2_data, session1_label, session2_label):
    """Hiển thị so sánh giữa 2 session"""
    
    st.markdown('<h1 class="main-header">🔄 Session Comparison</h1>', unsafe_allow_html=True)
    
    # Thống kê tổng quan so sánh
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"### 📊 {session1_label}")
        total_tokens_1 = sum(
            sum(obs.get('input_tokens', 0) for obs in trace['observations']) 
            for trace in session1_data['traces']
        )
        st.metric("Tổng Tokens", f"{total_tokens_1:,}")
        st.metric("Số Trace", len(session1_data['traces']))
        st.metric("Tổng Observations", sum(len(trace['observations']) for trace in session1_data['traces']))
    
    with col2:
        st.markdown(f"### 📊 {session2_label}")
        total_tokens_2 = sum(
            sum(obs.get('input_tokens', 0) for obs in trace['observations']) 
            for trace in session2_data['traces']
        )
        st.metric("Tổng Tokens", f"{total_tokens_2:,}")
        st.metric("Số Trace", len(session2_data['traces']))
        st.metric("Tổng Observations", sum(len(trace['observations']) for trace in session2_data['traces']))
    
    # So sánh tokens
    st.divider()
    st.markdown("### 📈 Token Comparison")
    
    # Chuẩn bị dữ liệu cho biểu đồ so sánh
    trace_tokens_1 = []
    trace_tokens_2 = []
    max_traces = max(len(session1_data['traces']), len(session2_data['traces']))
    
    for i in range(max_traces):
        if i < len(session1_data['traces']):
            total_trace_tokens_1 = sum(obs.get('input_tokens', 0) for obs in session1_data['traces'][i]['observations'])
            trace_tokens_1.append(total_trace_tokens_1)
        else:
            trace_tokens_1.append(0)
            
        if i < len(session2_data['traces']):
            total_trace_tokens_2 = sum(obs.get('input_tokens', 0) for obs in session2_data['traces'][i]['observations'])
            trace_tokens_2.append(total_trace_tokens_2)
        else:
            trace_tokens_2.append(0)
    
    # Biểu đồ so sánh
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name=session1_label,
        x=[f"Trace {i+1}" for i in range(max_traces)],
        y=trace_tokens_1,
        marker_color='lightcoral'
    ))
    fig.add_trace(go.Bar(
        name=session2_label,
        x=[f"Trace {i+1}" for i in range(max_traces)],
        y=trace_tokens_2,
        marker_color='lightblue'
    ))
    
    fig.update_layout(
        title="Token Usage Comparison",
        xaxis_title="Trace",
        yaxis_title="Input Tokens",
        barmode='group',
        height=500
    )
    st.plotly_chart(fig, use_container_width=True, key=f"comparison_{session1_data['session_id']}_{session2_data['session_id']}")
    
    # Thống kê so sánh
    col1, col2, col3 = st.columns(3)
    with col1:
        diff_tokens = total_tokens_2 - total_tokens_1
        diff_percent = (diff_tokens / total_tokens_1 * 100) if total_tokens_1 > 0 else 0
        st.metric("Chênh lệch Tokens", f"{diff_tokens:+,}", f"{diff_percent:+.1f}%")
    with col2:
        avg_tokens_1 = total_tokens_1 / len(session1_data['traces']) if session1_data['traces'] else 0
        avg_tokens_2 = total_tokens_2 / len(session2_data['traces']) if session2_data['traces'] else 0
        diff_avg = avg_tokens_2 - avg_tokens_1
        st.metric("Chênh lệch TB/Trace", f"{diff_avg:+.0f}")
    with col3:
        max_tokens_1 = max(trace_tokens_1) if trace_tokens_1 else 0
        max_tokens_2 = max(trace_tokens_2) if trace_tokens_2 else 0
        diff_max = max_tokens_2 - max_tokens_1
        st.metric("Chênh lệch Max", f"{diff_max:+,}")

def main():
    st.sidebar.title("🎯 Trace Analysis")
    
    # Langfuse credentials input
    st.sidebar.markdown("### 🔑 Langfuse Credentials")
    langfuse_public_key = st.sidebar.text_input(
        "Langfuse Public Key:",
        type="default",
        help="Nhập Langfuse Public Key"
    )
    langfuse_secret_key = st.sidebar.text_input(
        "Langfuse Secret Key:",
        type="password",
        help="Nhập Langfuse Secret Key"
    )
    
    # Chọn mode
    mode = st.sidebar.selectbox(
        "Chọn chế độ:",
        ["Phân tích đơn", "So sánh 2 session"],
        help="Phân tích một session hoặc so sánh 2 session"
    )

    # Tuỳ chọn giảm tải để né rate limit
    st.sidebar.markdown("### ⚙️ Giới hạn tải")
    max_traces = st.sidebar.number_input("Số trace tối đa", min_value=1, max_value=200, value=20, step=1,
        help="Giới hạn số trace lấy về mỗi session để né rate limit")
    max_obs_per_trace = st.sidebar.number_input("Số observation tối đa/trace", min_value=1, max_value=200, value=10, step=1,
        help="Giới hạn số observation xử lý mỗi trace để né rate limit")
    
    if mode == "Phân tích đơn":
        # Input session ID
        session_id = st.sidebar.text_input(
            "Nhập Session ID:",
            value="cd388252-6004-4fe1-b3eb-4113e0e986a2",
            help="Nhập session ID để phân tích trace"
        )
        
        if st.sidebar.button("🔍 Phân tích", type="primary"):
            if session_id and langfuse_public_key and langfuse_secret_key:
                with st.spinner("Đang tải dữ liệu..."):
                    trace_data = load_trace_data(session_id, langfuse_public_key, langfuse_secret_key, max_traces=int(max_traces), max_obs_per_trace=int(max_obs_per_trace))
                    
                    if trace_data:
                        display_trace_analysis(trace_data)
                    else:
                        st.error("Không thể tải dữ liệu trace")
            elif not session_id:
                st.warning("Vui lòng nhập Session ID")
            elif not langfuse_public_key or not langfuse_secret_key:
                st.warning("Vui lòng nhập Langfuse credentials")
    
    else:  # So sánh 2 session
        col1, col2 = st.columns(2)
        
        with col1:
            session1_id = st.text_input(
                "Session 1 ID:",
                value="cd388252-6004-4fe1-b3eb-4113e0e986a2",
                help="Session ID đầu tiên (ví dụ: không có summary)"
            )
            session1_label = st.text_input(
                "Nhãn Session 1:",
                value="Không bật Summary",
                help="Nhãn để hiển thị cho session 1"
            )
        
        with col2:
            session2_id = st.text_input(
                "Session 2 ID:",
                value="",
                help="Session ID thứ hai (ví dụ: có summary)"
            )
            session2_label = st.text_input(
                "Nhãn Session 2:",
                value="Bật summary",
                help="Nhãn để hiển thị cho session 2"
            )
        
        if st.button("🔄 So sánh", type="primary"):
            if session1_id and session2_id and langfuse_public_key and langfuse_secret_key:
                with st.spinner("Đang tải dữ liệu..."):
                    session1_data = load_trace_data(session1_id, langfuse_public_key, langfuse_secret_key, max_traces=int(max_traces), max_obs_per_trace=int(max_obs_per_trace))
                    session2_data = load_trace_data(session2_id, langfuse_public_key, langfuse_secret_key, max_traces=int(max_traces), max_obs_per_trace=int(max_obs_per_trace))
                    
                    if session1_data and session2_data:
                        display_comparison(session1_data, session2_data, session1_label, session2_label)
                        
                        # Hiển thị chi tiết từng session
                        st.divider()
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            display_trace_analysis(session1_data, session1_label)
                        
                        with col2:
                            display_trace_analysis(session2_data, session2_label)
                    else:
                        st.error("Không thể tải dữ liệu từ một hoặc cả hai session")
            elif not session1_id or not session2_id:
                st.warning("Vui lòng nhập cả hai Session ID")
            elif not langfuse_public_key or not langfuse_secret_key:
                st.warning("Vui lòng nhập Langfuse credentials")
    
    # Thông tin thêm
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📋 Hướng dẫn")
    st.sidebar.markdown("""
    **Phân tích đơn:**
    1. Nhập Session ID
    2. Nhấn "Phân tích"
    
    **So sánh 2 session:**
    1. Nhập 2 Session ID
    2. Đặt nhãn cho từng session
    3. Nhấn "So sánh"
    """)
    
    st.sidebar.markdown("### 📊 Metrics")
    st.sidebar.markdown("""
    - **Trace**: Một lần chat hoàn chỉnh
    - **Observation**: Các action của LLM
    - **Tool Call**: Lời gọi công cụ
    - **Tool Result**: Kết quả từ công cụ
    - **Tokens**: Số lượng input tokens
    """)

if __name__ == "__main__":
    main()
