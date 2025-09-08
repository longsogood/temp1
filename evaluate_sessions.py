import os
import json
import argparse
from collections import defaultdict, deque
from datetime import datetime
import time
import random
from typing import Dict, Any, List, Tuple

import boto3
from botocore.config import Config as BotoConfig
from dotenv import load_dotenv
from langfuse import Langfuse
import json_repair

# Import TokenCounter từ streamlit_demo.py
from streamlit_demo import TokenCounter


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


class BedrockClient:
    """Thin wrapper cho Bedrock Runtime dùng converse API."""

    def __init__(self, model_id: str, aws_access_key_id: str, aws_secret_access_key: str, region_name: str):
        self.model_id = model_id
        self.client = boto3.client(
            "bedrock-runtime",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
            config=BotoConfig(read_timeout=360, connect_timeout=10, retries={"max_attempts": 3, "mode": "standard"}),
        )

    def converse_json(self, system_prompt: str, user_content: str, temperature: float = 0.3, max_tokens: int = 65536) -> str:
        response = self.client.converse(
            modelId=self.model_id,
            system=[{"text": system_prompt}],
            messages=[{"role": "user", "content": [{"text": user_content}]}],
            inferenceConfig={"temperature": temperature, "maxTokens": max_tokens},
        )
        # Claude v4 trả về content[0].text
        outputs = response.get("output", {}).get("message", {}).get("content", [])
        return outputs[0].get("text", "") if outputs else ""


# Sử dụng TokenCounter từ streamlit_demo.py thay vì tạo lại class


def normalize_first_user_message(trace: Dict[str, Any]) -> str:
    for obs in trace.get("observations", []):
        for msg in obs.get("messages", []):
            if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                return msg["content"].strip().lower()
    return ""


def get_last_observation(trace: Dict[str, Any]) -> Dict[str, Any]:
    """Lấy observation cuối cùng của trace - áp dụng từ streamlit_demo.py"""
    if not trace.get('observations'):
        return None
    return trace['observations'][-1]


def extract_turn_summary(trace: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract turn summary - chỉ lấy thông tin cơ bản: messages, tools, input_tokens, system
    Để LLM tự phân tích question từ messages trong prompt
    """
    last_obs = get_last_observation(trace)
    if not last_obs:
        return {
            "messages": [],
            "tools": [],
            "input_tokens": 0,
            "system": []
        }
    
    messages = last_obs.get("messages", [])
    
    # Extract tool calls - logic y hệt streamlit_demo.py
    tools = []
    for j, message in enumerate(messages):
        content = message.get("content", "")
        
        if isinstance(content, dict) and "toolUse" in content:
            tool_call = content["toolUse"]
            
            tool_info = {
                "message_index": j,
                "id": tool_call["toolUseId"],
                "name": tool_call["name"],
                "input": tool_call.get("input"),
                "result": None,
                "result_index": None
            }
            
            # Tìm tool result tương ứng - logic giống streamlit demo (dòng 582-600)
            for k, next_message in enumerate(messages[j+1:], j+1):
                next_content = next_message.get("content")
                if (isinstance(next_content, dict) and
                    "toolResult" in next_content and
                    next_content["toolResult"]["toolUseId"] == tool_call["toolUseId"]):
                    
                    tool_result = next_content["toolResult"]
                    result_content = tool_result['content'][0]['text'] if tool_result['content'] else "No content"
                    tool_info["result"] = result_content
                    tool_info["result_index"] = k
                    break
            
            tools.append(tool_info)
    
    # Tính tokens giống như trong streamlit demo
    input_tokens = last_obs.get("input_tokens", 0)
    
    return {
        "messages": messages,
        "tools": tools,
        "input_tokens": input_tokens,
        "system": last_obs.get("system", [])
    }


def evaluate_sessions_markdown(session_a: str, session_b: str, label_a: str, label_b: str, output_path: str, max_traces: int = 50, max_obs_per_trace: int = 10) -> str:
    """Tạo báo cáo markdown trực tiếp so sánh 2 session - bỏ qua đánh giá JSON"""
    load_dotenv(".env")
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION", "us-east-1")
    langfuse_host = os.getenv("LANGFUSE_HOST", "")
    langfuse_pk = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    langfuse_sk = os.getenv("LANGFUSE_SECRET_KEY", "")
    model_id = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")

    if not (aws_key and aws_secret and aws_region and langfuse_pk and langfuse_sk and langfuse_host):
        raise RuntimeError("Thiếu AWS hoặc Langfuse environment variables (AWS_* và LANGFUSE_*).")

    # Sử dụng TokenCounter từ streamlit_demo.py
    tc = TokenCounter(model_id, aws_key, aws_secret, aws_region, langfuse_pk, langfuse_sk, langfuse_host)

    # Tải 2 session
    print(f"[INFO] Loading session A: {session_a}")
    data_a = tc.get_tracing_result(session_a)
    print(f"[INFO] Loading session B: {session_b}")
    data_b = tc.get_tracing_result(session_b)

    # Tính tokens cho mỗi observation - logic giống hệt streamlit_demo.py (dòng 385-392)
    print(f"[INFO] Calculating tokens for session A...")
    for t_idx, trace in enumerate(data_a["traces"]):
        if max_traces is not None and t_idx >= max_traces:
            break
        for o_idx, observation in enumerate(trace["observations"]):
            if max_obs_per_trace is not None and o_idx >= max_obs_per_trace:
                break
            observation["input_tokens"] = tc.count_tokens_for_observation(observation)
    
    print(f"[INFO] Calculating tokens for session B...")
    for t_idx, trace in enumerate(data_b["traces"]):
        if max_traces is not None and t_idx >= max_traces:
            break
        for o_idx, observation in enumerate(trace["observations"]):
            if max_obs_per_trace is not None and o_idx >= max_obs_per_trace:
                break
            observation["input_tokens"] = tc.count_tokens_for_observation(observation)

    # Chuẩn bị dữ liệu cho báo cáo markdown - tối ưu để tránh duplicate
    report_data = {
        "generated_at": _now_iso(),
        "model_id": model_id,
        "sessionA": {
            "id": session_a,
            "label": label_a,
            "num_traces": len(data_a.get("traces", [])),
            "last_conversation": None,  # Observation cuối cùng của trace cuối
            "trace_actions": []  # Action (tools) cho từng trace
        },
        "sessionB": {
            "id": session_b,
            "label": label_b,
            "num_traces": len(data_b.get("traces", [])),
            "last_conversation": None,  # Observation cuối cùng của trace cuối
            "trace_actions": []  # Action (tools) cho từng trace
        }
    }

    # Thu thập dữ liệu cho session A
    if data_a.get("traces"):
        # Lấy observation cuối cùng của trace cuối
        last_trace_a = data_a["traces"][-1]
        last_obs_a = extract_turn_summary(last_trace_a)
        report_data["sessionA"]["last_conversation"] = {
            "trace_id": last_trace_a.get("trace_id", ""),
            "input_tokens": last_obs_a.get("input_tokens", 0),
            "messages": last_obs_a.get("messages", []),
            "system": last_obs_a.get("system", []),
        }
        
        # Lấy action (tools) cho từng trace với thông tin turn chat
        for i, trace in enumerate(data_a["traces"]):
            trace_summary = extract_turn_summary(trace)
            
            # Lấy question và response từ messages để thể hiện turn chat
            messages = trace_summary.get("messages", [])
            question = ""
            assistant_response = ""
            
            # Tìm question từ user và response từ assistant
            for msg in messages:
                if msg.get("role") == "user" and isinstance(msg.get("content"), str) and not question:
                    question = msg["content"]
                elif msg.get("role") == "assistant" and isinstance(msg.get("content"), str):
                    assistant_response = msg["content"]
            
            report_data["sessionA"]["trace_actions"].append({
                "turn_number": i + 1,
                "trace_id": trace.get("trace_id", ""),
                "input_tokens": trace_summary.get("input_tokens", 0),
                "tools": trace_summary.get("tools", []),
                "question_preview": question[:100] + "..." if len(question) > 100 else question,
                "response_preview": assistant_response[:100] + "..." if len(assistant_response) > 100 else assistant_response,
            })
    
    # Thu thập dữ liệu cho session B
    if data_b.get("traces"):
        # Lấy observation cuối cùng của trace cuối
        last_trace_b = data_b["traces"][-1]
        last_obs_b = extract_turn_summary(last_trace_b)
        report_data["sessionB"]["last_conversation"] = {
            "trace_id": last_trace_b.get("trace_id", ""),
            "input_tokens": last_obs_b.get("input_tokens", 0),
            "messages": last_obs_b.get("messages", []),
            "system": last_obs_b.get("system", []),
        }
        
        # Lấy action (tools) cho từng trace với thông tin turn chat
        for i, trace in enumerate(data_b["traces"]):
            trace_summary = extract_turn_summary(trace)
            
            # Lấy question và response từ messages để thể hiện turn chat
            messages = trace_summary.get("messages", [])
            question = ""
            assistant_response = ""
            
            # Tìm question từ user và response từ assistant
            for msg in messages:
                if msg.get("role") == "user" and isinstance(msg.get("content"), str) and not question:
                    question = msg["content"]
                elif msg.get("role") == "assistant" and isinstance(msg.get("content"), str):
                    assistant_response = msg["content"]
            
            report_data["sessionB"]["trace_actions"].append({
                "turn_number": i + 1,
                "trace_id": trace.get("trace_id", ""),
                "input_tokens": trace_summary.get("input_tokens", 0),
                "tools": trace_summary.get("tools", []),
                "question_preview": question[:100] + "..." if len(question) > 100 else question,
                "response_preview": assistant_response[:100] + "..." if len(assistant_response) > 100 else assistant_response,
            })

    print(f"[INFO] Session A: {len(report_data['sessionA']['trace_actions'])} traces")
    print(f"[INFO] Session B: {len(report_data['sessionB']['trace_actions'])} traces")
    
    # Tạo báo cáo markdown bằng LLM
    print(f"[INFO] Generating markdown report...")
    bedrock = BedrockClient(model_id, aws_key, aws_secret, aws_region)
    markdown_report = generate_markdown_with_llm_direct(report_data, bedrock)

    # Lưu báo cáo
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_report)
        print(f"[INFO] Saved markdown report to {output_path}")

    return markdown_report


def build_markdown(report: Dict[str, Any]) -> str:
    hdr = [
        f"# Đánh giá so sánh hai session",
        "",
        f"- **Model**: `{report.get('model_id', '')}`",
        f"- **Generated at**: `{report.get('generated_at', '')}`",
        f"- **Session A**: `{report.get('sessionA', {}).get('id','')}` ({report.get('sessionA', {}).get('label','')})",
        f"- **Session B**: `{report.get('sessionB', {}).get('id','')}` ({report.get('sessionB', {}).get('label','')})",
        "",
        "## Tổng quan",
        "",
    ]
    summary = report.get("summary", {})
    overview = [
        "| Chỉ số | Giá trị |",
        "|---|---:|",
        f"| Wins A | {summary.get('wins_A', 0)} |",
        f"| Wins B | {summary.get('wins_B', 0)} |",
        f"| Ties | {summary.get('ties', 0)} |",
        f"| Avg score A | {summary.get('avg_score_A', '')} |",
        f"| Avg score B | {summary.get('avg_score_B', '')} |",
        f"| Avg token efficiency A | {summary.get('avg_token_eff_A', '')} |",
        f"| Avg token efficiency B | {summary.get('avg_token_eff_B', '')} |",
        "",
    ]

    details_md: List[str] = ["## Chi tiết từng turn", ""]
    for i, item in enumerate(report.get("details", []), 1):
        turn_key = item.get("turn_key", f"turn_{i}")
        eva = item.get("evaluation", {})
        a = item.get("sessionA", {})
        b = item.get("sessionB", {})
        # Hiển thị tools với cả call và result
        def format_tools(tools):
            if not tools:
                return "(không)"
            tool_list = []
            for t in tools:
                name = t.get('name', '')
                result = t.get('result', '')
                if result and result != "No content":
                    # Truncate result nếu quá dài
                    result_preview = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
                    tool_list.append(f"{name} → {result_preview}")
                else:
                    tool_list.append(name)
            return ", ".join(tool_list)
        
        tools_a = format_tools(a.get("tools", []))
        tools_b = format_tools(b.get("tools", []))

        details_md.extend([
            f"### Turn: `{turn_key}`",
            "",
            "| | Session A | Session B |",
            "|---|---|---|",
            f"| Label | {a.get('label','')} | {b.get('label','')} |",
            f"| Input tokens | {a.get('input_tokens', 0)} | {b.get('input_tokens', 0)} |",
            f"| Tools | {tools_a} | {tools_b} |",
            f"| Score | {eva.get('score_A','')} | {eva.get('score_B','')} |",
            f"| Token efficiency | {eva.get('token_efficiency_A','')} | {eva.get('token_efficiency_B','')} |",
            f"| Winner | \- | **{eva.get('winner','tie')}** |",
            "",
            "<details><summary>Tools A</summary>\n\n",
            "```json",
            json.dumps(a.get("tools", []), ensure_ascii=False, indent=2),
            "```\n\n</details>",
            "",
            "<details><summary>Tools B</summary>\n\n",
            "```json",
            json.dumps(b.get("tools", []), ensure_ascii=False, indent=2),
            "```\n\n</details>",
            "",
            "<details><summary>Messages A</summary>\n\n",
            "```json",
            json.dumps(a.get("messages", []), ensure_ascii=False, indent=2),
            "```\n\n</details>",
            "",
            "<details><summary>Messages B</summary>\n\n",
            "```json",
            json.dumps(b.get("messages", []), ensure_ascii=False, indent=2),
            "```\n\n</details>",
            "",
            "<details><summary>Lý do đánh giá</summary>\n\n",
            "```",
            str(eva.get("reasons", "")),
            "```\n\n</details>",
            "",
        ])

    return "\n".join(hdr + overview + details_md)


EVAL_MARKDOWN_SYSTEM_PROMPT = (
    "Bạn là một giám khảo LLM chuyên nghiệp và thận trọng. "
    "Nhiệm vụ: so sánh chi tiết hai session hội thoại (Session A: history thường; Session B: history + summary), "
    "dựa trên: lịch sử (messages), hệ thống (system), số token đầu vào, và các lần gọi tool (toolUse/toolResult).\n\n"
    "Yêu cầu phản hồi: TRẢ VỀ DUY NHẤT một báo cáo Markdown chi tiết và dài, không kèm lời giải thích ngoài lề. "
    "Không sử dụng link bên ngoài. Phân tích kỹ càng, càng dài càng tốt.\n\n"
    "HƯỚNG DẪN PHÂN TÍCH:\n"
    "- Phân tích toàn bộ session, không cần so sánh từng trace riêng lẻ\n"
    "- Tự phân tích messages để xác định question của user (role='user') và response của assistant (role='assistant')\n"
    "- Phân tích thứ tự messages để hiểu flow hội thoại: user question → tool calls → tool results → assistant response\n"
    "- So sánh tổng thể hiệu quả của Session A vs Session B\n\n"
    "QUAN TRỌNG - Phân tích mạch hội thoại và context:\n"
    "- Đặc biệt chú ý cách Session B sử dụng summary (trong system prompt) để duy trì ngữ cảnh\n"
    "- So sánh hiệu quả của việc sử dụng full history (A) vs summary (B) trong việc duy trì ngữ cảnh\n"
    "- Đánh giá tính nhất quán và liên kết giữa các trace trong cả hai session\n"
    "- Phân tích cách thông tin từ system prompt được sử dụng\n\n"
    "QUAN TRỌNG: Tất cả nhận xét, đánh giá, phân tích phải có dẫn chứng cụ thể từ dữ liệu thực tế:\n"
    "- Trích dẫn chính xác nội dung từ messages (user question, assistant response)\n"
    "- Trích dẫn tool calls và tool results từ messages\n"
    "- Nêu rõ số token, tên tool cụ thể\n"
    "- So sánh trực tiếp giữa A và B với ví dụ cụ thể từ messages\n"
    "- Không được đưa ra nhận xét chung chung không có căn cứ\n"
    "- Mỗi kết luận phải kèm theo bằng chứng từ dữ liệu đầu vào\n"
    "- Đặc biệt phân tích cách summary trong system prompt giúp tối ưu hóa context và giảm token\n\n"
    "SÀNG LỌC TURN BẤT THƯỜNG (chỉ phân tích chi tiết những turn này):\n"
    "1. **Chênh lệch token lớn**: ≥50% hoặc ≥500 tokens giữa A và B\n"
    "2. **Tool usage khác biệt**:\n"
    "   - Số lượng tool calls khác nhau (A gọi 3 tools, B gọi 1 tool)\n"
    "   - Loại tools khác nhau (A dùng search, B dùng calculator)\n"
    "   - Thứ tự gọi tools khác nhau\n"
    "   - Một bên có lỗi tool, bên kia thành công\n"
    "3. **Chất lượng response khác biệt rõ rệt**:\n"
    "   - Độ dài câu trả lời chênh lệch lớn (>2x)\n"
    "   - Nội dung hoàn toàn khác nhau cho cùng câu hỏi\n"
    "   - Một bên trả lời đúng, bên kia sai\n"
    "4. **Context/Summary usage khác biệt**:\n"
    "   - B sử dụng summary hiệu quả hơn A\n"
    "   - A bị giới hạn bởi history dài, B không\n"
    "   - Cách tham chiếu thông tin trước đó khác nhau\n"
    "5. **Edge cases và phức tạp**:\n"
    "   - Câu hỏi đa bước, phức tạp\n"
    "   - Yêu cầu tham chiếu nhiều thông tin trước\n"
    "   - Xử lý lỗi hoặc tình huống bất thường\n\n"
    "PHÂN TÍCH ACTION (tại sao có action như vậy):\n"
    "- **Tool selection**: Tại sao chọn tool này thay vì tool khác?\n"
    "- **Tool sequence**: Tại sao gọi tools theo thứ tự này?\n"
    "- **Input parameters**: Tại sao sử dụng parameters này?\n"
    "- **Context influence**: Summary/history ảnh hưởng như thế nào đến quyết định?\n"
    "- **Error handling**: Xử lý lỗi tool như thế nào?\n\n"
    "Tiêu chí chấm:\n"
    "- Chất lượng trả lời: đúng, đầy đủ, trực tiếp, mạch lạc, đúng ngôn ngữ người dùng, có tính thực tiễn.\n"
    "- Sử dụng công cụ: hợp lý, đúng mục đích, tạo giá trị, tránh gọi thừa, xử lý lỗi tốt.\n"
    "- Hiệu quả token: ít token đầu vào hơn với chất lượng tương đương hoặc cao hơn thì điểm cao hơn.\n"
    "- Mạch hội thoại: nhất quán ngữ cảnh, sử dụng history/summary hợp lý, không mâu thuẫn, có tính liên kết.\n"
    "- Khả năng thích ứng: xử lý câu hỏi phức tạp, đa dạng, và edge cases.\n\n"
    "Định dạng báo cáo Markdown (bắt buộc, giữ đúng thứ tự và heading):\n\n"
    "# Báo cáo đánh giá so sánh hai phương pháp memory\n"
    "- **Model**: <model_id>\n"
    "- **Generated at**: <iso_datetime>\n"
    "- **Session A**: <label_a> (ID: <id_a>)\n"
    "- **Session B**: <label_b> (ID: <id_b>)\n\n"
    "## Tóm tắt điều hành\n"
    "- **Kết luận chính**: <A thắng/B thắng/Hòa> - <lý do ngắn gọn với dẫn chứng cụ thể>\n"
    "Bảng so sánh điểm mạnh điểm yếu của A và B cho từng tiêu chí"
    "## Phân tích từng turn\n"
    "### Các turn bình thường\n"
    "| Turn | A tokens | B tokens | A tools | B tools | Winner | Ghi chú |\n"
    "|---|---:|---:|---|---|---|---|\n"
    "| <turn_key> | <int> | <int> | <tool_list> | <tool_list> | <1-2 câu tóm tắt> |\n"
    "| <turn_key> | <int> | <int> | <tool_list> | <tool_list> | <1-2 câu tóm tắt> |\n"
    "| <turn_key> | <int> | <int> | <tool_list> | <tool_list> | <1-2 câu tóm tắt> |\n\n"
    "### Các turn bất thường (phân tích chi tiết)\n"
    "#### Turn: `<turn_key>` - <Lý do bất thường>\n"
    "##### Thông tin cơ bản\n"
    "| | A | B |\n"
    "|---|---|---|\n"
    "| Input tokens | <int> | <int> |\n"
    "| Tool calls | <liệt kê chi tiết tên tool và mục đích> | <liệt kê chi tiết tên tool và mục đích> |\n"
    "##### Phân tích câu trả lời\n"
    "**A:**\n"
    "- <Phân tích chi tiết chất lượng câu trả lời với trích dẫn cụ thể: \"...\" (từ message role=assistant)>\n"
    "- <Đánh giá cách sử dụng context và history với ví dụ cụ thể từ system prompt>\n"
    "- <Nhận xét về ngôn ngữ và phong cách với trích dẫn cụ thể>\n\n"
    "**B:**\n"
    "- <Phân tích chi tiết chất lượng câu trả lời với trích dẫn cụ thể: \"...\" (từ message role=assistant)>\n"
    "- <Đánh giá cách sử dụng context và summary với ví dụ cụ thể từ system prompt>\n"
    "- <Nhận xét về ngôn ngữ và phong cách với trích dẫn cụ thể>\n\n"
    "##### So sánh sử dụng công cụ\n"
    "**A:**\n"
    "- <Phân tích chi tiết từng tool call với trích dẫn: tool \"<tên>\" với input \"<input>\" (từ toolUse)>\n"
    "- <Đánh giá tính hợp lý và cần thiết với ví dụ cụ thể từ tool result>\n"
    "- <Nhận xét về xử lý kết quả tool với trích dẫn: \"...\" (từ toolResult)>\n\n"
    "**B:**\n"
    "- <Phân tích chi tiết từng tool call với trích dẫn: tool \"<tên>\" với input \"<input>\" (từ toolUse)>\n"
    "- <Đánh giá tính hợp lý và cần thiết với ví dụ cụ thể từ tool result>\n"
    "- <Nhận xét về xử lý kết quả tool với trích dẫn: \"...\" (từ toolResult)>\n\n"
    "##### Phân tích hiệu quả token\n"
    "- <So sánh chi tiết số token: A sử dụng <X> tokens, B sử dụng <Y> tokens (chênh lệch <Z> tokens)>\n"
    "- <Đánh giá tỷ lệ chất lượng/token với ví dụ cụ thể từ câu trả lời>\n"
    "- <Nhận xét về tối ưu hóa context với dẫn chứng từ system prompt>\n\n"
    "##### Kết luận turn\n"
    "- <Tổng kết điểm mạnh/yếu của từng session với dẫn chứng cụ thể>\n"
    "- <Lý do A thắng/B thắng/Hòa với bằng chứng từ so sánh trên>\n"
    "- <Bài học rút ra với ví dụ cụ thể từ turn này>\n\n"
    "#### Turn: `<turn_key>` - <Lý do bất thường>\n"
    "<Lặp lại cấu trúc tương tự cho turn bất thường khác>\n\n"
    "**Lưu ý:**\n"
    "   - Đảm bảo liệt kê đầy đủ turn chat"
    "   - Các turn bất thường là các turn có cách gọi tool khác hẳn so với session kia, hoặc so với yêu cầu của người dùng, cũng như số lượng tool calls bất thường"
    "## Phân tích sâu về patterns sử dụng công cụ\n"
    "### Pattern Analysis - Session A\n"
    "**Tool Selection Patterns:**\n"
    "- <Phân tích xu hướng chọn tools: \"A thường chọn tool X trước tool Y trong <số> turns\">\n"
    "- <Lý do behind selection: \"Do history dài nên A cần search nhiều hơn\">\n"
    "- <Ví dụ cụ thể: \"Turn 3: A gọi search_memory → read_file → search_memory (redundant)\">\n\n"
    "**Tool Sequence Patterns:**\n"
    "- <Phân tích thứ tự gọi tools và tại sao: \"A luôn search trước khi read (pattern tốt)\">\n"
    "- <Inefficiencies: \"Turn 5: A gọi lại tool đã gọi ở turn 2 (không nhớ kết quả)\">\n\n"
    "**Context Influence:**\n"
    "- <Cách history ảnh hưởng: \"History dài khiến A gọi thêm search để tìm lại thông tin\">\n"
    "- <Ví dụ: \"Turn 7: A search 'previous calculation' vì không nhớ kết quả turn 3\">\n\n"
    "### Pattern Analysis - Session B\n"
    "**Tool Selection Patterns:**\n"
    "- <Phân tích xu hướng chọn tools với summary: \"B chọn tools chính xác hơn nhờ summary\">\n"
    "- <Efficiency gains: \"B ít gọi redundant tools hơn A\">\n"
    "- <Ví dụ: \"Turn 3: B đi thẳng read_file vì summary đã có path\">\n\n"
    "**Tool Sequence Patterns:**\n"
    "- <Optimization: \"B skip search steps nhờ summary context\">\n"
    "- <Smart decisions: \"Turn 5: B không gọi lại tool vì summary có kết quả\">\n\n"
    "**Summary Influence:**\n"
    "- <Cách summary giúp: \"Summary giúp B nhớ kết quả tools trước đó\">\n"
    "- <Ví dụ: \"Turn 7: B dùng kết quả từ summary thay vì gọi lại tool\">\n\n"
    "### So sánh Patterns\n"
    "**Tool Efficiency:**\n"
    "- <Số liệu: \"A trung bình <X> tools/turn, B trung bình <Y> tools/turn\">\n"
    "- <Redundancy: \"A có <X>% redundant calls, B có <Y>%\">\n"
    "- <Success rate: \"A <X>% tool success, B <Y>% tool success\">\n\n"
    "**Decision Quality:**\n"
    "- <Context usage: \"B sử dụng context tốt hơn A trong <X>/<Y> turns\">\n"
    "- <Tool selection: \"B chọn đúng tool ngay lần đầu trong <X>% cases vs A <Y>%\">\n\n"
    "**Impact on Results:**\n"
    "- <Quality: \"Better tool usage dẫn đến B trả lời chính xác hơn A\">\n"
    "- <Efficiency: \"B tiết kiệm <X> tokens/turn nhờ ít gọi redundant tools\">\n\n"
    "## Phân tích sâu về hiệu quả token\n"
    "### Phân tích định lượng\n"
    "- <Thống kê chi tiết token usage: A tổng <X> tokens, B tổng <Y> tokens, chênh lệch <Z> tokens>\n"
    "- <So sánh token/turn, token/tool call với số liệu cụ thể: A trung bình <X> tokens/turn, B trung bình <Y> tokens/turn>\n"
    "- <Phân tích xu hướng qua các turn với biểu đồ số liệu>\n\n"
    "### Phân tích định tính\n"
    "- <Đánh giá chất lượng context được sử dụng với trích dẫn từ system prompt>\n"
    "- <Phân tích tính hiệu quả của summary với ví dụ: \"Summary '...' giúp B giảm <X> tokens so với A\"\n"
    "- <So sánh cách tối ưu hóa input với dẫn chứng cụ thể>\n\n"
    "### Trường hợp điển hình\n"
    "- <Turn có hiệu quả token cao nhất A: turn <X> với <Y> tokens cho <Z> điểm chất lượng>\n"
    "- <Turn có hiệu quả token cao nhất B: turn <X> với <Y> tokens cho <Z> điểm chất lượng>\n"
    "- <Turn có sự chênh lệch lớn nhất: turn <X> với A <Y> tokens, B <Z> tokens (chênh lệch <W> tokens)>\n"
    "- <Phân tích nguyên nhân với dẫn chứng cụ thể từ messages và tool calls>\n\n"
    "## Phân tích mạch hội thoại và context\n"
    "### Session A - Sử dụng history\n"
    "- <Phân tích cách A sử dụng history>\n"
    "- <Điểm mạnh và yếu>\n"
    "- <Tác động đến chất lượng trả lời>\n\n"
    "### Session B - Sử dụng summary\n"
    "- <Phân tích cách B sử dụng summary>\n"
    "- <Điểm mạnh và yếu>\n"
    "- <Tác động đến chất lượng trả lời>\n\n"
    "### So sánh context management\n"
    "- <So sánh chi tiết cách quản lý context>\n"
    "- <Phân tích tác động của summary>\n"
    "- <Đánh giá tính nhất quán>\n\n"
    "## Phân tích khả năng thích ứng\n"
    "### Xử lý câu hỏi phức tạp\n"
    "- <So sánh cách A và B xử lý câu hỏi khó>\n"
    "- <Phân tích chi tiết từng trường hợp>\n"
    "- <Đánh giá tính sáng tạo và linh hoạt>\n\n"
    "### Xử lý edge cases\n"
    "- <Phân tích cách xử lý các trường hợp đặc biệt>\n"
    "- <So sánh khả năng recovery>\n"
    "- <Đánh giá tính robust>\n\n"
    "## Kết luận tổng thể\n"
    "### Winner: **<A/B/tie>**\n"
    "### Lý do chính (5-7 gạch đầu dòng chi tiết với dẫn chứng)\n"
    "- <Lý do 1 với phân tích chi tiết và dẫn chứng cụ thể từ turn <X>: \"A trả lời '...' trong khi B trả lời '...'\"\n"
    "- <Lý do 2 với phân tích chi tiết và dẫn chứng cụ thể từ tool usage: \"A gọi tool <tên> với input <input> trong khi B gọi tool <tên> với input <input>\"\n"
    "- <Lý do 3 với phân tích chi tiết và dẫn chứng cụ thể từ token usage: \"A sử dụng <X> tokens, B sử dụng <Y> tokens (chênh lệch <Z> tokens)\"\n"
    "- <Lý do 4 với phân tích chi tiết và dẫn chứng cụ thể từ context usage: \"A sử dụng history '...' trong khi B sử dụng summary '...'\"\n"
    "- <Lý do 5 với phân tích chi tiết và dẫn chứng cụ thể từ quality scores: \"A đạt <X> điểm, B đạt <Y> điểm trong turn <Z>\"\n\n"
    "### Khuyến nghị cải thiện cho A\n"
    "- <Khuyến nghị 1 với giải thích chi tiết và dẫn chứng từ turn <X>: \"Dựa trên việc A gọi tool <tên> không cần thiết trong turn <X>\"\n"
    "- <Khuyến nghị 2 với giải thích chi tiết và dẫn chứng từ token usage: \"A sử dụng <X> tokens nhiều hơn B <Y> tokens trong turn <Z>\"\n"
    "- <Khuyến nghị 3 với giải thích chi tiết và dẫn chứng từ quality: \"A đạt điểm thấp hơn B <X> điểm trong turn <Y> do <lý do cụ thể>\"\n\n"
    "### Khuyến nghị cải thiện cho B\n"
    "- <Khuyến nghị 1 với giải thích chi tiết và dẫn chứng từ turn <X>: \"Dựa trên việc B gọi tool <tên> không cần thiết trong turn <X>\"\n"
    "- <Khuyến nghị 2 với giải thích chi tiết và dẫn chứng từ token usage: \"B sử dụng <X> tokens nhiều hơn A <Y> tokens trong turn <Z>\"\n"
    "- <Khuyến nghị 3 với giải thích chi tiết và dẫn chứng từ quality: \"B đạt điểm thấp hơn A <X> điểm trong turn <Y> do <lý do cụ thể>\"\n\n"
    "### Khuyến nghị tổng thể\n"
    "- <Khuyến nghị về việc sử dụng summary>\n"
    "- <Khuyến nghị về tối ưu hóa token>\n"
    "- <Khuyến nghị về cải thiện tool usage>\n"
    "- <Khuyến nghị về context management>\n"
    "## IMPORTANT NOTE"
    "   - Đảm bảo dựa vào system prompt để xem xét action cũng như phản hồi của agent để đánh giá chi tiết"
)


def build_llm_markdown_user_payload(report: Dict[str, Any]) -> str:
    """Đóng gói dữ liệu vào JSON gọn để LLM sinh Markdown theo template trên."""
    
    def shrink_tool_content(content: str, max_length: int = 500) -> str:
        """Chỉ giới hạn ký tự content của tool giống streamlit_demo.py"""
        if isinstance(content, str) and len(content) > max_length:
            return content[:max_length] + "..."
        return content
    
    def shrink_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Chỉ giới hạn tool result content"""
        if not isinstance(tools, list):
            return []
        
        shrunk_tools = []
        for tool in tools:
            shrunk_tool = tool.copy()
            if isinstance(tool.get("result"), str):
                shrunk_tool["result"] = shrink_tool_content(tool["result"])
            shrunk_tools.append(shrunk_tool)
        return shrunk_tools
    
    def shrink_trace_actions(trace_actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Giới hạn content trong trace actions"""
        if not isinstance(trace_actions, list):
            return []
        
        shrunk_actions = []
        for action in trace_actions:
            shrunk_action = action.copy()
            if "tools" in shrunk_action:
                shrunk_action["tools"] = shrink_tools(shrunk_action["tools"])
            shrunk_actions.append(shrunk_action)
        return shrunk_actions
    
    def shrink_last_conversation(last_conv: Dict[str, Any]) -> Dict[str, Any]:
        """Giới hạn content trong last conversation - chỉ shrink tool content trong messages"""
        if not isinstance(last_conv, dict):
            return {}
        
        shrunk_conv = last_conv.copy()
        
        # Chỉ shrink tool result content trong messages, giữ nguyên user/assistant messages
        if "messages" in shrunk_conv:
            shrunk_messages = []
            for msg in shrunk_conv["messages"]:
                shrunk_msg = msg.copy()
                if isinstance(msg.get("content"), dict) and "toolResult" in msg["content"]:
                    # Chỉ shrink tool result content
                    tool_result = msg["content"]["toolResult"].copy()
                    if tool_result.get("content"):
                        for content_item in tool_result["content"]:
                            if isinstance(content_item, dict):
                                for key, value in content_item.items():
                                    if isinstance(value, str):
                                        content_item[key] = shrink_tool_content(value)
                    shrunk_msg["content"] = {"toolResult": tool_result}
                shrunk_messages.append(shrunk_msg)
            shrunk_conv["messages"] = shrunk_messages
        
        return shrunk_conv
    
    # Chuẩn bị payload với cấu trúc mới
    payload = {
        "model_id": report.get("model_id"),
        "generated_at": report.get("generated_at"),
        "sessionA": {
            "id": report.get("sessionA", {}).get("id"),
            "label": report.get("sessionA", {}).get("label"),
            "num_traces": report.get("sessionA", {}).get("num_traces", 0),
            "last_conversation": shrink_last_conversation(report.get("sessionA", {}).get("last_conversation", {})),
            "trace_actions": shrink_trace_actions(report.get("sessionA", {}).get("trace_actions", []))
        },
        "sessionB": {
            "id": report.get("sessionB", {}).get("id"),
            "label": report.get("sessionB", {}).get("label"),
            "num_traces": report.get("sessionB", {}).get("num_traces", 0),
            "last_conversation": shrink_last_conversation(report.get("sessionB", {}).get("last_conversation", {})),
            "trace_actions": shrink_trace_actions(report.get("sessionB", {}).get("trace_actions", []))
        }
    }
    return json.dumps(payload, ensure_ascii=False)


def generate_markdown_with_llm_direct(report_data: Dict[str, Any], bedrock: BedrockClient, temperature: float = 0.2) -> str:
    """Tạo báo cáo markdown trực tiếp từ dữ liệu session - bỏ qua JSON evaluation"""
    user_payload = (
        "Hãy tạo báo cáo Markdown theo đúng template. Dữ liệu đầu vào JSON dưới đây:\n\n" +
        json.dumps(report_data, ensure_ascii=False, indent=2)
    )
    return bedrock.converse_json(EVAL_MARKDOWN_SYSTEM_PROMPT, user_payload, temperature=temperature, max_tokens=65536)


def main():
    parser = argparse.ArgumentParser(description="Tạo báo cáo markdown so sánh 2 session Langfuse")
    parser.add_argument("--session-a", required=True, help="Session ID phương pháp A (history thường)")
    parser.add_argument("--session-b", required=True, help="Session ID phương pháp B (history + summary)")
    parser.add_argument("--label-a", default="History thường")
    parser.add_argument("--label-b", default="History + Summary")
    parser.add_argument("--output", default="evaluation_report.md", help="Đường dẫn file Markdown kết quả")
    parser.add_argument("--max-traces", type=int, default=50)
    parser.add_argument("--max-obs-per-trace", type=int, default=10)
    args = parser.parse_args()

    # Tạo báo cáo markdown trực tiếp
    markdown_report = evaluate_sessions_markdown(
        session_a=args.session_a,
        session_b=args.session_b,
        label_a=args.label_a,
        label_b=args.label_b,
        output_path=args.output,
        max_traces=args.max_traces,
        max_obs_per_trace=args.max_obs_per_trace,
    )
    
    print(f"Generated markdown report with {len(markdown_report)} characters")
    print(f"Saved markdown report to {args.output}")
    


if __name__ == "__main__":
    main()


