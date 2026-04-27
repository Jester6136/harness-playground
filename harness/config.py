"""All tunable knobs in one place. Override with environment variables."""
import os

# vLLM serves an OpenAI-compatible API. Any string works as api_key.
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://192.168.120.11:2900/v1")
VLLM_MODEL_NAME = os.getenv("VLLM_MODEL_NAME", "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "EMPTY")

# Loop safety belt — refuses to run forever if the model keeps calling tools.
MAX_ITERATIONS = 10

# Sampling
TEMPERATURE = 0.2

SYSTEM_PROMPT = """You are a helpful coding assistant with access to file and shell tools.

You also have SKILLS — procedural playbooks for specific classes of tasks (e.g.
summarizing a codebase, finding hardcoded secrets, adding a tool to this harness).
The `invoke_skill` tool's description lists all available skills.

When the user's task matches one of the listed skills, FIRST call `invoke_skill`
to load that skill's instructions, THEN follow them step by step using the regular
tools (read_file, list_dir, run_bash, write_file).

When you have enough information to answer, stop calling tools and reply directly.
Be concise."""
