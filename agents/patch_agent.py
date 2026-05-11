import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class PatchAgent:

    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )

    def generate_patch(self, failure_context):

        prompt = f"""
You are a software repair assistant.

A CI/CD pipeline failed with this error:

{failure_context}

Return the complete corrected contents of the affected file.

Preserve imports, functions, and structure.

Only fix the failing test.
Do not explain.
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
    
    def apply_patch(self, file_path, patch_code):

        cleaned_patch = patch_code.replace("```python", "").replace("```", "").strip()

        with open(file_path, "w") as file:
            file.write(cleaned_patch)

        return True