import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class ReasoningAgent:

    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )

    def diagnose_failure(self, failure_context):

        prompt = f"""
You are a software debugging assistant.

Analyze the following CI/CD failure:

{failure_context}

Explain:
1. What caused the failure?
2. What should be fixed?
Keep the answer concise and technical.
"""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response.choices[0].message.content