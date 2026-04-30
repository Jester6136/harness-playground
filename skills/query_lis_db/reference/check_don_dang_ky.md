# Schema — `check_don_dang_ky`

Snapshot 1 đơn đăng ký theo UUID. Trả `{rows: [{...}], count: 1}` — **luôn 1 row** với 4 nested array. Toàn bộ field dùng **camelCase** (do ORM-generated, khác với các tool flat snake_case).

## Top-level (đơn đăng ký)

| Trường | Ý nghĩa |
|---|---|
| `id` | UUID đơn |
| `xaId` | UUID xã |
| `daiDienKhaiTrinhId` | UUID đại diện khai trình |
| `maDon` | Mã đơn |
| `maHoSoLuu` | Mã hồ sơ lưu |
| `maVach` | Mã vạch |
| `dongSuDung` | Đồng sử dụng (bool) |
| `daDangKy` | Đã đăng ký (bool) |
| `ngayDangKy` | Ngày đăng ký |
| `capGiayNguoiDaiDien`, `kieuGiayNguoiDaiDien` | Cấp / kiểu giấy người đại diện |
| `daiDienCapGiayId` | UUID đại diện cấp giấy |

## `phapNhanSdds[]` — chủ sở hữu

Mỗi phần tử có `id`, `doiTuongSddId`, `loaiDoiTuong` (1=cá nhân, 2=tổ chức, 3=hộ gia đình, 4=vợ chồng, 5=cộng đồng dân cư) + **đúng 1 trong 5 nested object** sau non-null tuỳ `loaiDoiTuong`:

### `caNhan` (nếu `loaiDoiTuong = 1`)

```
{ id, loaiDoiTuongSddId, quocTichId, danTocId, gioiTinh,
  hoTen, namSinh, ngaySinh, diaChi, maSoThue,
  giayToPhapNhan: [...] }
```

### `hoGiaDinh` (nếu `loaiDoiTuong = 3`)

```
{ id, chuHoId, voChongChuHoId, inHoOngBa,
  chuHo: { ...cá nhân nested... } }
```

Chú ý: `chuHo` là object cá nhân nested, có riêng `giayToPhapNhan[]`.

### `voChong` (nếu `loaiDoiTuong = 4`)

```
{ id, nguoiThuNhatId, nguoiThuHaiId,
  nguoiThuNhat: { ...cá nhân nested... },
  nguoiThuHai:  { ...cá nhân nested... } }
```

Cả 2 người đều có `giayToPhapNhan[]` riêng.

### `toChuc` (nếu `loaiDoiTuong = 2`)

```
{ id, loaiDoiTuongSddId, tenToChuc, tenVietTat, tenToChucTa,
  nguoiDaiDienId, maSoDoanhNghiep, maSoThue, diaChi, ghiChu,
  giayToPhapNhan: [...] }
```

### `congDongDanCu` (nếu `loaiDoiTuong = 5`)

```
{ id, loaiDoiTuongSddId, tenCongDong, nguoiDaiDienId, diaChi, ghiChu,
  giayToPhapNhan: [...] }
```

### `giayToPhapNhan[]` (nested trong cá nhân/tổ chức/cộng đồng)

CMND/CCCD/MST/hộ chiếu của chủ.

| Trường | Ý nghĩa |
|---|---|
| `id` | UUID |
| `doiTuongSoHuuGiayToId` | UUID người sở hữu giấy |
| `loaiGiayTo` | Loại (CMND / CCCD / hộ chiếu / MST / ...) |
| `soGiayTo` | Số giấy tờ |
| `ngayCap`, `ngayHetHan`, `noiCap` | Ngày / nơi cấp |
| `ghiChu` | Ghi chú |

## `thuaDats[]` — thửa đất

| Trường | Ý nghĩa |
|---|---|
| `id` | UUID thửa đất |
| `xaId` | UUID xã |
| `taiLieuDoDacId` | UUID tài liệu đo đạc |
| `soHieuToBanDo`, `soThuTuThua` | Số tờ / số thửa hiện tại |
| `soHieuToBanDoCu`, `soThuTuThuaCu` | Số tờ / số thửa cũ |
| `dienTich` | Diện tích đo đạc (m²) |
| `dienTichPhapLy` | Diện tích pháp lý (m²) |
| `dienTichBanDo` | Diện tích trên bản đồ (m²) |
| `diaChi` | Địa chỉ thửa |
| `laToThua2Cap` | Cờ tờ thửa 2 cấp |

## `daMdsdds[]` — đăng ký mục đích sử dụng đất

| Trường | Ý nghĩa |
|---|---|
| `id` | UUID đăng ký mục đích |
| `thuaDatId` | UUID thửa đất gắn với |
| `loaiMdsddId` | FK loại mục đích |
| `dienTich` | Diện tích cho mục đích này (m²) |
| `suDungChung` | Cờ sử dụng chung |
| `thoiHanSuDung` | Thời hạn (date hoặc text) |
| `ngayHetHanSuDung` | Ngày hết hạn |
| `thoiHanSuDungLauDai` | Cờ "lâu dài" (true → không có hạn) |
| `loaiMdsdd` | Object nested: `{ id, kyHieuMucDich, kyHieuBangSo, tenMucDich, tenDayDu }` |

## `giayChungNhans[]` — GCN liên quan đơn

| Trường | Ý nghĩa |
|---|---|
| `id`, `xaId`, `loaiGcnId` | UUID GCN / xã / loại GCN |
| `hinhThucSoHuu` | Hình thức sở hữu |
| `daCongNhanPhapLy` | Cờ đã công nhận pháp lý |
| `tinhTrangGcn` | Trạng thái |
| `maVach` | Mã vạch |
| `soHieuGcn`, `soHoSoGoc`, `soVaoSo`, `ngayVaoSo` | Định danh hiện tại |
| `soHoSoGocCu`, `soVaoSoCu`, `ngayVaoSoCu` | Phiên bản cũ |
| `canCuPhapLy`, `donViCap`, `uyQuyenKy`, `kyThay`, `tenNguoiKy` | Pháp lý + ký |
| `ghiChuTrang1` ... `ghiChuTrang4` | Ghi chú 4 trang |
| `hoSoQuets[]` | Mảng hồ sơ quét → xem dưới |

### `hoSoQuets[]` — hồ sơ quét gắn GCN

| Trường | Ý nghĩa |
|---|---|
| `id`, `dsHoSoQuetId`, `xaId` | UUID hồ sơ |
| `soHoSo`, `soBienNhan` | Số hồ sơ / biên nhận |
| `loaiGcnId`, `soGcn`, `ngayCap` | Khớp với GCN |
| `nenBanDo` | Nền bản đồ |
| `soHoSoGoc`, `khoHoSo`, `dayHoSo`, `hopHoSo`, `viTriHoSo` | Vị trí lưu trữ vật lý |
| `ghiChu` | Ghi chú |
| `soVaoSo`, `hoTen`, `soCmnd` | Snapshot info |
| `soVaoSoCu`, `ngayVaoSoCu`, `soHoSoGocCu` | Phiên bản cũ |
| `giayMoiNhat` | Cờ giấy mới nhất |
| `papers[]` | Mảng file scan vật lý → xem dưới |

### `papers[]` — file scan vật lý

| Trường | Ý nghĩa |
|---|---|
| `id`, `hoSoQuetId` | UUID |
| `thuTuSapXep` | Thứ tự sắp xếp |
| `fileType` | Loại file (pdf/jpg/...) |
| `fileName` | Tên file |
| `filePath` | Đường dẫn file scan |
