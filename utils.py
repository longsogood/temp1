import requests
import re
from datetime import datetime
import json

def query(API_URL, payload):
    response = requests.post(API_URL, json=payload)
    return response

def extract_json(response_text):
    pattern = r"```json\s*([\[{].*?[\]}])\s*```"
    match = re.search(pattern, response_text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    return None

def extract_section(text):
    json_data = extract_json(text)
    results = {}
    if json_data:
        results["scores"] = {}
        relevance = json_data["relevance"]
        accuracy_and_currency = json_data["accuracy_and_currency"]
        completeness_and_guidance = json_data["completeness_and_guidance"]
        clarity_and_format = json_data["clarity_and_format"]
        supportiveness_and_tone = json_data["supportiveness_and_tone"]
        results["scores"]["relevance"] = relevance
        results["scores"]["accuracy_and_currency"] = accuracy_and_currency
        results["scores"]["completeness_and_guidance"] = completeness_and_guidance
        results["scores"]["clarity_and_format"] = clarity_and_format
        results["scores"]["supportiveness_and_tone"] = supportiveness_and_tone
        results["scores"]["average"] = (relevance + accuracy_and_currency + completeness_and_guidance + clarity_and_format + supportiveness_and_tone) / 5
        results["comments"] = json_data["comments"]
        return results
    else:
        return None