import requests
import re
from datetime import datetime
import json
import json_repair

def query(API_URL, payload):
    response = requests.post(API_URL, json=payload)
    return response

def extract_json(response_text):
    if not response_text or not isinstance(response_text, str):
        print("Response text is empty or not a string")
        return None
        
    try:
        # Thử tìm JSON trong code blocks trước
        pattern = r"```json\s*([\[{].*?[\]}])\s*```"
        match = re.search(pattern, response_text, re.DOTALL)
        if match:
            try:
                obj = json.loads(match.group(1))
                return obj
            except json.JSONDecodeError:
                try:
                    obj = json_repair.loads(match.group(1))
                    return obj
                except Exception as e:
                    print(f"Lỗi khi repair JSON trong code block: {e}")
        
        # Thử parse toàn bộ response text
        try:
            obj = json.loads(response_text)
            return obj
        except json.JSONDecodeError:
            try:
                obj = json_repair.loads(response_text)
                return obj
            except Exception as e:
                print(f"Lỗi khi repair JSON từ response: {e}")
                return None
                
    except Exception as e:
        print(f"Lỗi không mong đợi trong extract_json: {e}")
        return None

def extract_section(text):
    json_data = extract_json(text)
    print(f"JSON data:\n{json_data}")
    results = {}
    
    if json_data and isinstance(json_data, dict):
        results["scores"] = {}
        try:
            # Kiểm tra và lấy các trường cần thiết với giá trị mặc định
            relevance = json_data.get("relevance", 0)
            accuracy = json_data.get("accuracy", 0)
            completeness = json_data.get("completeness", 0)
            clarity = json_data.get("clarity", 0)
            tone = json_data.get("tone", 0)
            
            results["scores"]["relevance"] = relevance
            results["scores"]["accuracy"] = accuracy
            results["scores"]["completeness"] = completeness
            results["scores"]["clarity"] = clarity
            results["scores"]["tone"] = tone
            results["scores"]["average"] = (relevance + accuracy + completeness + clarity + tone) / 5
            results["comments"] = json_data.get("comments", "Không có nhận xét")
            
            return results
        except Exception as e:
            print(f"Lỗi khi xử lý JSON data: {e}")
            # Trả về kết quả mặc định thay vì None
            return {
                "scores": {
                    "relevance": 0,
                    "accuracy": 0,
                    "completeness": 0,
                    "clarity": 0,
                    "tone": 0,
                    "average": 0
                },
                "comments": f"Lỗi khi xử lý JSON: {str(e)}"
            }
    else:
        # Trả về kết quả mặc định thay vì None
        return {
            "scores": {
                "relevance": 0,
                "accuracy": 0,
                "completeness": 0,
                "clarity": 0,
                "tone": 0,
                "average": 0
            },
            "comments": "Không thể trích xuất dữ liệu từ response"
        }