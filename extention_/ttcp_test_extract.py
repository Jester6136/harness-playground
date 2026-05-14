"""Test TTCP extraction trên vài PDF — không ghi DB, không cần MinIO list.

Mục đích: cho Sếp Thái xem 1-2 file PDF qua prompt+schema mới ra cái gì,
validate có pass không, field nào còn thiếu. Sau khi OK thì mới bump
TTCP_VERSION=2 và re-extract toàn bộ.

Usage::

    # Local files
    python extention_/ttcp_test_extract.py /path/to/kltt1.pdf /path/to/kltt2.pdf

    # MinIO keys (thêm --minio)
    python extention_/ttcp_test_extract.py --minio ttcp/ttcp-bot/abc.pdf ttcp/ttcp-bot/def.pdf

    # Dump full kết quả ra file để inspect kỹ
    python extention_/ttcp_test_extract.py --out report.json file1.pdf file2.pdf
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import os
import sys
import time
from pathlib import Path

# Đảm bảo import src.* khi chạy script trực tiếp.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

from src.extentions.multimodal.ttcp_inference import process_pdf  # noqa: E402
from src.extentions.multimodal.ttcp_validator import validate_ttcp  # noqa: E402

log = logging.getLogger("ttcp_test")


# ── source loaders ─────────────────────────────────────────────────────────


def _load_local(path: str) -> io.BytesIO:
    with open(path, "rb") as f:
        return io.BytesIO(f.read())


def _load_minio(key: str) -> io.BytesIO:
    """Lazy-import boto3 — chỉ cần khi --minio."""
    import boto3
    from botocore.config import Config

    s3 = boto3.client(
        "s3",
        endpoint_url=os.getenv("ENDPOINT_URL_MINIO", "http://192.168.120.12:9002"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID_MINIO", ""),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY_MINIO", ""),
        config=Config(signature_version="s3v4"),
    )
    bucket = os.getenv("TTCP_BUCKET", "datalens-data")
    buf = io.BytesIO()
    s3.download_fileobj(bucket, key, buf)
    buf.seek(0)
    return buf


# ── pretty-print summary ───────────────────────────────────────────────────


def _summarize(name: str, result: dict, elapsed: float) -> str:
    """Render một báo cáo tóm tắt 1 file để in ra console."""
    canon = result.get("canonical") or {}
    raw = result.get("raw_extract") or {}
    valid = result.get("valid")
    errs = result.get("errors", [])

    lines = [
        "",
        "═" * 78,
        f"  {name}    [{elapsed:.1f}s]    valid={valid}  errors={len(errs)}",
        "═" * 78,
    ]

    # Validation errors — show first 10
    if errs:
        lines.append("┌─ Validation errors ─┐")
        for e in errs[:10]:
            lines.append(f"  • {e}")
        if len(errs) > 10:
            lines.append(f"  … and {len(errs) - 10} more")
        lines.append("")

    # Khi invalid, vẫn dùng raw để show summary — Sếp Thái thấy VLM emit ra cái gì.
    src = canon if canon else raw
    if not isinstance(src, dict):
        lines.append(f"(raw is not a dict: {type(src).__name__})")
        return "\n".join(lines)

    def g(path: str, default=None):
        cur: Any = src
        for k in path.split("."):
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                return default
        return cur

    # ── nhận dạng văn bản ──
    lines.append("┌─ Văn bản ─┐")
    lines.append(f"  so_ket_luan       : {g('so_ket_luan')!r}")
    lines.append(f"  loai_van_ban      : {g('loai_van_ban')!r}")
    lines.append(f"  ngay_ban_hanh     : {g('ngay_ban_hanh')!r}   (nam={g('nam')!r})")
    lines.append(f"  co_quan_ban_hanh  : {g('co_quan_ban_hanh')!r}")
    lines.append(f"  nguoi_ky          : {g('nguoi_ky')!r} ({g('chuc_vu_nguoi_ky')!r})")

    # ── đối tượng ──
    lines.append("┌─ Đối tượng ─┐")
    lines.append(f"  doi_tuong_thanh_tra  : {g('doi_tuong_thanh_tra')!r}")
    lines.append(f"  don_vi_bi_thanh_tra  : {g('don_vi_bi_thanh_tra')}")
    lines.append(f"  dia_phuong (canon)   : {g('dia_phuong')}")

    # ── 5 phần ──
    pcc = g("phan_can_cu") or {}
    pnd = g("phan_noi_dung") or {}
    pttc = g("phan_to_chuc_thuc_hien") or {}
    lines.append("┌─ 5 phần KLTT ─┐")
    lines.append(f"  4.1 căn cứ:    QĐ={len(pcc.get('quyet_dinh_thanh_tra') or [])}  "
                 f"VBPL={len(pcc.get('van_ban_phap_luat') or [])}  "
                 f"KH={len(pcc.get('ke_hoach_thanh_tra') or [])}")
    thoi_ky = pnd.get("thoi_ky") or {}
    lines.append(f"  4.2 nội dung:  pham_vi={(pnd.get('pham_vi') or '')[:50]!r}…  "
                 f"thoi_ky={thoi_ky.get('tu')}→{thoi_ky.get('den')} "
                 f"({thoi_ky.get('mo_ta')!r})")
    lines.append(f"  4.3 vi_pham:   {len(g('vi_pham') or [])} item(s)")
    lines.append(f"  4.4 kien_nghi: {len(g('kien_nghi') or [])} item(s)")
    lines.append(f"  4.5 tổ chức:   don_vi={len(pttc.get('don_vi_thuc_hien') or [])}  "
                 f"thoi_han={pttc.get('thoi_han_chung')!r}")

    # ── breakdown vi_pham ──
    vi_pham = g("vi_pham") or []
    if vi_pham:
        lines.append("┌─ vi_pham[] breakdown ─┐")
        for i, v in enumerate(vi_pham[:5], 1):
            so_lieu = v.get("so_lieu") or {}
            tn = v.get("trach_nhiem") or {}
            lines.append(
                f"  [{i}] {v.get('hanh_vi_chuan'):30}  "
                f"lv={v.get('linh_vuc')}  "
                f"muc_do={v.get('muc_do')}  "
                f"hs={v.get('co_dau_hieu_hinh_su')}"
            )
            lines.append(f"        chu_the={(v.get('chu_the') or '')[:60]!r}")
            lines.append(f"        hanh_vi_chi_tiet={(v.get('hanh_vi_chi_tiet') or '')[:80]!r}")
            lines.append(f"        so_lieu: vnd={so_lieu.get('gia_tri_vnd')}  m2={so_lieu.get('dien_tich_dat_m2')}  qty={so_lieu.get('so_luong_don_vi')}")
            lines.append(f"        trach_nhiem: TT={len(tn.get('tap_the') or [])}  CN={len(tn.get('ca_nhan') or [])}  NDD={len(tn.get('nguoi_dung_dau') or [])}")
        if len(vi_pham) > 5:
            lines.append(f"  … {len(vi_pham) - 5} thêm")

    # ── breakdown kien_nghi ──
    kn = g("kien_nghi") or []
    if kn:
        lines.append("┌─ kien_nghi[] breakdown ─┐")
        for i, k in enumerate(kn[:5], 1):
            lines.append(
                f"  [{i}] loai={k.get('loai'):28}  "
                f"tinh_trang={k.get('tinh_trang')}  "
                f"vnd={k.get('gia_tri_vnd')}  "
                f"m2={k.get('dien_tich_dat_m2')}"
            )
            lines.append(f"        noi_dung={(k.get('noi_dung') or '')[:80]!r}")
            lines.append(f"        co_quan_thuc_hien={k.get('co_quan_thuc_hien')}")
        if len(kn) > 5:
            lines.append(f"  … {len(kn) - 5} thêm")

    # ── top-level aggregate ──
    tien = g("tien") or {}
    ns = g("nhan_su") or {}
    hs = g("hinh_su") or {}
    lines.append("┌─ Aggregate top-level ─┐")
    lines.append(f"  linh_vuc        : {g('linh_vuc')}")
    lines.append(f"  trang_thai      : {g('trang_thai_thuc_hien')!r}")
    lines.append(f"  tien            : kien_nghi_thu_hoi={tien.get('kien_nghi_thu_hoi')}  da_thu_hoi={tien.get('da_thu_hoi')}  tong_sai_pham={tien.get('tong_sai_pham')}")
    lines.append(f"  nhan_su         : kiem_diem={ns.get('kien_nghi_kiem_diem')}  ky_luat={ns.get('kien_nghi_ky_luat')}  khoi_to={ns.get('kien_nghi_khoi_to')}")
    lines.append(f"  hinh_su         : co_dau_hieu={hs.get('co_dau_hieu')}  da_chuyen_cqdt={hs.get('da_chuyen_cqdt')}  dieu_blhs={hs.get('dieu_blhs')}")

    # ── tóm tắt ──
    nd = g("noi_dung_chinh") or ""
    sp = g("sai_pham_chinh") or []
    if nd or sp:
        lines.append("┌─ Tóm tắt cho lãnh đạo ─┐")
        if nd:
            lines.append(f"  noi_dung_chinh: {nd[:200]}{'…' if len(nd) > 200 else ''}")
        if sp:
            lines.append("  sai_pham_chinh:")
            for s in sp[:7]:
                lines.append(f"    • {s[:120]}{'…' if len(s) > 120 else ''}")

    return "\n".join(lines)


# ── main loop ──────────────────────────────────────────────────────────────


async def _process_one(source: str, *, is_minio: bool) -> tuple[dict, float]:
    t0 = time.monotonic()
    loader = _load_minio if is_minio else _load_local
    pdf = await asyncio.to_thread(loader, source)
    raw = await process_pdf(pdf)
    result = validate_ttcp(raw)
    return result, time.monotonic() - t0


async def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("files", nargs="+", help="Đường dẫn PDF local hoặc MinIO key")
    p.add_argument("--minio", action="store_true",
                   help="Treat args as MinIO keys thay vì local paths")
    p.add_argument("--out", help="Ghi full kết quả (raw + canonical) ra JSON file")
    p.add_argument("--concurrent", type=int, default=1,
                   help="Số file xử lý song song (mặc định 1)")
    args = p.parse_args()

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    sem = asyncio.Semaphore(args.concurrent)

    async def _run(f: str) -> tuple[str, dict, float]:
        async with sem:
            try:
                result, elapsed = await _process_one(f, is_minio=args.minio)
            except Exception as exc:
                log.exception("processing %s failed", f)
                result = {
                    "raw_extract": None,
                    "canonical": None,
                    "valid": False,
                    "errors": [f"exception: {type(exc).__name__}: {exc}"],
                }
                elapsed = 0.0
            return f, result, elapsed

    coros = [_run(f) for f in args.files]
    results: dict[str, dict] = {}
    for coro in asyncio.as_completed(coros):
        f, result, elapsed = await coro
        results[f] = result
        print(_summarize(f, result, elapsed))

    # Final tally.
    valid = sum(1 for r in results.values() if r.get("valid"))
    print(f"\n{'═' * 78}")
    print(f"  Tổng: {valid}/{len(results)} valid")
    print(f"{'═' * 78}")

    if args.out:
        Path(args.out).write_text(
            json.dumps(results, ensure_ascii=False, indent=2, default=str)
        )
        log.info("wrote %s", args.out)


if __name__ == "__main__":
    asyncio.run(main())
