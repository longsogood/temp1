import pandas as pd
import json
import requests
from utils import extract_section

GENERAL_PURPOSE_API_URL = "https://stock.cmcts.ai/c-agent/api/v1/prediction/a1514d8f-749c-4e01-b961-811e9346d83e"
CMC_UNI_API_URL = "https://cmc-uni.cagent.cmcts.ai/api/v1/prediction/226da69f-74ed-4250-b754-a388e57b2877"

df = pd.read_excel("Book1.xlsx", sheet_name="c5278144-dcf8-41ca-8c5b-2a93734")
questions = df.iloc[:, 0].to_list()
true_answers = df.iloc[:, 1].to_list()
agent_answers = df.iloc[:, 2].to_list()
# print(len(questions), len(true_answers), len(agent_answers))
# print(true_answers[1])
evaluate_system_prompt = open("prompts/evaluation/system_prompt.txt", encoding="utf-8").read()
evaluate_human_prompt_template = open("prompts/evaluation/human_prompt.txt", encoding="utf-8").read()

result = {
    "Question": [],
    "True Answer": [],
    "Agent Answer": [],
    "Relevance": [],
    "Accuracy": [],
    "Completeness": [],
    "Clarity": [],
    "Tone": [],
    "Average score": [],
    "Comments": []
}

for question, true_answer, agent_answer in zip(questions, true_answers, agent_answers):
    evaluate_human_prompt = evaluate_human_prompt_template.format(
        question=question,
        true_answer=true_answer,
        agent_answer=agent_answer
    )

    payload = {
        "question": "Đánh giá câu trả lời từ agent so với câu trả lời chuẩn (true_answer)",
        "overrideConfig": {
                "systemMessagePrompt": evaluate_system_prompt,
                "humanMessagePrompt": evaluate_human_prompt
            }
    }
    print(f"Question: {question}")
    evaluate_response = requests.post(GENERAL_PURPOSE_API_URL, json=payload, timeout=1000)
    try:
        evaluate_response = evaluate_response.json()["text"]
    except Exception as e:
        print(f"Lỗi khi lấy response: {evaluate_response.text}")
    try:
        evaluate_result = extract_section(evaluate_response)
        result["Question"].append(question)
        result["True Answer"].append(true_answer)
        result["Agent Answer"].append(agent_answer)
        result["Relevance"].append(evaluate_result["scores"]["relevance"])
        result["Accuracy"].append(evaluate_result["scores"]["accuracy"])
        result["Completeness"].append(evaluate_result["scores"]["completeness"])
        result["Clarity"].append(evaluate_result["scores"]["clarity"])
        result["Tone"].append(evaluate_result["scores"]["tone"])
        result["Average score"].append(evaluate_result["scores"]["average"])
        result["Comments"].append(evaluate_result["comments"])
        print(f"Kết quả đánh giá câu hỏi {question}: {evaluate_response}")
    except Exception as e:
        error_message = f"Lỗi khi trích xuất kết quả đánh giá: {str(e)}"
        break

import pickle
with open("results.pkl", "wb") as f:
    pickle.dump(result, f)


df = pd.DataFrame.from_dict(result)
df.to_excel('outputB.xlsx', index=False)
