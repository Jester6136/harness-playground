"""Create / update an account in MongoDB.

Accounts live in Mongo (``AUTH_USERS_COLLECTION``). Each carries the
per-tenant overrides — Mongo collection, MinIO prefix, DataLens chatbot
code, etc. — that the harness's :mod:`harness.tenant` reads per request.

Usage::

    python -m harness.useradd <username> [--password PW]
        [--ttcp-collection ttcp-extracted-v3]
        [--ttcp-prefix     ttcp/ttcp_hs_16_05]
        [--datalens-code   ttcp-hs]
        [--ttcp-bucket     datalens-data]
        [--ttcp-sync-url   ''   # '' disables the webhook for this account]
        [--label           "Sếp Thái (private)"]

    python -m harness.useradd --list
    python -m harness.useradd --disable <user>
    python -m harness.useradd --enable  <user>

Any --xxx-yyy flag you omit → the account inherits the global env value at
request time (so an account that's content with the defaults can be
created with just `python -m harness.useradd alice --password ...`).
"""
from __future__ import annotations

import argparse
import getpass
import sys

from dotenv import load_dotenv

load_dotenv()

from harness.auth import _users, upsert_user  # noqa: E402


def _list() -> None:
    rows = list(_users().find({}, {"password": 0}))
    if not rows:
        print("(chưa có tài khoản nào)")
        return
    for r in rows:
        flag = " [DISABLED]" if r.get("disabled") else ""
        cfg = r.get("config") or {}
        bits = ", ".join(f"{k}={v}" for k, v in cfg.items() if v != "")
        label = f"  {r.get('label','')}" if r.get("label") else ""
        print(f"  {r['_id']:<24}{flag}{label}")
        if bits:
            print(f"      {bits}")


def main() -> None:
    p = argparse.ArgumentParser(description="Quản lý tài khoản (Mongo)")
    p.add_argument("username", nargs="?", help="Tên đăng nhập")
    p.add_argument("--password", help="Mật khẩu (bỏ trống → hỏi ẩn)")
    p.add_argument("--label", default="", help="Nhãn hiển thị (tuỳ chọn)")
    # Per-tenant overrides — bỏ trống = thừa kế env mặc định lúc request.
    p.add_argument("--ttcp-collection")
    p.add_argument("--ttcp-prefix")
    p.add_argument("--datalens-code", dest="datalens_chatbot_code")
    p.add_argument("--ttcp-bucket")
    p.add_argument("--ttcp-sync-url",
                   help="Đặt '' (rỗng) để TẮT webhook sync cho account này")
    # Admin ops.
    p.add_argument("--list", action="store_true", help="Liệt kê tài khoản")
    p.add_argument("--disable", metavar="USER", help="Vô hiệu hoá một tài khoản")
    p.add_argument("--enable", metavar="USER", help="Bật lại một tài khoản")
    args = p.parse_args()

    if args.list:
        _list()
        return

    if args.disable or args.enable:
        target = args.disable or args.enable
        res = _users().update_one(
            {"_id": target}, {"$set": {"disabled": bool(args.disable)}}
        )
        if res.matched_count == 0:
            print(f"✗ không tìm thấy tài khoản '{target}'")
            sys.exit(1)
        print(f"✓ {'vô hiệu hoá' if args.disable else 'bật lại'} '{target}'")
        return

    if not args.username:
        p.error("cần <username> (hoặc dùng --list / --disable / --enable)")
    if "|" in args.username:
        p.error("username không được chứa ký tự '|'")

    password = args.password or getpass.getpass(f"Mật khẩu cho '{args.username}': ")
    if not password:
        p.error("mật khẩu rỗng")

    config: dict = {}
    for k in ("ttcp_collection", "ttcp_prefix", "datalens_chatbot_code",
              "ttcp_bucket", "ttcp_sync_url"):
        v = getattr(args, k)
        if v is not None:
            config[k] = v

    upsert_user(args.username, password, config=config, label=args.label)
    print(f"✓ đã lưu tài khoản '{args.username}'")
    if config:
        for k, v in config.items():
            print(f"      {k} = {v!r}")
    else:
        print("  (không có override — sẽ dùng env mặc định)")


if __name__ == "__main__":
    main()
