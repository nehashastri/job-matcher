import json
import logging
import os

from dotenv import load_dotenv
from openai import OpenAI
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load environment variables from .env file if present
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    logging.warning(".env file not found at %s", dotenv_path)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logging.error("OPENAI_API_KEY not set in environment or .env file.")
    exit(1)

# Create OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


# --- Simple test: check if 'reasoning_effort' is supported by gpt-5-mini ---
def test_reasoning_effort_support():
    try:
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[{"role": "user", "content": "Hello!"}],
            max_completion_tokens=10,
            reasoning_effort="low",
        )
        print("'reasoning_effort' is supported by gpt-5-mini.")
    except TypeError as e:
        print("TypeError:", e)
        print("'reasoning_effort' is NOT supported by gpt-5-mini.")
    except Exception as e:
        print("Other Exception:", e)
        print("Check error details above.")


if __name__ == "__main__":
    test_reasoning_effort_support()
# --- End simple test ---

# Test prompt and model
MODEL = "gpt-5-nano"


# Load prompts as in main scorer
with open(
    os.path.join(os.path.dirname(__file__), "data", "LLM_rerank_score.txt"),
    "r",
    encoding="utf-8",
) as f:
    RERANK_PROMPT = f.read().strip()

BASE_PROMPT = 'You are a job match scorer. Given a job description and a resume, return a JSON object with the following fields: score (float, 0-10), reason (string), title (string), company (string). Example: {\n  "score": 8.5,\n  "reason": "Strong match on skills and experience.",\n  "title": "Data Scientist",\n  "company": "Acme Corp"\n}\n'

# Example job/resume for testing
JOB_DESCRIPTION = "Data Scientist at Acme Corp. Requirements: Python, ML, SQL."
RESUME = "Experienced in Python, ML, SQL, and data analysis."
JOB_TITLE = "Data Scientist"
COMPANY = "Acme Corp"
LOCATION = "Remote"


# Message builder to match main scorer
def build_messages(resume_text, job_details, prompt):
    description = job_details.get("description", "")
    return [
        ChatCompletionSystemMessageParam(
            role="system", content="You are a helpful assistant."
        ),
        ChatCompletionUserMessageParam(
            role="user",
            content=(
                f"{prompt}\nResume: {resume_text}\nJob Title: {job_details.get('title', '')}\nCompany: {job_details.get('company', '')}\nLocation: {job_details.get('location', '')}\nDescription: {description[:4000]}"
            ),
        ),
    ]


# Simulate main scorer LLM calls
job_details = {
    "title": JOB_TITLE,
    "company": COMPANY,
    "location": LOCATION,
    "description": JOB_DESCRIPTION,
}

# 1. Base scoring call
base_messages = build_messages(RESUME, job_details, BASE_PROMPT)

# 2. Rerank scoring call
rerank_messages = build_messages(RESUME, job_details, RERANK_PROMPT)


def call_llm(messages, label):
    try:
        logging.info(f"Calling OpenAI API with model: {MODEL} [{label}]")
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_completion_tokens=2048,
        )
        logging.info(f"Raw API response: {response}")
        content = response.choices[0].message.content
        logging.info(f"LLM content: {content}")
        try:
            if content is not None:
                data = json.loads(content)
                logging.info(f"Parsed JSON: {data}")
            else:
                logging.error(
                    "No content returned from LLM response; cannot parse JSON."
                )
        except Exception as e:
            logging.error(f"Failed to parse JSON: {e}")
            logging.error(f"Raw content: {content}")
    except Exception as e:
        logging.error(f"OpenAI API call failed: {e}")


# Run both base and rerank LLM calls
call_llm(base_messages, "base")
call_llm(rerank_messages, "rerank")
