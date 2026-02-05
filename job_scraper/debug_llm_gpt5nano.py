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

# Test prompt and model
MODEL = "gpt-5-nano"

PROMPT = """
You are a job match scorer. Given a job description and a resume, return a JSON object with the following fields: score (float, 0-10), reason (string), title (string), company (string). Example: {\n  \"score\": 8.5,\n  \"reason\": \"Strong match on skills and experience.\",\n  \"title\": \"Data Scientist\",\n  \"company\": \"Acme Corp\"\n}\nJob Description: Data Scientist at Acme Corp. Requirements: Python, ML, SQL.\nResume: Experienced in Python, ML, SQL, and data analysis.\n"""

# Prepare API call

messages = [
    ChatCompletionSystemMessageParam(
        role="system", content="You are a helpful assistant."
    ),
    ChatCompletionUserMessageParam(role="user", content=PROMPT),
]


try:
    logging.info(f"Calling OpenAI API with model: {MODEL}")
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_completion_tokens=512,
    )
    logging.info(f"Raw API response: {response}")
    content = response.choices[0].message.content
    logging.info(f"LLM content: {content}")
    try:
        if content is not None:
            data = json.loads(content)
            logging.info(f"Parsed JSON: {data}")
        else:
            logging.error("No content returned from LLM response; cannot parse JSON.")
    except Exception as e:
        logging.error(f"Failed to parse JSON: {e}")
        logging.error(f"Raw content: {content}")
except Exception as e:
    logging.error(f"OpenAI API call failed: {e}")
