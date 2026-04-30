"""Pre-formatted Vietnamese output for the 3 fixed LIS queries.

Each public function takes raw DB rows (list[dict]) + capped flag and
returns a ready-to-display string. No LLM interpretation needed for the
80% common path.

Conventions:
- Flat-row queries (lookup_gcn_*): dedup sub-entities by their UUID column.
- Nested-JSON query (check_don_dang_ky): 1 row, camelCase, 4 nested arrays.
"""
from __future__ import annotations

import json
from datetime import date, datetime

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _maybe_json(val):
    """psycopg may return `json` columns as strings; jsonb is auto-decoded."""
    if isinstance(val, str):
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return None
    return val


def _fmt_date(val) -> str:
    if val is None:
        return "?"
    if isinstance(val, (date, datetime)):
        return val.strftime("%d/%m/%Y")
    return str(val)


def _fmt_area(val) -> str:
    if val is None:
        return "?"
    try:
        return f"{float(val):,.1f} m²".replace(",", ".")
    except (TypeError, ValueError):
        return str(val)


_LOAI_DOI_TUONG_LABEL: dict[int, str] = {
    1: "Cá nhân",
    2: "Tổ chức",
    3: "Hộ gia đình",
    4: "Vợ chồng",
    5: "Cộng đồng dân cư",
}

_CAPPED_NOTE = "\n\n*(Kết quả đã giới hạn 50 dòng — có thể còn thêm dữ liệu.)*"


# ---------------------------------------------------------------------------
# Tool A — lookup_gcn_by_so_hieu
# ---------------------------------------------------------------------------

def format_gcn_by_so_hieu(rows: list[dict], capped: bool = False) -> str:
    if not rows:
        return "Không tìm thấy GCN."

    r0 = rows[0]
    lines: list[str] = []

    # GCN header
    lines.append(f"**GCN: {r0.get('so_hieu_gcn', '?')}**")
    meta: list[str] = []
    if r0.get("loai_gcn"):
        meta.append(r0["loai_gcn"])
    if r0.get("tinh_trang_gcn"):
        meta.append(r0["tinh_trang_gcn"])
    if meta:
        lines.append(" | ".join(meta))
    if r0.get("so_ho_so_goc"):
        lines.append(f"Hồ sơ gốc: {r0['so_ho_so_goc']}")
    if r0.get("so_vao_so"):
        lines.append(
            f"Vào sổ: {r0['so_vao_so']} ngày {_fmt_date(r0.get('ngay_vao_so'))}"
        )
    if r0.get("ten_nguoi_ky"):
        lines.append(f"Người ký: {r0['ten_nguoi_ky']}")
    if r0.get("can_cu_phap_ly"):
        lines.append(f"Căn cứ pháp lý: {r0['can_cu_phap_ly']}")

    # Collect unique sub-entities (first row wins for each id)
    seen_pn:    dict[str, dict] = {}
    seen_td:    dict[str, dict] = {}
    seen_nha:   dict[str, dict] = {}
    seen_ctxd:  dict[str, dict] = {}
    seen_paper: dict[str, dict] = {}

    for row in rows:
        for key, store in (
            ("phap_nhan_id", seen_pn),
            ("thua_dat_id",  seen_td),
            ("nha_id",       seen_nha),
            ("ctxd_id",      seen_ctxd),
        ):
            v = row.get(key)
            if v and v not in store:
                store[v] = row
        fp = row.get("file_scan_path")
        if fp and fp not in seen_paper:
            seen_paper[fp] = row

    # Chủ sở hữu
    if seen_pn:
        lines.append(f"\n**Chủ sở hữu ({len(seen_pn)}):**")
        for row in seen_pn.values():
            loai = row.get("loai_doi_tuong")
            if loai == 1:
                name = row.get("ho_ten") or "?"
                info: list[str] = []
                if row.get("ngay_sinh"):
                    info.append(f"sinh {_fmt_date(row['ngay_sinh'])}")
                if row.get("gioi_tinh") is not None:
                    info.append("Nam" if row["gioi_tinh"] else "Nữ")
                if row.get("dia_chi_chu"):
                    info.append(row["dia_chi_chu"])
                lines.append(
                    f"  Cá nhân: **{name}**"
                    + (f" ({', '.join(info)})" if info else "")
                )
            elif loai == 2:
                name = row.get("ten_to_chuc") or "?"
                msdn = row.get("ma_so_doanh_nghiep") or ""
                lines.append(
                    f"  Tổ chức: **{name}**"
                    + (f" (MSDN: {msdn})" if msdn else "")
                )
            else:
                lines.append(f"  Chủ (loại {loai})")

    # Thửa đất
    if seen_td:
        lines.append(f"\n**Thửa đất ({len(seen_td)}):**")
        for row in seen_td.values():
            so_to    = row.get("so_hieu_to_ban_do") or "?"
            so_thua  = row.get("so_thu_tu_thua") or "?"
            dt_dd    = row.get("dien_tich")
            dt_pl    = row.get("dien_tich_phap_ly")
            muc_dich = row.get("muc_dich_su_dung") or ""
            nguon_goc= row.get("ten_nguon_goc_sdd") or ""
            thoi_han = row.get("thoi_han_su_dung") or ""
            ngay_het = row.get("ngay_het_han_su_dung")
            dia_chi  = row.get("dia_chi_thua_dat") or ""
            ten_xa   = row.get("ten_xa") or ""

            desc = f"  Tờ {so_to}, thửa {so_thua}"
            if dt_dd:
                desc += f" — đo đạc {_fmt_area(dt_dd)}"
            if dt_pl and dt_pl != dt_dd:
                desc += f", pháp lý {_fmt_area(dt_pl)}"
            lines.append(desc)

            detail: list[str] = []
            if muc_dich:
                detail.append(f"Mục đích: {muc_dich}")
            if nguon_goc:
                detail.append(f"Nguồn gốc: {nguon_goc}")
            if thoi_han:
                detail.append(
                    f"Thời hạn: {thoi_han}"
                    + (f" (hết {_fmt_date(ngay_het)})" if ngay_het else "")
                )
            location = ", ".join(filter(None, [dia_chi, ten_xa]))
            if location:
                detail.append(f"Vị trí: {location}")
            for d in detail:
                lines.append(f"    {d}")

    # Nhà
    if seen_nha:
        lines.append(f"\n**Tài sản — Nhà ({len(seen_nha)}):**")
        for row in seen_nha.values():
            so_nha  = row.get("so_nha") or "?"
            dt_san  = row.get("dien_tich_san")
            dt_xd   = row.get("dien_tich_xay_dung")
            so_tang = row.get("so_tang")
            nam_xd  = row.get("nam_xay_dung")
            ket_cau = row.get("ket_cau_nha") or ""
            loai_cap= row.get("ten_loai_cap_nha") or ""

            parts: list[str] = []
            if so_tang: parts.append(f"{so_tang} tầng")
            if dt_san:  parts.append(f"sàn {_fmt_area(dt_san)}")
            if dt_xd:   parts.append(f"xây dựng {_fmt_area(dt_xd)}")
            if ket_cau: parts.append(ket_cau)
            if loai_cap:parts.append(loai_cap)
            if nam_xd:  parts.append(f"năm XD: {nam_xd}")
            lines.append(
                f"  Số {so_nha}" + (f" ({', '.join(parts)})" if parts else "")
            )

    # Công trình xây dựng
    if seen_ctxd:
        lines.append(f"\n**Tài sản — Công trình XD ({len(seen_ctxd)}):**")
        for row in seen_ctxd.values():
            ten = row.get("ten_cong_trinh") or "?"
            dt  = row.get("dt_ctxd")
            lines.append(f"  {ten}" + (f" ({_fmt_area(dt)})" if dt else ""))

    # File scan
    if seen_paper:
        lines.append(f"\n**File scan ({len(seen_paper)}):**")
        for row in seen_paper.values():
            fname = row.get("file_scan_name") or row.get("file_scan_path") or "?"
            lines.append(f"  {fname}")
    elif r0.get("so_gcn_quet"):
        lines.append(f"\nHồ sơ quét: số {r0['so_gcn_quet']} (chưa có file scan)")

    # Ghi chú trang 1
    ghi_chu = next(
        (r["ghi_chu_trang1"] for r in rows if r.get("ghi_chu_trang1")), None
    )
    if ghi_chu:
        lines.append(f"\n**Ghi chú:** {ghi_chu}")

    if capped:
        lines.append(_CAPPED_NOTE)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool B — lookup_gcn_by_giay_to_dinh_danh
# ---------------------------------------------------------------------------

def format_gcn_by_giay_to_dinh_danh(rows: list[dict], capped: bool = False) -> str:
    if not rows:
        return "Không tìm thấy GCN nào gắn với số giấy tờ này."

    r0 = rows[0]
    lines: list[str] = []

    # Thông tin giấy tờ + chủ
    ten_chu  = r0.get("ten_chu") or "?"
    so_gt    = r0.get("so_giay_to") or "?"
    loai_gt  = r0.get("loai_giay_to") or ""
    ngay_cap = r0.get("ngay_cap")
    noi_cap  = r0.get("noi_cap") or ""

    lines.append(f"**Chủ sở hữu: {ten_chu}**")
    gt_parts = [so_gt]
    if loai_gt:  gt_parts.append(loai_gt)
    if ngay_cap: gt_parts.append(f"cấp {_fmt_date(ngay_cap)}")
    if noi_cap:  gt_parts.append(f"tại {noi_cap}")
    lines.append("Giấy tờ: " + " | ".join(gt_parts))

    # Group rows by gcn_id
    seen_gcn:    dict[str, dict]        = {}
    gcn_td_keys: dict[str, set[tuple]]  = {}   # dedup thửa by (tờ, thửa)
    gcn_tds:     dict[str, list[dict]]  = {}
    gcn_papers:  dict[str, list[str]]   = {}

    for row in rows:
        gcn_id = row.get("gcn_id")
        if not gcn_id:
            continue
        if gcn_id not in seen_gcn:
            seen_gcn[gcn_id]    = row
            gcn_td_keys[gcn_id] = set()
            gcn_tds[gcn_id]     = []
            gcn_papers[gcn_id]  = []

        td_key = (row.get("so_hieu_to_ban_do"), row.get("so_thu_tu_thua"))
        if any(v is not None for v in td_key) and td_key not in gcn_td_keys[gcn_id]:
            gcn_td_keys[gcn_id].add(td_key)
            gcn_tds[gcn_id].append(row)

        fp = row.get("file_scan_path")
        if fp and fp not in gcn_papers[gcn_id]:
            gcn_papers[gcn_id].append(fp)

    lines.append(f"\n**Tìm thấy {len(seen_gcn)} GCN:**")

    for i, (gcn_id, row) in enumerate(seen_gcn.items(), 1):
        so_hieu    = row.get("so_hieu_gcn") or "?"
        tinh_trang = row.get("tinh_trang_gcn") or ""
        loai_gcn   = row.get("loai_gcn") or ""
        so_vao_so  = row.get("so_vao_so") or ""
        ngay_vs    = row.get("ngay_vao_so")

        hdr = f"\n**{i}. GCN {so_hieu}**"
        if tinh_trang: hdr += f" — {tinh_trang}"
        lines.append(hdr)

        if loai_gcn:  lines.append(f"   Loại: {loai_gcn}")
        if so_vao_so:
            vao_so = f"   Vào sổ: {so_vao_so}"
            if ngay_vs: vao_so += f" ngày {_fmt_date(ngay_vs)}"
            lines.append(vao_so)

        # Thửa đất của GCN này
        thuas = gcn_tds[gcn_id]
        if thuas:
            lines.append(f"   **Thửa đất ({len(thuas)}):**")
            for td in thuas:
                so_to    = td.get("so_hieu_to_ban_do") or "?"
                so_thua  = td.get("so_thu_tu_thua") or "?"
                dt       = td.get("dien_tich") or td.get("dien_tich_phap_ly")
                muc_dich = td.get("muc_dich_su_dung") or ""
                thoi_han = td.get("thoi_han_su_dung") or ""
                ngay_het = td.get("ngay_het_han_su_dung")
                dia_chi  = td.get("dia_chi_thua_dat") or ""
                ten_xa   = td.get("ten_xa") or ""

                desc = f"     Tờ {so_to}, thửa {so_thua}"
                if dt: desc += f" — {_fmt_area(dt)}"
                if muc_dich: desc += f" ({muc_dich})"
                if thoi_han:
                    desc += f" | Thời hạn: {thoi_han}"
                    if ngay_het: desc += f" (hết {_fmt_date(ngay_het)})"
                location = ", ".join(filter(None, [dia_chi, ten_xa]))
                if location: desc += f"\n       Vị trí: {location}"
                lines.append(desc)

        papers = gcn_papers[gcn_id]
        if papers:
            lines.append(f"   File scan: {len(papers)} file(s)")

    if capped:
        lines.append(_CAPPED_NOTE)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool C — check_don_dang_ky
# ---------------------------------------------------------------------------

def _pn_name(pn: dict) -> str:
    """Extract display name from a phapNhanSdd object."""
    loai = pn.get("loaiDoiTuong")
    try:
        loai = int(loai)
    except (TypeError, ValueError):
        pass

    if loai == 1 and pn.get("caNhan"):
        return pn["caNhan"].get("hoTen") or "?"
    if loai == 2 and pn.get("toChuc"):
        return pn["toChuc"].get("tenToChuc") or "?"
    if loai == 3 and pn.get("hoGiaDinh"):
        chu_ho = pn["hoGiaDinh"].get("chuHo") or {}
        return f"Hộ {chu_ho.get('hoTen', '?')}"
    if loai == 4 and pn.get("voChong"):
        vc = pn["voChong"]
        n1 = (vc.get("nguoiThuNhat") or {}).get("hoTen", "?")
        n2 = (vc.get("nguoiThuHai") or {}).get("hoTen", "?")
        return f"{n1} & {n2}"
    if loai == 5 and pn.get("congDongDanCu"):
        return pn["congDongDanCu"].get("tenCongDong") or "?"
    return "?"


def format_don_dang_ky(rows: list[dict], capped: bool = False) -> str:
    if not rows:
        return "Không tìm thấy đơn đăng ký."

    row = rows[0]

    def _j(key):
        return _maybe_json(row.get(key)) or []

    lines: list[str] = []

    # Header
    ma_don = row.get("maDon") or row.get("id") or "?"
    lines.append(f"**Đơn đăng ký: {ma_don}**")
    if row.get("maHoSoLuu"):
        lines.append(f"Hồ sơ lưu: {row['maHoSoLuu']}")
    if row.get("maVach"):
        lines.append(f"Mã vạch: {row['maVach']}")
    if row.get("ngayDangKy"):
        lines.append(f"Ngày đăng ký: {_fmt_date(row['ngayDangKy'])}")
    da_dk = row.get("daDangKy")
    if da_dk is not None:
        lines.append(f"Đã đăng ký: {'Có' if da_dk else 'Chưa'}")
    if row.get("dongSuDung"):
        lines.append("Đồng sử dụng: Có")

    phap_nhans = _j("phapNhanSdds")
    thua_dats  = _j("thuaDats")
    da_mdsdds  = _j("daMdsdds")
    gcns       = _j("giayChungNhans")

    ok = all([phap_nhans, thua_dats, da_mdsdds, gcns])
    lines.append(
        f"\nTình trạng: {'✓ Đầy đủ 4 nhóm' if ok else '⚠ Thiếu dữ liệu'}"
    )

    # Pháp nhân
    if phap_nhans:
        lines.append(f"\n**Pháp nhân ({len(phap_nhans)}):**")
        for pn in phap_nhans:
            loai_raw = pn.get("loaiDoiTuong")
            try:
                loai_int = int(loai_raw)
            except (TypeError, ValueError):
                loai_int = -1
            label = _LOAI_DOI_TUONG_LABEL.get(loai_int, f"Loại {loai_raw}")
            name  = _pn_name(pn)
            lines.append(f"  {label}: **{name}**")
    else:
        lines.append("\n**Pháp nhân:** ✗ chưa có")

    # Thửa đất
    if thua_dats:
        lines.append(f"\n**Thửa đất ({len(thua_dats)}):**")
        for td in thua_dats:
            so_to   = td.get("soHieuToBanDo") or "?"
            so_thua = td.get("soThuTuThua") or "?"
            dt      = td.get("dienTich") or td.get("dienTichPhapLy")
            dia_chi = td.get("diaChi") or ""
            desc = f"  Tờ {so_to}, thửa {so_thua}"
            if dt:      desc += f" — {_fmt_area(dt)}"
            if dia_chi: desc += f" | {dia_chi}"
            lines.append(desc)
    else:
        lines.append("\n**Thửa đất:** ✗ chưa có")

    # Mục đích sử dụng đất
    if da_mdsdds:
        lines.append(f"\n**Mục đích sử dụng ({len(da_mdsdds)}):**")
        for m in da_mdsdds:
            loai_md  = m.get("loaiMdsdd") or {}
            ten_md   = loai_md.get("tenMucDich") or loai_md.get("tenDayDu") or "?"
            dt       = m.get("dienTich")
            lau_dai  = m.get("thoiHanSuDungLauDai")
            thoi_han = m.get("thoiHanSuDung") or ""
            ngay_het = m.get("ngayHetHanSuDung")

            desc = f"  {ten_md}"
            if dt: desc += f" — {_fmt_area(dt)}"
            if lau_dai:
                desc += " (lâu dài)"
            elif thoi_han:
                desc += f" ({thoi_han}"
                if ngay_het: desc += f", hết {_fmt_date(ngay_het)}"
                desc += ")"
            lines.append(desc)
    else:
        lines.append("\n**Mục đích sử dụng:** ✗ chưa có")

    # GCN
    if gcns:
        lines.append(f"\n**Giấy chứng nhận ({len(gcns)}):**")
        for g in gcns:
            so_hieu    = g.get("soHieuGcn") or "?"
            tinh_trang = g.get("tinhTrangGcn") or ""
            so_vs      = g.get("soVaoSo") or ""
            ngay_vs    = g.get("ngayVaoSo")
            hsq        = g.get("hoSoQuets") or []
            n_papers   = sum(len(h.get("papers") or []) for h in hsq)

            desc = f"  GCN {so_hieu}"
            if tinh_trang: desc += f" — {tinh_trang}"
            if so_vs:
                desc += f" | vào sổ {so_vs}"
                if ngay_vs: desc += f" ngày {_fmt_date(ngay_vs)}"
            if n_papers:   desc += f" | {n_papers} file scan"
            lines.append(desc)
    else:
        lines.append("\n**Giấy chứng nhận:** ✗ chưa có")

    if not ok:
        lines.append("\n→ Dùng `/status <id>` để xem báo cáo kiểm tra chi tiết.")

    return "\n".join(lines)
