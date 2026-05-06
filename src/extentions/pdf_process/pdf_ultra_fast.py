import ctypes
import os
import time
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

_lib = ctypes.CDLL("src/extentions/pdf_process/libpdf_converter.so")

class ImageResult(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.POINTER(ctypes.c_ubyte)),
        ("size", ctypes.c_size_t),
        ("width", ctypes.c_int),
        ("height", ctypes.c_int),
        ("success", ctypes.c_int),
    ]

_lib.pdf_get_page_count.argtypes = [ctypes.c_char_p]
_lib.pdf_get_page_count.restype = ctypes.c_int

_lib.pdf_render_page_raw_base64.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_double]
_lib.pdf_render_page_raw_base64.restype = ctypes.POINTER(ImageResult)

_lib.free_image_result.argtypes = [ctypes.POINTER(ImageResult)]
_lib.free_image_result.restype = None

def get_page_count(pdf_path: str) -> int:
    return _lib.pdf_get_page_count(pdf_path.encode("utf-8"))

def render_page_fast(pdf_path: str, page_num: int, dpi: float = 144) -> Optional[tuple]:
    result = _lib.pdf_render_page_raw_base64(
        pdf_path.encode("utf-8"), page_num, dpi
    )

    if not result or not result.contents.success:
        if result:
            _lib.free_image_result(result)
        return None

    b64_str = ctypes.string_at(
        result.contents.data, result.contents.size
    ).decode("ascii")
    width = result.contents.width
    height = result.contents.height
    raw_size = width * height * 3

    _lib.free_image_result(result)

    return (b64_str, width, height, raw_size)

def process_single_page(args):
    pdf_path, page_num, dpi = args
    return render_page_fast(pdf_path, page_num, dpi)

def pdf_to_base64_parallel(
    pdf_path: str,
    dpi: float = 144,
    max_workers: int = 8,
    verbose: bool = True,
) -> List[Dict]:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    page_count = get_page_count(pdf_path)
    if page_count <= 0:
        raise ValueError(f"Cannot read PDF or empty: {pdf_path}")

    if verbose:
        print(f"File: {Path(pdf_path).name}")
        print(f"Pages: {page_count}")
        print(f"DPI: {dpi}")
        print(f"Workers: {max_workers}")
        print()

    start_time = time.time()

    args_list = [(pdf_path, i, dpi) for i in range(page_count)]

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for i, result in enumerate(executor.map(process_single_page, args_list)):
            if result:
                b64_str, width, height, raw_size = result
                size_kb = len(b64_str) * 0.75 / 1024

                results.append(
                    {
                        "page": i + 1,
                        "base64": b64_str,
                        "data_uri": f"data:image/rgb;base64,{b64_str}",
                        "width": width,
                        "height": height,
                        "size_kb": size_kb,
                    }
                )

                if verbose:
                    print(
                        f"Page {i + 1}/{page_count} - {size_kb:.1f} KB"
                    )

    total_time = time.time() - start_time

    if verbose:
        print(
            f"\nDone in {total_time:.2f}s "
            f"({total_time / page_count:.3f}s/page)"
        )
        print(f"Total: {sum(r['size_kb'] for r in results):.1f} KB")
        print(f"Speed: {page_count / total_time:.1f} pages/sec")

    return results

def save_base64_to_file(results: List[Dict], output_file: str):
    with open(output_file, "w", encoding="utf-8") as f:
        for item in results:
            f.write(f"=== PAGE {item['page']} ===\n")
            f.write(f"Size: {item['width']}x{item['height']}\n")
            f.write(f"{item['base64']}\n\n")
    print(f"Saved to: {output_file}")

if __name__ == "__main__":
    from pdf_ultra_fast import pdf_to_base64_parallel, save_base64_to_file
    pdf_file = "/home/cit/bags/so-hoa-pho-quat/src/tests/files/goc_cay2.pdf"

    results_generator = pdf_to_base64_parallel(pdf_file, dpi=144, max_workers=16)