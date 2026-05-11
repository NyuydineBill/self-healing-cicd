import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class PatchAgent:

    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY")
        )

    def generate_patch(self, failure_context, target_file):

        # Read current target file
        with open(target_file, "r") as f:
            current_file_content = f.read()

        # Try to locate related source file
        source_context = ""

        if "project_1" in target_file:
            with open("sample_projects/project_1/app.py", "r") as f:
                source_context = f.read()

        elif "project_2" in target_file:
            with open("sample_projects/project_2/app.py", "r") as f:
                source_context = f.read()

        prompt = f"""
You are a software repair assistant.

A CI/CD pipeline failed with this error:

{failure_context}

Target file:
{target_file}

Current target file content:
{current_file_content}

Related source code:
{source_context}

Instructions:

1. Only modify the target file.
2. Do NOT invent new functions or imports.
3. Use only functions that already exist in the related source code.
4. Preserve the original test structure.
5. Return the COMPLETE corrected contents of the target file.
6. Return only valid Python code.
7. Do not explain anything.

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

        cleaned_patch = (
            patch_code
            .replace("```python", "")
            .replace("```", "")
            .strip()
        )

        with open(file_path, "w") as file:
            file.write(cleaned_patch)

        return True