import asyncio
import base64
import io
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
from src.extentions.multimodal.prompt import pdf_detect_prompt,system_prompt
from src.extentions.multimodal.make import pdf_to_corrected_images

VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://192.168.120.12:2900/v1")
VLLM_MODEL_NAME = os.getenv("VLLM_MODEL_NAME", "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "EMPTY")



async def process_pdf(pdf_bytesio: io.BytesIO) -> list[dict]:
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
        # extra_body={
        #         "chat_template_kwargs": {"enable_thinking": True},
        #         "skip_special_tokens": False
        #     },
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": pdf_detect_prompt},
                    *image_contents,
                ],
            }
        ],
    )

    return response.choices[0].message.content


async def main():
    file_path = "/home/vpdk02/nlp/bags/extract_gcn/tests/output/0_DE 513009-GCN.pdf"
    with open(file_path, "rb") as f:
        pdf_bytesio = io.BytesIO(f.read())

    text = await ocr_pdf(pdf_bytesio)
    print(text)


if __name__ == "__main__":
    asyncio.run(main())