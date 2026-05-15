import asyncio
import base64
import io
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Allow `python src/extentions/multimodal/ttcp_inference.py` direct-script
# execution to resolve `harness.*` imports (the report renderer below). The
# `python -m ...` form doesn't need this, but it's harmless when present.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load variables from .env into the environment
load_dotenv()
import litellm

litellm.turn_off_message_logging = True
litellm.suppress_logs = True

litellm_logger = logging.getLogger("LiteLLM")
litellm_logger.setLevel(logging.CRITICAL)
litellm_logger.propagate = False
from litellm import acompletion
from src.extentions.multimodal.prompt import ttcp_extract_prompt,ttcp_system_prompt
from src.extentions.multimodal.make import pdf_to_corrected_images
from harness.tools.ttcp_report import _build_html, _safe_filename

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://192.168.120.12:2900/v1")
VLLM_MODEL_NAME = os.getenv("VLLM_MODEL_NAME", "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "EMPTY")
ENABLE_THINKING = os.getenv("ENABLE_THINKING", "true").strip().lower() == "true"


async def process_pdf(pdf_bytesio: io.BytesIO, gcn_id: str = None) -> list[dict]:
    loop = asyncio.get_running_loop()
    images = await loop.run_in_executor(None, pdf_to_corrected_images, pdf_bytesio)

    # Gom tất cả ảnh vào 1 request
    image_contents = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img_b64}"}
        }
        for img_b64 in images
    ]

    response = await acompletion(
        model=f"openai/{VLLM_MODEL_NAME}",
        api_base=VLLM_BASE_URL,
        api_key=VLLM_API_KEY,
        **(
            {
                "extra_body": {
                    "chat_template_kwargs": {"enable_thinking": True},
                    "skip_special_tokens": False,
                }
            }
            if ENABLE_THINKING else {}
        ),
        temperature=1,
        top_p=0.9,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": ttcp_system_prompt
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ttcp_extract_prompt},
                    *image_contents,
                ],
            }
        ],
    )

    return response.choices[0].message.content

import asyncio
import io


_REPORTS_DIR = Path("reports")


def render_report(result_text: str) -> Path | None:
    """Build the standard HTML report from one extraction result.

    Wraps `result_text` (the JSON string from `process_pdf`) into the same
    shape the Mongo doc would have (``{"result": parsed}``), feeds it to
    the canonical `_build_html` from harness/tools/ttcp_report, writes the
    output under ``./reports/<số văn bản>.html``. Returns the file path.

    Returns None if the model output isn't valid JSON (logs and skips).
    """
    try:
        parsed = json.loads(result_text) if isinstance(result_text, str) else result_text
    except (json.JSONDecodeError, TypeError):
        print("⚠️  model output is not valid JSON — skipping report render")
        return None
    if not isinstance(parsed, dict):
        print(f"⚠️  unexpected result shape: {type(parsed).__name__} — skipping report")
        return None

    so_vb = ((parsed.get("thông tin chung") or {}).get("số văn bản") or "ttcp").strip() or "ttcp"
    doc = {"result": parsed}
    html_text = _build_html(doc)

    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _REPORTS_DIR / f"{_safe_filename(so_vb)}.html"
    out_path.write_text(html_text, encoding="utf-8")
    return out_path


async def infer(file_path: str):
    with open(file_path, "rb") as f:
        pdf_bytesio = io.BytesIO(f.read())

    result = await process_pdf(pdf_bytesio)

    print(f"\n{'=' * 30}")
    print(file_path)
    print(result)

    out_path = render_report(result)
    if out_path:
        print(f"→ report: {out_path.resolve()}")

    return result


async def main():
    file_paths = [
        "/home/vpdk02/nlp/bags/harness-playground/src/extentions/multimodal/test_files/0_20200910174452.pdf",
        # "src/extentions/multimodal/test_files/0_20200910165524.pdf"
    ]

    results = await asyncio.gather(
        *(infer(path) for path in file_paths)
    )

    return results


if __name__ == "__main__":
    asyncio.run(main())