"""Refreshed Dev‑Assistant module (v1.1)

▸ Uses langchain‑community imports (>= 0.2).
▸ Auto‑creates vector store **whenever it is missing or corrupt** (even after you delete `.vector_store`).
▸ Still skips corrupt memory entries.
"""
from __future__ import annotations

import difflib
import json
import logging
import subprocess
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel

# ── LangChain (community) ────────────────────────────────────────────────────
from langchain_community.chat_models import ChatOpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.memory import ConversationBufferMemory
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.tools import tool
from langchain.agents import AgentExecutor, AgentType, initialize_agent

logger = logging.getLogger("dev_assistant")

# ── Paths & Constants ────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent  # Repo root
MEM_PATH = ROOT / "config" / "dev_assistant_memory.json"
STORE_DIR = ROOT / ".vector_store"
CODE_EXT = {"py", "js", "jsx", "ts", "tsx", "json"}  # File extensions to include
EXCLUDE_DIRS = {"node_modules", "venv", ".venv", "dist", "build", ".git", "__pycache__", ".vector_store"}  # Directories to exclude

# ── Memory Helpers ───────────────────────────────────────────────────────────

def _load_raw_turns() -> List[dict]:
    """Load conversation history from memory."""
    if not MEM_PATH.exists():
        return []
    try:
        data = json.loads(MEM_PATH.read_text())
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict) and "user" in x and "assistant" in x]
        if isinstance(data, dict) and "conversations" in data:
            return [
                {"user": c.get("user_prompt", ""), "assistant": c.get("assistant_reply", "")}
                for c in data["conversations"]
            ]
    except Exception:
        logger.warning("Memory file unreadable – starting blank")
    return []

_buffer: List[dict] = _load_raw_turns()

memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
for turn in _buffer:
    memory.chat_memory.add_user_message(turn["user"])
    memory.chat_memory.add_ai_message(turn["assistant"])

def _persist(turn: dict):
    """Persist a new conversation turn to memory."""
    _buffer.append(turn)
    try:
        MEM_PATH.write_text(json.dumps(_buffer, indent=2))
    except Exception as e:
        logger.error("Failed to persist dev‑assistant memory: %s", e)

# ── Vector Store Helpers ─────────────────────────────────────────────────────

def _build_store() -> FAISS:
    """Build the vector store by indexing code files."""
    logger.info("[DevAssistant] Building code vector store (this is one‑off)…")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,  # Larger chunk size to fit entire functions
        chunk_overlap=120  # Small overlap for context
    )
    texts, metas = [], []
    files = list(ROOT.rglob("**/*"))  # Collect all files first for progress tracking

    for i, path in enumerate(files, 1):
        # Skip excluded directories
        if any(excluded in path.parts for excluded in EXCLUDE_DIRS):
            continue

        # Process only files with allowed extensions
        if path.is_file() and path.suffix.lstrip(".") in CODE_EXT:
            try:
                src = path.read_text(encoding="utf-8")
                for chunk in splitter.split_text(src):
                    texts.append(chunk)
                    metas.append({"path": str(path)})
            except Exception:
                logger.warning("Failed to read file: %s", path)

        # Log progress every 100 files
        if i % 100 == 0:
            logger.info("Indexed %d/%d files", i, len(files))

    # Create and save the vector store
    store = FAISS.from_texts(texts, OpenAIEmbeddings(), metadatas=metas)
    store.save_local(STORE_DIR)
    return store

# Load or create store safely
try:
    if (STORE_DIR / "index.faiss").exists():
        store = FAISS.load_local(STORE_DIR, OpenAIEmbeddings(model="text-embedding-ada-002"))
    else:
        store = _build_store()
except Exception as e:  # Corrupted store → rebuild
    logger.warning("Vector store load failed (%s) – rebuilding", e)
    STORE_DIR.mkdir(exist_ok=True)
    store = _build_store()

# ── Tools ────────────────────────────────────────────────────────────────────

@tool("code_search")
def code_search(query: str) -> str:
    """Search repository code and return up to 4 snippets."""
    try:
        docs = store.similarity_search(query, k=4)
        return "\n\n".join(f"{d.metadata['path']}\n{d.page_content}" for d in docs)
    except Exception as e:
        return f"❌ code_search failed: {e}"


class PatchArgs(BaseModel):
    file_path: str
    patch: Optional[str] = None  # Make patch optional


@tool("code_edit", args_schema=PatchArgs, return_direct=True)
def code_edit(file_path: str, patch: str) -> str:
    """
    Apply a unified diff patch to a file and commit the changes.

    Args:
        file_path (str): The path to the file to be patched.
        patch (str): The unified diff patch to apply.

    Returns:
        str: A success message if the patch is applied and committed, or an error message if it fails.
    """
    logger.info(f"Received file_path: {file_path}")
    logger.info(f"Received patch: {patch}")

    path = ROOT / file_path
    if not path.exists():
        return f"❌ {file_path} not found"
    try:
        orig = path.read_text().splitlines(keepends=True)
        new = list(difflib.restore(patch.splitlines(keepends=True), 2))
        path.write_text("".join(new))
        subprocess.run(["git", "checkout", "-B", "ai-patch"], cwd=ROOT, check=True)
        subprocess.run(["git", "add", file_path], cwd=ROOT, check=True)
        subprocess.run(["git", "commit", "-m", f"AI patch: {file_path}"], cwd=ROOT, check=True)
        return "✅ Patch applied & committed on ai-patch"
    except Exception as e:
        logger.exception("Patch failed")
        return f"❌ Patch failed: {e}"


class ShowArgs(BaseModel):
    file_path: str  # Example: "stores/shopify_async.py" or "stores/shopify_async.py:40:120"

@tool(
    "code_show",
    args_schema=ShowArgs,
    description="Return the entire file or the slice file_path:start:end.",
    return_direct=True
)
def code_show(file_path: str) -> str:
    """
    Return the entire file or a specific line range from a file.

    Args:
        file_path (str): The path to the file, optionally with :<line_start>:<line_end>.

    Returns:
        str: The requested lines or the entire file content.
    """
    try:
        if ":" in file_path:
            parts = file_path.split(":")
            if len(parts) == 3:
                path, start, end = parts
                src = (ROOT / path).read_text().splitlines()
                slice = src[int(start) - 1:int(end)]
                return f"{path} lines {start}-{end}\n" + "\n".join(slice)
            else:
                logger.warning("Invalid file_path format. Expected format: <path>:<start>:<end>")
                return "❌ Invalid file_path format. Expected format: <path>:<start>:<end>"
        else:
            path = ROOT / file_path
            return path.read_text()
    except Exception as e:
        logger.exception("Failed to retrieve code")
        return f"❌ Failed to retrieve code: {e}"

# ── Agent ────────────────────────────────────────────────────────────────────
llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
agent: AgentExecutor = initialize_agent(
    [code_search, code_edit, code_show],  # Add code_show to the tools
    llm,
    memory=memory,
    agent=AgentType.OPENAI_FUNCTIONS,
    verbose=True
)

# ── FastAPI-Friendly Entry ───────────────────────────────────────────────────
class DevChatRequest(BaseModel):
    query: str
    model: Optional[str] = None

async def dev_chat(req: DevChatRequest):
    """Handle developer chat requests."""
    if req.model and req.model != llm.model_name:
        agent.llm = ChatOpenAI(model=req.model, temperature=0.1)
    try:
        reply = await agent.arun(req.query.strip())
        _persist({"user": req.query, "assistant": reply})
        return {"result": reply}
    except Exception as e:
        logger.exception("DevAssistant error")
        return {"error": str(e)}
