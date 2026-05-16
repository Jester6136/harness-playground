# Quản lý & Sử dụng Bot

> Hệ thống tra cứu kết luận thanh tra — một tiến trình duy nhất, login đa tài
> khoản, mỗi tài khoản gắn một "profile" cấu hình riêng (collection / prefix /
> DataLens code). File này gom mọi thứ cần biết để vận hành.

---

## 1. Khởi chạy nhanh

```bash
# Cài đặt (1 lần)
pip install -e .

# Chạy server (1 lệnh duy nhất)
python main.py --serve --host 0.0.0.0 --port 8000
```

Mở trình duyệt vào `http://<host>:8000/ui` → bị đá sang `/login` → đăng nhập:

| Tài khoản mặc định | Mật khẩu |
|---|---|
| `bags` | `bags111` |

Account này **tự tạo lần đầu khởi động** nếu collection `accounts` còn rỗng, và
dùng env mặc định (`TTCP_COLLECTION`, `TTCP_PREFIX`, `DATALENS_CHATBOT_CODE`).

> **Production:** đổi mật khẩu mặc định ngay (xem mục 3), và đặt
> `AUTH_SECRET` trong `.env` (nếu bỏ trống, mỗi lần restart sẽ logout hết).

---

## 2. Cơ chế đa tài khoản (multi-tenant)

Một tiến trình harness phục vụ nhiều tài khoản. Mỗi account doc trong Mongo:

```jsonc
{
  "_id": "alice",
  "password": "scrypt$...",
  "label": "Phòng nội bộ",
  "disabled": false,
  "config": {
    "ttcp_collection": "ttcp-extracted-v3",
    "ttcp_prefix":     "ttcp/ttcp_hs_16_05",
    "datalens_chatbot_code": "ttcp-hs",
    "ttcp_bucket":     "datalens-data",
    "ttcp_sync_url":   ""
  }
}
```

Mỗi request:
1. Cookie `hp_session` (đã ký HMAC) → xác định account.
2. App load account doc → build `Tenant` từ `config`.
3. Set `ContextVar` cho request → mọi tool (`find_ttcp`, `save_ttcp`,
   `render_ttcp_report`, `search_docs`, `/upload`, `/files`...) đọc đúng
   collection / prefix / DataLens code của account.

**Trường nào không khai trong `config`** → tự thừa kế env (`settings.*`).
Tài khoản chỉ cần override những gì khác mặc định.

| Field trong `config` | Env tương đương | Vai trò |
|---|---|---|
| `ttcp_collection` | `TTCP_COLLECTION` | Collection Mongo lưu kết luận đã trích xuất |
| `ttcp_prefix` | `TTCP_PREFIX` | Tiền tố key trên MinIO (`s3://bucket/<prefix>...`) |
| `ttcp_bucket` | `TTCP_BUCKET` | Bucket MinIO |
| `datalens_chatbot_code` | `DATALENS_CHATBOT_CODE` | Code chatbot DataLens (search_docs) |
| `ttcp_sync_url` | `TTCP_SYNC_URL` | Webhook đồng bộ ngược; **`""` = TẮT** cho account đó |

---

## 3. Quản lý tài khoản (CLI)

Mọi thao tác qua `python -m harness.useradd`. CLI thao tác trực tiếp Mongo.

### Tạo / cập nhật tài khoản

```bash
# Tài khoản "public" — dùng env mặc định (v2):
python -m harness.useradd bags --password 'doi_mat_khau_di' \
    --label 'Tài khoản chính'

# Tài khoản "private" — cấu hình hoàn toàn khác:
python -m harness.useradd alice --password '...' \
    --ttcp-collection ttcp-extracted-v3 \
    --ttcp-prefix     ttcp/ttcp_hs_16_05 \
    --datalens-code   ttcp-hs \
    --ttcp-sync-url   ''            \
    --label 'Phòng nội bộ'
```

Bỏ qua `--password` → CLI hỏi ẩn (không hiện màn hình).
Re-chạy cùng `username` → ghi đè (đổi mật khẩu / đổi profile / đổi label).

### Liệt kê

```bash
python -m harness.useradd --list
```

In ra mỗi account + override (nếu có). Mật khẩu không bao giờ hiện.

### Vô hiệu hoá / bật lại

```bash
python -m harness.useradd --disable olduser
python -m harness.useradd --enable  olduser
```

Account `disabled=true` không login được nhưng vẫn còn dữ liệu — bật lại bất
cứ lúc nào.

### Đổi mật khẩu

Chạy lại lệnh tạo với `--password`. Các field config khác giữ nguyên *nếu* bạn
truyền lại đầy đủ, **bị xoá nếu không truyền** (vì là upsert). Nên copy lại
các `--ttcp-*` khi đổi mật khẩu.

---

## 4. Slash commands trong chat

Gõ trong khung chat (`/ui` hoặc Telegram):

| Lệnh | Ý nghĩa |
|---|---|
| `/help` | Liệt kê tất cả lệnh |
| `/clear` | Xoá lịch sử session hiện tại |
| `/compact` | Nén lịch sử (tóm tắt phần cũ, giữ phần gần đây). Tự động chạy khi chạm 160k token, hoặc bấm tay khi cần |
| `/list-skills` | Liệt kê sub-agent (skills) đang load |

---

## 5. Telegram bot (tuỳ chọn)

Telegram chạy tiến trình riêng, không qua login web — dùng đường fallback
`X-User-Id`. Khi không có cookie session, harness **không bind tenant** → tool
dùng env mặc định. Nên Telegram bot ⇄ một profile duy nhất (cấu hình bằng env
trong `.env` của bot).

```bash
# Cài env (TELEGRAM_BOT_TOKEN, AGENT_API_URL...) rồi:
python -m channels.telegram.bot
```

Nếu muốn nhiều profile qua Telegram → tạo nhiều bot, mỗi bot trỏ AGENT_API_URL
sang một đường tách (hoặc dùng `X-User-Id` đặc biệt + reverse-proxy gắn cookie
giả lập — phức tạp, hỏi em).

---

## 6. Batch trích xuất (offline)

`extention_/ttcp_batch.py` dùng env trực tiếp (không có khái niệm tài khoản).
Mỗi profile chạy 1 lần batch riêng:

```bash
# Batch cho profile public (v2):
TTCP_COLLECTION=ttcp-extracted-v2 TTCP_PREFIX=ttcp/ttcp-bot/ \
    python extention_/ttcp_batch.py

# Batch cho profile private (v3):
TTCP_COLLECTION=ttcp-extracted-v3 TTCP_PREFIX=ttcp/ttcp_hs_16_05 \
    TTCP_SYNC_URL='' python extention_/ttcp_batch.py --retry-failed
```

Tham số khác (xem `--help`): `--retry-failed`, `--retry-errors-only`, `--stats-only`.

---

## 7. Phát hiện & cắt phụ lục

Mặc định bật, áp dụng cho mọi PDF (batch + chat upload). Tham số env:

| ENV | Mặc định | Vai trò |
|---|---|---|
| `PHU_LUC_ENABLED` | `true` | Tắt hoàn toàn cơ chế nếu đặt `false` |
| `PHU_LUC_CHUNK_SIZE` | `50` | Số trang mỗi lần model detect |
| `PHU_LUC_DPI` | `110` | Độ phân giải render cho detect |
| `PHU_LUC_SAFETY_PAGES` | `0` | Giữ thêm N trang sau ranh giới (đệm an toàn nếu hay cắt hụt) |

Test thủ công 1 file:

```bash
python src/extentions/multimodal/detect_phu_luc.py <file.pdf>
```

---

## 8. Auto-compact & ngữ cảnh

Gemma 4 26B-A4B ~200k token. Khi chạm `COMPACT_TOKEN_THRESHOLD` (mặc định
160k), middleware tự tóm tắt phần cũ, giữ `COMPACT_KEEP_LAST` tin nhắn gần
nhất. Người dùng cũng gõ `/compact` bất cứ lúc nào.

| ENV | Mặc định | Vai trò |
|---|---|---|
| `COMPACT_ENABLED` | `true` | Tắt auto-compact (manual `/compact` vẫn dùng được) |
| `COMPACT_TOKEN_THRESHOLD` | `160000` | Ngưỡng kích hoạt |
| `COMPACT_KEEP_LAST` | `8` | Số tin nhắn gần nhất giữ nguyên |

---

## 9. Checklist production

- [ ] Đổi mật khẩu account `bags` (hoặc xoá + tạo lại với tên khác).
- [ ] `AUTH_SECRET` đặt giá trị cố định: `python -c "import secrets;print(secrets.token_hex(32))"`.
- [ ] Sau TLS / nginx: `AUTH_COOKIE_SECURE=true`.
- [ ] `MONGO_URI`, `POSTGRES_DSN`, `ENDPOINT_URL_MINIO` trỏ đúng môi trường.
- [ ] Hạ tầng MinIO + Postgres + Mongo đã chạy, có backup.
- [ ] Tạo account thật, đặt `config` đúng cho từng profile.
- [ ] `TTCP_SYNC_URL` per-account đúng (account internal → `""` để khỏi đẩy data ra ngoài).
- [ ] Đặt `PDF_RENDER_WORKERS` theo số CPU thực của server (vd 32-core → `24`).

---

## 10. Phục hồi sự cố

### Quên hết mật khẩu
1. Vào Mongo (`mongosh`) → xoá hết doc trong collection `accounts`.
2. Restart server → bootstrap tạo lại `bags` / `bags111`.

### Account login được nhưng tool báo sai collection
1. Kiểm tra `config.ttcp_collection` của account (`python -m harness.useradd --list`).
2. Check ENV process: collection mặc định có khớp không.
3. Restart server (account doc đọc per-request, nhưng `lru_cache` MongoStore
   được giữ theo tên collection — vô hại nhưng restart cho chắc).

### Lỡ commit `.env` lên git
1. Đổi ngay `AUTH_SECRET` (tất cả session cũ vô hiệu).
2. Đổi mọi credential MinIO / Mongo / vLLM.

---

*Tài liệu này là nguồn duy nhất về vận hành bot. Có thay đổi quy trình thì cập
nhật trực tiếp ở đây, đừng tạo file mới song song.*
