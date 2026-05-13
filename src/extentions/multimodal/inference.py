import asyncio
import base64
import io
import json
import logging
import os
from dotenv import load_dotenv
# Load variables from .env into the environment
load_dotenv()
import litellm

litellm.turn_off_message_logging = True
litellm.suppress_logs = True

litellm_logger = logging.getLogger("LiteLLM")
litellm_logger.setLevel(logging.CRITICAL)
litellm_logger.propagate = False
from litellm import acompletion
from src.extentions.multimodal.prompt import pdf_extract_prompt,extract_system_prompt
from src.extentions.multimodal.make import pdf_to_corrected_images

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
                "content": extract_system_prompt
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": pdf_extract_prompt},
                    *image_contents,
                ],
            }
        ],
    )

    return response.choices[0].message.content

import asyncio
import io


async def process_pdf(file_path: str):
    with open(file_path, "rb") as f:
        pdf_bytesio = io.BytesIO(f.read())

    result = await process_pdf(pdf_bytesio)

    print(f"\n{'=' * 30}")
    print(file_path)
    print(result)

    return result


async def main():
    file_paths = [
        "/home/vpdk02/nlp/bags/extract_gcn/tests/output/0_10363-GCN-BO 175400.pdf",
        "/home/vpdk02/nlp/bags/extract_gcn/tests/output/0_10363-GCN-BO 175403.pdf",
        "/home/vpdk02/nlp/bags/extract_gcn/tests/output/0_BO 175399-GCN.pdf"
    ]

    results = await asyncio.gather(
        *(process_pdf(path) for path in file_paths)
    )

    return results


if __name__ == "__main__":
    asyncio.run(main())