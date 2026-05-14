# Phần 2 — Kịch bản Demo (5 màn · ~7 phút)

### Chuẩn bị

* Nạp sẵn vài trăm kết luận vào MongoDB bằng `ttcp_batch`.
* Chuẩn bị 1–2 PDF mới để demo extract trực tiếp.

---

## Màn 1 — “Nó hiểu tài liệu”

Upload một file PDF kết luận thanh tra lên Telegram, thêm caption là trích xuất tài liệu thanh tra cho tôi

→ Agent tự nhận diện loại văn bản, chạy `extract_ttcp` và trả JSON cấu trúc đầy đủ.

### Điểm nhấn

Không cần prompt kỹ thuật. Chỉ cần gửi tài liệu — AI tự hiểu nó đang đọc gì.

---

## Màn 2 — “Nó nhớ — nhưng có kiểm soát”

Người dùng:

> “Lưu kết luận này vào hệ thống.”

→ Agent hiển thị dữ liệu sắp ghi cùng nút:

`[✅ Approve]   [❌ Deny]`

Người demo bấm **Approve**.

### Điểm nhấn

AI không tự ý ghi dữ liệu. Con người luôn giữ quyền kiểm soát cuối cùng.

---

## Màn 3 — “Nó truy vấn cả kho dữ liệu”

Ví dụ:

> “Có bao nhiêu kết luận về đất đai?”
> “Liệt kê các kết luận có dấu hiệu tội phạm năm 2017.”
> “Tìm vi phạm liên quan đến đấu giá khoáng sản.”

→ Agent tự chuyển ngôn ngữ tự nhiên thành query có cấu trúc.

### Điểm nhấn

Không cần biết SQL hay dùng dashboard phức tạp.

---

## Màn 4 — “Nó phân tích”

Ví dụ:

> “Tổng giá trị vi phạm theo năm.”
> “Hành vi vi phạm phổ biến nhất trong lĩnh vực đất đai?”

→ Agent tự tổng hợp, thống kê và phân tích dữ liệu.

### Điểm nhấn

Những thứ thường phải build dashboard riêng giờ chỉ cần… đặt câu hỏi.

---

## Màn 5 — “Nó tạo ra sản phẩm hoàn chỉnh”

> “Xuất báo cáo tóm tắt cho kết luận 636/TB-TTCP.”

→ Telegram nhận file HTML hoàn chỉnh: có quốc huy, bảng chi tiết, nút in/xuất PDF.

### Điểm nhấn

Không chỉ trả lời — hệ thống tạo ra deliverable dùng được ngay.

---

# Kết màn — “Một agent, mọi giao diện”

Lặp lại một câu hỏi trên Web UI → kết quả giống Telegram.

### Câu chốt

> “Đây không phải chatbot gắn với một giao diện.
> Đây là AI Agent có thể hoạt động trên Telegram, web hoặc tích hợp vào hệ thống sẵn có — mà không khóa khách hàng vào bất kỳ nền tảng nào.”
