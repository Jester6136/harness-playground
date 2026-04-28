"""Tools as plain Python functions decorated with @tool.

LangChain reads the docstring (becomes the model-facing description) and the
type hints (become the JSON schema). No registry boilerplate needed — just
write a function and add it to ALL_TOOLS.
"""
import subprocess
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.types import interrupt


@tool
def read_file(path: str) -> str:
    """Read a UTF-8 text file from disk and return its contents.

    Files larger than 20K chars are truncated to keep the context window bounded.
    """
    text = Path(path).read_text()
    if len(text) > 20_000:
        return text[:20_000] + f"\n\n... [truncated {len(text) - 20_000} chars]"
    return text


@tool
def list_dir(path: str = ".") -> str:
    """List entries in a directory. 'd' prefix = directory, 'f' = file."""
    entries = sorted(Path(path).iterdir(), key=lambda p: (not p.is_dir(), p.name))
    return "\n".join(f"{'d' if p.is_dir() else 'f'} {p.name}" for p in entries)


# Substrings that must never run, even with approval.
HARD_DENY = ("rm -rf /", "mkfs", ":(){ :|:& };:", "dd if=/dev/zero of=/dev/")


@tool
def write_file(path: str, content: str) -> str:
    """Write text to a file (creates or overwrites). Requires human approval."""
    decision = interrupt({
        "type": "approval",
        "tool": "write_file",
        "args": {"path": path, "bytes": len(content)},
    })
    if decision != "approve":
        return "ERROR: denied by user"
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"wrote {len(content)} bytes to {p}"


@tool
def run_bash(command: str) -> str:
    """Run a shell command and return stdout/stderr. Requires human approval."""
    for danger in HARD_DENY:
        if danger in command:
            return f"ERROR: command matches denylist pattern {danger!r}"
    decision = interrupt({
        "type": "approval",
        "tool": "run_bash",
        "args": {"command": command},
    })
    if decision != "approve":
        return "ERROR: denied by user"
    result = subprocess.run(
        command, shell=True, capture_output=True, text=True, timeout=30
    )
    return (
        f"exit_code: {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}"
        f"--- stderr ---\n{result.stderr}"
    )


@tool
def analyze_image(path: str, question: str = "Describe this image in detail.") -> str:
    """Analyze an image or PDF using the vision model.

    Supports JPEG, PNG, GIF, WebP, and PDF (converted to images automatically).
    Returns the model's answer to the question about the file contents.
    """
    from harness.multimodal import file_to_contents

    contents = file_to_contents(path)
    if not contents:
        return f"ERROR: unsupported or unreadable file: {path}"

    from harness.config import TEMPERATURE, VLLM_API_KEY, VLLM_BASE_URL, VLLM_MODEL_NAME
    from langchain_openai import ChatOpenAI

    vlm = ChatOpenAI(
        base_url=VLLM_BASE_URL,
        api_key=VLLM_API_KEY,
        model=VLLM_MODEL_NAME,
        temperature=TEMPERATURE,
    )
    msg = HumanMessage(content=[{"type": "text", "text": question}] + contents)
    response = vlm.invoke([msg])
    return response.content


@tool
def remember_about_user(key: str, value: str) -> str:
    """Persist a fact about the current user in long-term memory.

    Use this to remember information that should survive across sessions, e.g.
    the user's name, role, preferences, or project context. Key should be a
    short snake_case label (e.g. 'name', 'department', 'preferred_language').
    """
    import asyncio
    from langchain_core.runnables import RunnableConfig

    async def _write(key: str, value: str) -> str:
        from harness.store import get_store
        store = await get_store()
        # Thread context not available inside a plain @tool without RunnableConfig.
        # We use a generic namespace; the API layer should inject user_id via config.
        namespace = ("users", "default")
        await store.aput(namespace, key, {"value": value})
        return f"Remembered: {key} = {value!r}"

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _write(key, value))
                return future.result()
        else:
            return loop.run_until_complete(_write(key, value))
    except Exception as exc:
        return f"ERROR storing memory: {exc}"


@tool
def recall_user_context() -> str:
    """Retrieve all facts remembered about the current user from long-term memory.

    Returns a formatted list of key-value pairs. Returns an empty message if
    no facts have been stored yet.
    """
    import asyncio

    async def _read() -> str:
        from harness.store import get_store
        store = await get_store()
        namespace = ("users", "default")
        items = await store.asearch(namespace)
        if not items:
            return "No facts remembered about this user yet."
        lines = ["**Remembered facts:**"]
        for item in items:
            lines.append(f"  {item.key}: {item.value.get('value', item.value)}")
        return "\n".join(lines)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _read())
                return future.result()
        else:
            return loop.run_until_complete(_read())
    except Exception as exc:
        return f"ERROR reading memory: {exc}"


ALL_TOOLS = [read_file, list_dir, write_file, run_bash, analyze_image,
             remember_about_user, recall_user_context]
