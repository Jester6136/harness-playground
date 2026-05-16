# ƯỚC LƯỢNG CHI PHÍ XÂY DỰNG

## Hệ thống Số hóa Dữ liệu Thanh tra & Nền tảng Trợ lý AI

> Tài liệu ước lượng sơ bộ phục vụ lập dự toán. Con số mang tính tham chiếu,
> cần chốt lại theo phạm vi và hạ tầng thực tế. Đơn vị: triệu đồng (tr.đ).

---

## 1. CÁC GIẢ ĐỊNH & YẾU TỐ CHI PHỐI

Chi phí phụ thuộc mạnh vào bốn yếu tố. Bản ước lượng dưới đây dựa trên giả định cơ sở:

| Yếu tố | Giả định cơ sở |
|---|---|
| Quy mô số hóa | ~50.000–100.000 trang tài liệu giai đoạn đầu, có thể mở rộng |
| Thời gian triển khai | 6–9 tháng, đội 5–7 người |
| Hạ tầng tính toán | Trình bày 3 kịch bản (đã có / mua mới / thuê) — xem mục 4 |
| Mức độ kế thừa | Các cấu phần lõi đã có bản chạy (giai đoạn 2, 4, 5) → giảm rủi ro và khối lượng |
| Đơn giá nhân công | Đơn giá blended (đã gồm chi phí quản lý) ~ 45 tr.đ / người-tháng |

> **Lưu ý**: phần lớn công nghệ là mã nguồn mở (vLLM, Weaviate, MinIO, Apache Iceberg, Airbyte, LangGraph) nên **chi phí bản quyền gần như bằng 0**; chi phí chủ yếu là nhân lực và hạ tầng tính toán.

---

## 2. KHỐI LƯỢNG CÔNG VIỆC THEO GIAI ĐOẠN

Ước lượng theo người-tháng (PM = person-month). Cột "Kế thừa" phản ánh phần đã có bản chạy thực tế, giúp giảm khối lượng và rủi ro.

| Giai đoạn | Nội dung | Khối lượng (PM) | Kế thừa |
|---|---|---|---|
| 1 | Nhận dạng chữ (DeepSeek-OCR) + sửa hướng + tiền xử lý + quản lý tiến trình | 3,5 | Một phần |
| 2 | Trích xuất theo biểu mẫu (Gemma 4 26B-A4B) + thiết kế ngược schema + xử lý hàng loạt | 4,0 | Đã có bản chạy |
| 3 | Mục lục thông minh (PageIndex) + tìm kiếm hai tầng (RAG: Nemotron + Weaviate) + dịch vụ tra cứu | 6,5 | Mới (hạng mục nặng nhất) |
| 4 | Trợ lý AI (AI Agent harness) + bộ công cụ tra cứu/thống kê + kiểm soát con người (HITL) | 4,0 | Đã có bản chạy |
| 5 | Sinh báo cáo theo biểu mẫu + đa kênh + đồng bộ realtime | 3,0 | Đã có bản chạy |
| 6 | Chuyển sang nền dữ liệu lớn (Apache Iceberg / Big Data) + tối ưu + giám sát | 3,5 | Mới |
| — | Xuyên suốt: kiến trúc, quản trị dự án, kiểm thử, bộ mẫu chuẩn (gold set), an toàn thông tin, tài liệu, đào tạo, bàn giao | 7,5 | — |
| **Tổng** | | **≈ 32 người-tháng** | |

---

## 3. CHI PHÍ NHÂN LỰC

| Vai trò | Tỷ trọng tham gia |
|---|---|
| Kỹ sư AI/ML (OCR, RAG, PageIndex, trích xuất) | Chủ lực |
| Kỹ sư hệ thống (Agent harness, API, tích hợp) | Chủ lực |
| Kỹ sư dữ liệu (Data Lake, Iceberg, MinIO, ingest) | Vừa |
| Kỹ sư giao diện (Web/Mobile) | Vừa |
| Kỹ sư vận hành (MLOps, vLLM, hạ tầng GPU) | Vừa |
| Kiểm thử (QA) | Vừa |
| Chuyên gia nghiệp vụ thanh tra / phân tích | Vừa |
| Quản trị dự án / Kiến trúc trưởng | Điều phối |

**Ước tính**: 32 người-tháng × 45 tr.đ = **≈ 1.440 tr.đ**.
Khoảng dao động theo đơn giá và phạm vi: **1.250 – 1.800 tr.đ**.

---

## 4. CHI PHÍ HẠ TẦNG TÍNH TOÁN (3 KỊCH BẢN)

Mô hình chạy nội bộ qua vLLM. Nhu cầu: GPU phục vụ Gemma 4 26B-A4B (lượng tử hóa 4-bit), DeepSeek-OCR, hai mô hình Nemotron 1B; máy chủ lưu trữ cho MinIO / Weaviate / nền dữ liệu lớn / ứng dụng.

| Kịch bản | Mô tả | Chi phí hạ tầng |
|---|---|---|
| **A. Đã có hạ tầng GPU** | Cơ quan đã có máy chủ GPU đủ năng lực; chỉ cấu hình, tối ưu | ≈ 0 – 150 tr.đ |
| **B. Mua mới hạ tầng on-premise** | 1 máy chủ GPU (2–4 GPU 48GB) + máy chủ lưu trữ/CPU + mạng | ≈ 800 – 1.600 tr.đ (chi phí 1 lần) |
| **C. Thuê hạ tầng (cloud/đối tác)** | Thuê GPU theo tháng trong thời gian triển khai + chuyển nội bộ sau | ≈ 250 – 500 tr.đ (giai đoạn dự án) |

> Khuyến nghị: nếu chưa có GPU, kịch bản B tối ưu lâu dài (dữ liệu thanh tra phải nội bộ, không nên phụ thuộc thuê ngoài kéo dài).

---

## 5. CHI PHÍ KHÁC

| Khoản mục | Ước tính |
|---|---|
| Xây dựng bộ mẫu chuẩn (gold set) — chuyên gia nghiệp vụ chấm 2 vòng | 60 – 120 tr.đ |
| Triển khai, cài đặt, chuyển giao tại chỗ | Tính trong nhân lực |
| Đào tạo người dùng & quản trị viên | 30 – 60 tr.đ |
| Bản quyền phần mềm (chủ yếu mã nguồn mở) | ≈ 0 – 50 tr.đ |
| Dự phòng rủi ro (10–15% tổng) | Theo tỷ lệ |

---

## 6. TỔNG HỢP CHI PHÍ XÂY DỰNG

| Khoản | Giá trị (tr.đ) |
|---|---|
| Nhân lực phát triển | 1.250 – 1.800 |
| Chi phí khác (gold set, đào tạo, bản quyền) | 90 – 230 |
| Dự phòng (≈ 12%) | 160 – 240 |
| **Tổng (chưa gồm hạ tầng GPU)** | **≈ 1.500 – 2.270** |
| Hạ tầng GPU — Kịch bản A (đã có) | + 0 – 150 |
| Hạ tầng GPU — Kịch bản B (mua mới) | + 800 – 1.600 |
| Hạ tầng GPU — Kịch bản C (thuê) | + 250 – 500 |

**Tổng theo kịch bản:**

| Kịch bản hạ tầng | Tổng chi phí xây dựng (tr.đ) |
|---|---|
| A — Đã có hạ tầng GPU | **≈ 1.500 – 2.420** |
| B — Mua mới hạ tầng | **≈ 2.300 – 3.870** |
| C — Thuê hạ tầng | **≈ 1.750 – 2.770** |

---

## 7. CHI PHÍ VẬN HÀNH & BẢO TRÌ (tùy chọn, sau bàn giao)

| Khoản mục | Ước tính / năm |
|---|---|
| Bảo trì, vá lỗi, cập nhật mô hình | 15 – 20% chi phí xây dựng / năm |
| Vận hành hạ tầng (điện, làm mát, thay thế) | Theo thực tế hạ tầng |
| Hỗ trợ kỹ thuật & nâng cấp tính năng | Theo gói thỏa thuận |

---

## 8. GHI CHÚ QUAN TRỌNG

- Đây là **ước lượng sơ bộ**, không phải báo giá chính thức; con số cần chốt theo phạm vi, quy mô tài liệu, hạ tầng và mức dịch vụ cam kết.
- **Lợi thế chi phí**: các cấu phần lõi (trích xuất, trợ lý + công cụ, báo cáo, xử lý hàng loạt, kiểm soát con người, đa kênh) đã có bản chạy thực tế → giảm rủi ro phát sinh và rút ngắn thời gian, là cơ sở để đưa giá cạnh tranh mà vẫn khả thi.
- Phần "nặng" nhất về chi phí và chất xám là **Giai đoạn 3 (PageIndex + RAG hai tầng)** — cũng là phần tạo khác biệt cạnh tranh lớn nhất.
- Phần lớn công nghệ mã nguồn mở → không phụ thuộc bản quyền nhà cung cấp, chủ động lâu dài.

---

*Tài liệu thuộc hồ sơ đề xuất. Sẵn sàng điều chỉnh chi tiết theo phạm vi và ngân sách mục tiêu.*
