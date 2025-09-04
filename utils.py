import requests
import re
from datetime import datetime
import json
import json_repair

def query(API_URL, payload):
    response = requests.post(API_URL, json=payload)
    return response

def extract_json(response_text):
    pattern = r"```json\s*([\[{].*?[\]}])\s*```"
    match = re.search(pattern, response_text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(1))
        except:
            obj = json_repair.loads(match.group(1))
        return obj
    else:
        obj = json_repair.loads(response_text)
        return obj
    return None

def extract_section(text):
    json_data = extract_json(text)
    print(f"JSON data:\n{json_data}")
    results = {}
    if json_data:
        results["scores"] = {}
        relevance = json_data["relevance"]
        accuracy = json_data["accuracy"]
        completeness = json_data["completeness"]
        access_control = json_data["access_control"]
        clarity = json_data["clarity"]
        results["scores"]["relevance"] = relevance
        results["scores"]["accuracy"] = accuracy
        results["scores"]["completeness"] = completeness
        results["scores"]["access_control"] = access_control
        results["scores"]["clarity"] = clarity
        results["scores"]["average"] = (relevance + accuracy + completeness + access_control + clarity) / 5
        results["comments"] = json_data["comments"]
        print(f"Extracted: {results}")
        return results
    else:
        return None