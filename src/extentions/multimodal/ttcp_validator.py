"""Validate VLM output against ``TTCPRecord`` — warning-only mode.

Never raises. Always returns a dict that downstream code can store / inspect:

    {
      "raw_extract": dict | str,    # JSON object if parseable; raw text if not
      "canonical":   dict | None,   # model_dump(mode="json") khi validate OK
      "valid":       bool,
      "errors":      list[str],     # 1 dòng / lỗi validation; [] nếu OK
    }

Side-effects trước validation:
- canonicalize ``dia_phuong`` qua bảng 63 tỉnh (xem ``vn_provinces``)
- KHÔNG patch các field khác — invalid là invalid, fix ở prompt / re-extract.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from src.extentions.multimodal.ttcp_schema import TTCPRecord
from src.extentions.multimodal.vn_provinces import canonicalize_list

log = logging.getLogger(__name__)


def validate_ttcp(raw: str | dict) -> dict[str, Any]:
    """Parse → canonicalize → validate. See module docstring for shape."""
    # 1) parse JSON
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            return {
                "raw_extract": raw,
                "canonical": None,
                "valid": False,
                "errors": [f"json_parse: {e}"],
            }
    else:
        data = raw

    if not isinstance(data, dict):
        return {
            "raw_extract": data,
            "canonical": None,
            "valid": False,
            "errors": [f"not_dict: got {type(data).__name__}"],
        }

    # 2) canonicalize tỉnh in-place — chạy trước validate để dù invalid vẫn
    #    có data đẹp ở raw_extract cho aggregation thô.
    if isinstance(data.get("dia_phuong"), list):
        data["dia_phuong"] = canonicalize_list(data["dia_phuong"])

    # 3) pydantic validate
    try:
        record = TTCPRecord(**data)
    except ValidationError as exc:
        errors = [
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        ]
        log.warning(
            "TTCP validation failed (%d errors). First 3: %s",
            len(errors), errors[:3],
        )
        return {
            "raw_extract": data,
            "canonical": None,
            "valid": False,
            "errors": errors,
        }

    return {
        "raw_extract": data,
        "canonical": record.model_dump(mode="json"),
        "valid": True,
        "errors": [],
    }
