# modules/langchain_agent.py

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from modules.grace_brain import GraceBrain
import logging
from dotenv import load_dotenv
import os
import asyncio

# Load environment variables
load_dotenv()

# Logger setup
logger = logging.getLogger("langchain_agent")

# Initialize GraceBrain
brain = GraceBrain()

# --- Prompt Template ---
async def build_grace_prompt(message: str, history: str = "") -> str:
    """Build a prompt for Grace using the conversation history and user message."""
    try:
        if not message:
            logger.warning("Empty message received for prompt building.")
            return "I'm sorry, I didn't understand your request."
        return await brain.build_prompt(history, message)
    except Exception as e:
        logger.error(f"Error building prompt: {e}", exc_info=True)
        return "I'm sorry, I couldn't process your request."

# --- LLM Setup ---
llm = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "gpt-4o"),
    temperature=float(os.getenv("OPENAI_TEMPERATURE", 0.7)),
    streaming=bool(int(os.getenv("OPENAI_STREAMING", 1))),
)

# --- LangChain Flow ---
GraceAgent = RunnableLambda(
    lambda prompt: asyncio.run(build_grace_prompt(prompt, ""))
) | llm
