import requests

class GeneralPurposeAgent:
    def __init__(self, system_prompt, human_prompt=None):
        self.system_prompt = system_prompt
        self.human_prompt = human_prompt if human_prompt else None
        self.api_url = "https://stock.cmcts.ai/c-agent/api/v1/prediction/a1514d8f-749c-4e01-b961-811e9346d83e"

    def change_system_prompt(self, system_prompt):
        self.system_prompt = system_prompt

    def query(self, payload):
        response = requests.post(self.api_url, json=payload)
        try:
            return response.json()
        except Exception as e:
            print(f"Error: {e}")
            return response

    def get_response(self, question):
        if self.human_prompt:
            payload = {
                "question": question,
                "overrideConfig": {
                    "systemMessagePrompt": self.system_prompt,
                    "humanMessagePrompt": self.human_prompt,
                }
            }
        else:
            payload = {
                "question": question,
                "overrideConfig": {
                    "systemMessagePrompt": self.system_prompt,
                }
            }
        return self.query(payload)
