import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import json

# Set style for better looking plots
plt.style.use('default')
sns.set_palette("husl")

def demo_visualization():
    """
    Demo các phương thức visualization với dữ liệu mẫu
    """
    
    # Dữ liệu mẫu để test
    sample_result = {
        "session_id": "demo-session-123",
        "traces": [
            {
                "trace_id": "trace-1",
                "observations": [
                    {"observation_id": "obs-1", "tokens": 150, "messages": 3},
                    {"observation_id": "obs-2", "tokens": 200, "messages": 4}
                ]
            },
            {
                "trace_id": "trace-2", 
                "observations": [
                    {"observation_id": "obs-3", "tokens": 180, "messages": 2},
                    {"observation_id": "obs-4", "tokens": 250, "messages": 5}
                ]
            }
        ]
    }
    
    # Tạo dữ liệu cho visualization
    trace_data = []
    observation_data = []
    
    for trace in sample_result["traces"]:
        trace_id = trace["trace_id"]
        total_trace_tokens = sum(obs["tokens"] for obs in trace['observations'])
        
        trace_data.append({
            'trace_id': trace_id,
            'total_tokens': total_trace_tokens,
            'observation_count': len(trace['observations'])
        })
        
        for obs in trace['observations']:
            observation_data.append({
                'trace_id': trace_id,
                'observation_id': obs['observation_id'],
                'tokens': obs['tokens'],
                'message_count': obs['messages'],
                'system_length': 50  # Giá trị mẫu
            })
    
    # Tạo DataFrame
    trace_df = pd.DataFrame(trace_data)
    obs_df = pd.DataFrame(observation_data)
    
    print("Trace Data:")
    print(trace_df)
    print("\nObservation Data:")
    print(obs_df)
    
    # Tạo subplots
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle(f'Token Usage Analysis - Session: {sample_result["session_id"]}', 
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
        scatter = ax4.scatter(obs_df['message_count'], obs_df['tokens'], 
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
        
        # Thêm colorbar
        plt.colorbar(scatter, ax=ax4, label='Token Count')
    
    plt.tight_layout()
    
    # Lưu ảnh
    plt.savefig("demo_token_usage_analysis.png", dpi=300, bbox_inches='tight')
    print("Chart saved to: demo_token_usage_analysis.png")
    
    # Hiển thị plot
    plt.show()
    
    return fig, trace_df, obs_df

def demo_summary_chart():
    """
    Demo tạo biểu đồ tóm tắt
    """
    
    # Dữ liệu mẫu
    sample_result = {
        "session_id": "demo-session-123",
        "traces": [
            {
                "trace_id": "trace-1",
                "observations": [
                    {"observation_id": "obs-1", "tokens": 150},
                    {"observation_id": "obs-2", "tokens": 200}
                ]
            },
            {
                "trace_id": "trace-2", 
                "observations": [
                    {"observation_id": "obs-3", "tokens": 180},
                    {"observation_id": "obs-4", "tokens": 250}
                ]
            }
        ]
    }
    
    # Tính tổng token usage
    total_tokens = 0
    trace_counts = []
    
    for trace in sample_result["traces"]:
        trace_tokens = sum(obs["tokens"] for obs in trace['observations'])
        total_tokens += trace_tokens
        trace_counts.append(trace_tokens)
    
    # Tạo biểu đồ đơn giản
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
    fig.suptitle(f'Token Usage Summary - Session: {sample_result["session_id"]}', 
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
    
    # Lưu ảnh
    plt.savefig("demo_token_usage_summary.png", dpi=300, bbox_inches='tight')
    print("Summary chart saved to: demo_token_usage_summary.png")
    
    # Hiển thị plot
    plt.show()
    
    return fig, total_tokens, trace_counts

if __name__ == "__main__":
    print("Demo visualization methods...")
    
    # Test detailed visualization
    print("\n1. Testing detailed visualization...")
    fig1, trace_df, obs_df = demo_visualization()
    
    # Test summary chart
    print("\n2. Testing summary chart...")
    fig2, total_tokens, trace_counts = demo_summary_chart()
    
    print(f"\nDemo completed!")
    print(f"Total tokens: {total_tokens}")
    print(f"Trace counts: {trace_counts}")
