"""63 tỉnh/thành Việt Nam — canonical names + alias map.

Dùng để chuẩn hoá field ``dia_phuong`` trong TTCP records. VLM hay viết
"TP.HCM", "Tp. Hồ Chí Minh", "HCM", "Saigon"… → ``canonicalize`` quy về
"TP. Hồ Chí Minh" để Mongo group-by ra số sạch.

5 TP trực thuộc trung ương kèm prefix "TP. " trong canonical name; 58 tỉnh
còn lại không có prefix. Khớp với cách lãnh đạo hay viết trong văn bản.
"""
from __future__ import annotations

import unicodedata
from typing import Optional


# Canonical list. KHÔNG đổi spelling — bảng này là single source of truth.
PROVINCES: list[str] = [
    # 5 thành phố trực thuộc trung ương
    "TP. Hà Nội", "TP. Hải Phòng", "TP. Đà Nẵng", "TP. Hồ Chí Minh", "TP. Cần Thơ",

    # Miền núi & trung du phía Bắc (14)
    "Hà Giang", "Cao Bằng", "Bắc Kạn", "Tuyên Quang", "Lào Cai", "Điện Biên",
    "Lai Châu", "Sơn La", "Yên Bái", "Hòa Bình", "Thái Nguyên", "Lạng Sơn",
    "Bắc Giang", "Phú Thọ",

    # Đồng bằng sông Hồng (8, không kể HN + HP)
    "Vĩnh Phúc", "Bắc Ninh", "Hải Dương", "Hưng Yên", "Thái Bình",
    "Hà Nam", "Nam Định", "Ninh Bình", "Quảng Ninh",

    # Bắc Trung Bộ & duyên hải miền Trung (13, không kể ĐN)
    "Thanh Hóa", "Nghệ An", "Hà Tĩnh", "Quảng Bình", "Quảng Trị",
    "Thừa Thiên Huế", "Quảng Nam", "Quảng Ngãi", "Bình Định", "Phú Yên",
    "Khánh Hòa", "Ninh Thuận", "Bình Thuận",

    # Tây Nguyên (5)
    "Kon Tum", "Gia Lai", "Đắk Lắk", "Đắk Nông", "Lâm Đồng",

    # Đông Nam Bộ (5, không kể HCM)
    "Bình Phước", "Tây Ninh", "Bình Dương", "Đồng Nai", "Bà Rịa - Vũng Tàu",

    # Đồng bằng sông Cửu Long (12, không kể CT)
    "Long An", "Tiền Giang", "Bến Tre", "Trà Vinh", "Vĩnh Long",
    "Đồng Tháp", "An Giang", "Kiên Giang", "Hậu Giang", "Sóc Trăng",
    "Bạc Liêu", "Cà Mau",
]
assert len(PROVINCES) == 63, f"expected 63 provinces, got {len(PROVINCES)}"


# Cách viết khác nhau lãnh đạo / VLM có thể dùng → canonical.
# Key sẽ được normalize qua ``_norm`` trước khi tra cứu nên không cần lo
# về dấu / case / khoảng trắng.
_ALIASES: dict[str, str] = {
    # TP. Hồ Chí Minh
    "ho chi minh": "TP. Hồ Chí Minh",
    "hcm": "TP. Hồ Chí Minh",
    "tphcm": "TP. Hồ Chí Minh",
    "tp hcm": "TP. Hồ Chí Minh",
    "sai gon": "TP. Hồ Chí Minh",
    "saigon": "TP. Hồ Chí Minh",
    # Hà Nội
    "ha noi": "TP. Hà Nội",
    "hn": "TP. Hà Nội",
    # Hải Phòng
    "hai phong": "TP. Hải Phòng",
    # Đà Nẵng
    "da nang": "TP. Đà Nẵng",
    # Cần Thơ
    "can tho": "TP. Cần Thơ",
    # Thừa Thiên Huế
    "hue": "Thừa Thiên Huế",
    "thua thien-hue": "Thừa Thiên Huế",
    "tt-hue": "Thừa Thiên Huế",
    "tt hue": "Thừa Thiên Huế",
    # Bà Rịa - Vũng Tàu
    "ba ria vung tau": "Bà Rịa - Vũng Tàu",
    "br-vt": "Bà Rịa - Vũng Tàu",
    "brvt": "Bà Rịa - Vũng Tàu",
    "vung tau": "Bà Rịa - Vũng Tàu",
    # Đắk Lắk / Đắk Nông — historic spelling Đắc
    "dac lac": "Đắk Lắk",
    "daklak": "Đắk Lắk",
    "dac nong": "Đắk Nông",
}


def _norm(s: str) -> str:
    """Lowercase + strip diacritics + strip TP/tỉnh prefix + collapse spaces.

    "Tp. Hồ Chí Minh" → "ho chi minh"; "Tỉnh Hà Tĩnh" → "ha tinh".
    """
    if not s:
        return ""
    # NFD splits "đ" → "d" + ◌, "ă" → "a" + ◌; strip combining marks.
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    # "đ" doesn't decompose — special-case.
    s = s.replace("đ", "d").replace("Đ", "d")
    s = s.lower().strip().strip(".,;:")
    # Strip leading admin prefix variants.
    for prefix in ("tp.", "tp ", "thanh pho ", "tinh ", "t.", "t "):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    return " ".join(s.split())


# Pre-built lookup: normalized form → canonical. Built once at import.
_LOOKUP: dict[str, str] = {}
for canonical in PROVINCES:
    _LOOKUP[_norm(canonical)] = canonical
for alias, canonical in _ALIASES.items():
    _LOOKUP[_norm(alias)] = canonical


def canonicalize(name: str) -> Optional[str]:
    """Quy 1 tên tỉnh/TP về canonical. Trả ``None`` nếu không match."""
    if not name:
        return None
    return _LOOKUP.get(_norm(name))


def canonicalize_list(names: list[str]) -> list[str]:
    """Map a list of names → canonical, dedupe, drop None. Preserves order."""
    seen: set[str] = set()
    out: list[str] = []
    for n in names or []:
        c = canonicalize(n)
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out
