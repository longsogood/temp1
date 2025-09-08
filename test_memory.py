import boto3
from dotenv import load_dotenv
import os
import json
import json_repair
from langfuse import Langfuse
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from datetime import datetime
import numpy as np
load_dotenv(".env")

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY= os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")

LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST")

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
        # Set style for better looking plots
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")

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
    
    def count_tokens(self, result):
        token_usage = {"session_id": result["session_id"],
                       "detail": []}
        for trace in result["traces"]:
            trace_tokens = {
                "trace_id": trace["trace_id"],
                "token_usage": 0
            }
            for observation in trace['observations']:
                system = [{"text": ""}]
                messages = []
                for system_text in observation["system"]:
                    system[0]["text"] += f"{system_text['text']}\n"
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
                    
                    # print({
                    #     "role": message_text["role"],
                    #     "content": [
                    #         {"text": message_text["content"]}
                    #     ]
                #     # })
                # print(system)
                # print(messages)
                # print("Messages:", json.dumps(messages, indent=4, ensure_ascii=False))
                # print("="*100)
                response = self.client.count_tokens(
                    modelId=self.model_id,
                    input={
                        "converse": {
                            "messages": messages,
                            "system": system
                        }
                    }
                )
            trace_tokens["token_usage"] += response["inputTokens"]
            token_usage["detail"].append(trace_tokens)
        return token_usage

    def visualize_token_usage(self, result, save_path=None, show_plot=True):
        """
        Tạo biểu đồ visualize token usage cho một phiên chat
        
        Args:
            result: Kết quả từ get_tracing_result
            save_path: Đường dẫn để lưu ảnh (optional)
            show_plot: Có hiển thị plot không (default: True)
        """
        # Chuẩn bị dữ liệu cho visualization
        trace_data = []
        observation_data = []
        
        for trace in result["traces"]:
            trace_id = trace["trace_id"]
            total_trace_tokens = 0
            
            for obs in trace['observations']:
                obs_id = obs['observation_id']
                
                # Tính token cho observation này
                system = [{"text": ""}]
                messages = []
                
                for system_text in obs["system"]:
                    system[0]["text"] += f"{system_text['text']}\n"
                    
                for message_text in obs["messages"]:
                    message_temp = {"role": message_text["role"]}
                    
                    if isinstance(message_text["content"], str):
                        message_temp.update({
                            "content": [{"text": message_text["content"]}]
                        })
                    else:
                        message_temp.update({
                            "content": [message_text["content"]]
                        })
                    messages.append(message_temp)
                
                # Đếm token
                try:
                    response = self.client.count_tokens(
                        modelId=self.model_id,
                        input={
                            "converse": {
                                "messages": messages,
                                "system": system
                            }
                        }
                    )
                    obs_tokens = response["inputTokens"]
                    total_trace_tokens += obs_tokens
                    
                    observation_data.append({
                        'trace_id': trace_id,
                        'observation_id': obs_id,
                        'tokens': obs_tokens,
                        'message_count': len(messages),
                        'system_length': len(system[0]["text"])
                    })
                    
                except Exception as e:
                    print(f"Error counting tokens for observation {obs_id}: {e}")
                    obs_tokens = 0
                    total_trace_tokens += obs_tokens
            
            trace_data.append({
                'trace_id': trace_id,
                'total_tokens': total_trace_tokens,
                'observation_count': len(trace['observations'])
            })
        
        # Tạo DataFrame
        trace_df = pd.DataFrame(trace_data)
        obs_df = pd.DataFrame(observation_data)
        
        # Tạo subplots
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle(f'Token Usage Analysis - Session: {result["session_id"][:8]}...', 
                    fontsize=16, fontweight='bold')
        
        # 1. Bar chart - Token usage per trace
        if not trace_df.empty:
            ax1.bar(range(len(trace_df)), trace_df['total_tokens'], 
                   color=sns.color_palette("husl", len(trace_df)))
            ax1.set_title('Token Usage per Trace', fontweight='bold')
            ax1.set_xlabel('Trace Index')
            ax1.set_ylabel('Total Tokens')
            ax1.set_xticks(range(len(trace_df)))
            ax1.set_xticklabels([f"Trace {i+1}" for i in range(len(trace_df))])
            
            # Thêm giá trị trên mỗi bar
            for i, v in enumerate(trace_df['total_tokens']):
                ax1.text(i, v + max(trace_df['total_tokens']) * 0.01, 
                        str(v), ha='center', va='bottom', fontweight='bold')
        
        # 2. Pie chart - Distribution of tokens across traces
        if not trace_df.empty:
            ax2.pie(trace_df['total_tokens'], labels=[f"Trace {i+1}" for i in range(len(trace_df))], 
                   autopct='%1.1f%%', startangle=90)
            ax2.set_title('Token Distribution Across Traces', fontweight='bold')
        
        # 3. Line chart - Token usage per observation
        if not obs_df.empty:
            obs_df_sorted = obs_df.sort_values('trace_id')
            ax3.plot(range(len(obs_df_sorted)), obs_df_sorted['tokens'], 
                    marker='o', linewidth=2, markersize=6)
            ax3.set_title('Token Usage per Observation', fontweight='bold')
            ax3.set_xlabel('Observation Index')
            ax3.set_ylabel('Tokens')
            ax3.grid(True, alpha=0.3)
            
            # Thêm giá trị trên mỗi điểm
            for i, v in enumerate(obs_df_sorted['tokens']):
                ax3.text(i, v + max(obs_df_sorted['tokens']) * 0.02, 
                        str(v), ha='center', va='bottom', fontsize=8)
        
        # 4. Scatter plot - Message count vs Tokens
        if not obs_df.empty:
            ax4.scatter(obs_df['message_count'], obs_df['tokens'], 
                       s=100, alpha=0.7, c=obs_df['tokens'], cmap='viridis')
            ax4.set_title('Message Count vs Token Usage', fontweight='bold')
            ax4.set_xlabel('Number of Messages')
            ax4.set_ylabel('Tokens')
            ax4.grid(True, alpha=0.3)
            
            # Thêm trend line
            if len(obs_df) > 1:
                z = np.polyfit(obs_df['message_count'], obs_df['tokens'], 1)
                p = np.poly1d(z)
                ax4.plot(obs_df['message_count'], p(obs_df['message_count']), 
                        "r--", alpha=0.8, linewidth=2)
        
        plt.tight_layout()
        
        # Lưu ảnh nếu có đường dẫn
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Chart saved to: {save_path}")
        
        # Hiển thị plot
        if show_plot:
            plt.show()
        
        return fig, trace_df, obs_df
    
    def create_summary_chart(self, result, save_path=None, show_plot=True):
        """
        Tạo biểu đồ tóm tắt đơn giản cho token usage
        
        Args:
            result: Kết quả từ get_tracing_result
            save_path: Đường dẫn để lưu ảnh (optional)
            show_plot: Có hiển thị plot không (default: True)
        """
        # Tính tổng token usage
        total_tokens = 0
        trace_counts = []
        
        for trace in result["traces"]:
            trace_tokens = 0
            for obs in trace['observations']:
                system = [{"text": ""}]
                messages = []
                
                for system_text in obs["system"]:
                    system[0]["text"] += f"{system_text['text']}\n"
                    
                for message_text in obs["messages"]:
                    message_temp = {"role": message_text["role"]}
                    
                    if isinstance(message_text["content"], str):
                        message_temp.update({
                            "content": [{"text": message_text["content"]}]
                        })
                    else:
                        message_temp.update({
                            "content": [message_text["content"]]
                        })
                    messages.append(message_temp)
                
                try:
                    response = self.client.count_tokens(
                        modelId=self.model_id,
                        input={
                            "converse": {
                                "messages": messages,
                                "system": system
                            }
                        }
                    )
                    trace_tokens += response["inputTokens"]
                except Exception as e:
                    print(f"Error counting tokens: {e}")
            
            total_tokens += trace_tokens
            trace_counts.append(trace_tokens)
        
        # Tạo biểu đồ đơn giản
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
        fig.suptitle(f'Token Usage Summary - Session: {result["session_id"][:8]}...', 
                    fontsize=14, fontweight='bold')
        
        # 1. Tổng token usage
        ax1.bar(['Total Tokens'], [total_tokens], color='skyblue', alpha=0.7)
        ax1.set_title('Total Token Usage', fontweight='bold')
        ax1.set_ylabel('Tokens')
        ax1.text(0, total_tokens + max(trace_counts) * 0.01, 
                str(total_tokens), ha='center', va='bottom', fontweight='bold')
        
        # 2. Token per trace
        if trace_counts:
            ax2.bar(range(len(trace_counts)), trace_counts, color='lightcoral', alpha=0.7)
            ax2.set_title('Tokens per Trace', fontweight='bold')
            ax2.set_xlabel('Trace Index')
            ax2.set_ylabel('Tokens')
            ax2.set_xticks(range(len(trace_counts)))
            ax2.set_xticklabels([f"Trace {i+1}" for i in range(len(trace_counts))])
            
            # Thêm giá trị trên mỗi bar
            for i, v in enumerate(trace_counts):
                ax2.text(i, v + max(trace_counts) * 0.01, 
                        str(v), ha='center', va='bottom', fontweight='bold')
        
        plt.tight_layout()
        
        # Lưu ảnh nếu có đường dẫn
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Summary chart saved to: {save_path}")
        
        # Hiển thị plot
        if show_plot:
            plt.show()
        
        return fig, total_tokens, trace_counts

    # def create_message(self, role, text, image: None, document: None, toolUse: None, toolResult: None, ):


token_counter = TokenCounter(model_id="anthropic.claude-sonnet-4-20250514-v1:0",
                             aws_access_key_id=AWS_ACCESS_KEY_ID,
                             aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                             region_name=AWS_REGION,
                             langfuse_public_key=LANGFUSE_PUBLIC_KEY,
                             langfuse_secret_key=LANGFUSE_SECRET_KEY,
                             langfuse_host=LANGFUSE_HOST)

result = token_counter.get_tracing_result("cd388252-6004-4fe1-b3eb-4113e0e986a2")
token_usage = token_counter.count_tokens(result)
print(f"Token usage: {json.dumps(token_usage, indent=4, ensure_ascii=False)}")

# Visualize token usage
token_counter.visualize_token_usage(result, save_path="token_usage_analysis.png")

# Create summary chart
token_counter.create_summary_chart(result, save_path="token_usage_summary.png")