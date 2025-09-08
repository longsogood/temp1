#!/usr/bin/env python3
"""
Test file để kiểm tra các phương thức visualization của TokenCounter class
"""

import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# Set style
plt.style.use('default')
sns.set_palette("husl")

def test_visualization_methods():
    """
    Test các phương thức visualization
    """
    print("Testing visualization methods...")
    
    # Tạo dữ liệu mẫu
    sample_data = 
    
    # Giả lập token counting (thay vì gọi AWS API)
    def mock_count_tokens(messages, system):
        """Mock function để giả lập việc đếm token"""
        total_chars = sum(len(str(msg.get('content', ''))) for msg in messages)
        total_chars += sum(len(str(sys.get('text', ''))) for sys in system)
        # Giả sử 1 token ≈ 4 ký tự
        return max(1, total_chars // 4)
    
    # Chuẩn bị dữ liệu cho visualization
    trace_data = []
    observation_data = []
    
    for trace in sample_data["traces"]:
        trace_id = trace["trace_id"]
        total_trace_tokens = 0
        
        for obs in trace['observations']:
            obs_id = obs['observation_id']
            
            # Tính token cho observation này
            system = obs["system"]
            messages = obs["messages"]
            
            # Giả lập đếm token
            obs_tokens = mock_count_tokens(messages, system)
            total_trace_tokens += obs_tokens
            
            observation_data.append({
                'trace_id': trace_id,
                'observation_id': obs_id,
                'tokens': obs_tokens,
                'message_count': len(messages),
                'system_length': sum(len(sys.get('text', '')) for sys in system)
            })
        
        trace_data.append({
            'trace_id': trace_id,
            'total_tokens': total_trace_tokens,
            'observation_count': len(trace['observations'])
        })
    
    # Tạo DataFrame
    trace_df = pd.DataFrame(trace_data)
    obs_df = pd.DataFrame(observation_data)
    
    print("Trace Data:")
    print(trace_df)
    print("\nObservation Data:")
    print(obs_df)
    
    # Tạo biểu đồ chi tiết
    print("\nCreating detailed visualization...")
    fig1, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
    fig1.suptitle(f'Token Usage Analysis - Session: {sample_data["session_id"]}', 
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
        
        if len(obs_df) > 1:
            z = np.polyfit(obs_df['message_count'], obs_df['tokens'], 1)
            p = np.poly1d(z)
            ax4.plot(obs_df['message_count'], p(obs_df['message_count']), 
                    "r--", alpha=0.8, linewidth=2)
        
        plt.colorbar(scatter, ax=ax4, label='Token Count')
    
    plt.tight_layout()
    plt.savefig("test_token_usage_analysis.png", dpi=300, bbox_inches='tight')
    print("Detailed chart saved to: test_token_usage_analysis.png")
    
    # Tạo biểu đồ tóm tắt
    print("\nCreating summary chart...")
    fig2, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
    fig2.suptitle(f'Token Usage Summary - Session: {sample_data["session_id"]}', 
                fontsize=14, fontweight='bold')
    
    total_tokens = trace_df['total_tokens'].sum()
    trace_counts = trace_df['total_tokens'].tolist()
    
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
        
        for i, v in enumerate(trace_counts):
            ax2.text(i, v + max(trace_counts) * 0.01, 
                    str(v), ha='center', va='bottom', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig("test_token_usage_summary.png", dpi=300, bbox_inches='tight')
    print("Summary chart saved to: test_token_usage_summary.png")
    
    print(f"\nTest completed!")
    print(f"Total tokens: {total_tokens}")
    print(f"Trace counts: {trace_counts}")
    
    return fig1, fig2, trace_df, obs_df

if __name__ == "__main__":
    test_visualization_methods()
