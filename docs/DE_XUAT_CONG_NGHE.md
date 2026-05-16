# ĐỀ XUẤT GIẢI PHÁP CÔNG NGHỆ

## Hệ thống Số hóa Dữ liệu Thanh tra & Nền tảng Trợ lý AI làm việc trên dữ liệu số hóa

> Tài liệu phục vụ hồ sơ đề xuất kỹ thuật. Phạm vi gồm hai cấu phần:
> (1) Hệ thống số hóa dữ liệu thanh tra — kết luận, kiến nghị xử lý; và
> (2) Nền tảng Trợ lý AI vận hành trên kho dữ liệu đã số hóa.

---

## A. TỔNG QUAN & ĐỊNH VỊ GIẢI PHÁP

### A.1. Bối cảnh và đặc thù dữ liệu thanh tra

Văn bản kết luận, thông báo kết luận thanh tra thuộc loại tài liệu khó số hóa, với các đặc thù:

- **Bản scan chất lượng thấp**: trang nghiêng, mờ, đóng dấu chồng lên chữ, nhiều trang, phông chữ cũ.
- **Cấu trúc pháp lý phân tầng sâu**: Mục I/II/III; nhóm vi phạm; mỗi vi phạm có hành vi, căn cứ pháp luật, hậu quả, trách nhiệm; kiến nghị xử lý trình bày tách riêng theo văn xuôi.
- **Ngữ nghĩa pháp lý chặt chẽ**: cần giữ nguyên ngôn từ "hành vi vi phạm", "căn cứ vi phạm" để không sai bản chất pháp lý.
- **Quan hệ chéo khó định vị**: kiến nghị xử lý thường viết gộp ở một mục riêng, không gắn trực tiếp với từng vi phạm.

Nếu chỉ nhận dạng chữ rồi cắt nhỏ máy móc theo độ dài, cấu trúc tài liệu sẽ bị mất, dẫn tới tra cứu kém và trích xuất sai số liệu — kết quả số hóa không đáp ứng được mục đích tra cứu, thống kê, ra báo cáo của cơ quan thanh tra.

### A.2. Triết lý thiết kế

**Thiết kế ngược từ sản phẩm đầu ra.** Cấu trúc dữ liệu số hóa được thiết kế đi ngược từ chính biểu mẫu báo cáo mà cơ quan thanh tra sử dụng (Bảng tóm tắt kết luận thanh tra: thông tin chung → trích lược vi phạm → bảng chi tiết → kiến nghị xử lý). Mỗi trường thông tin được số hóa đều có đích đến rõ ràng trên báo cáo, bảo đảm dữ liệu sau số hóa sử dụng được ngay.

### A.3. Kiến trúc tổng thể

Giải pháp ánh xạ theo mô hình nền tảng số hóa dữ liệu bất cấu trúc:

| Lớp | Vai trò |
|---|---|
| Nguồn dữ liệu | Tài liệu nội bộ (Word/PDF/ảnh), cơ sở dữ liệu nội bộ, dữ liệu tra cứu trực tuyến |
| Thu nhận dữ liệu | Bộ thu thập, cổng tiếp nhận, chuẩn hóa và tích hợp dữ liệu |
| Hạ tầng dữ liệu | Kho dữ liệu thô → sạch → trích xuất → sản xuất; kho phân tích; kho phục vụ tìm kiếm thông minh |
| Dữ liệu & ứng dụng | Số hóa dữ liệu thô, nhận dạng & trích xuất, tạo mục lục thông minh, trực quan hóa, lõi AI |
| Dịch vụ dữ liệu | Cổng dịch vụ chia sẻ dữ liệu tới hệ thống khác |
| Trải nghiệm người dùng | Ứng dụng Web, Mobile và Trợ lý AI đa kênh |
| Xuyên suốt | An toàn thông tin và Trục trao đổi dữ liệu |

### A.4. Đặc điểm nổi bật của giải pháp

- Thiết kế dữ liệu đi ngược từ biểu mẫu báo cáo — dữ liệu dùng được ngay.
- Tạo mục lục thông minh bằng công nghệ **PageIndex**, giữ nguyên cấu trúc pháp lý của tài liệu.
- Truy hồi tăng cường sinh (**RAG**) hai tầng: tìm rộng để không bỏ sót, lọc tinh để bảo đảm chính xác.
- Mọi câu trả lời có trích dẫn ngược về trang tài liệu gốc, bảo đảm kiểm chứng.
- Toàn bộ mô hình AI (LLM **Gemma 4 26B-A4B**, OCR **DeepSeek-OCR**, mô hình tìm kiếm **NVIDIA Nemotron**) vận hành nội bộ, dữ liệu không rời hạ tầng của cơ quan.
- Trợ lý AI xây trên nền **AI Agent harness** có kiểm soát con người; các cấu phần lõi đã có bản chạy thực tế, kiểm chứng được.

---

## B. CẤU PHẦN 1 — HỆ THỐNG SỐ HÓA DỮ LIỆU THANH TRA

Quy trình số hóa gồm sáu công đoạn. Bốn công đoạn đánh dấu ★ là phần lõi tạo khác biệt (chi tiết tại Phần D):

1. Thu nhận và chuẩn hóa đầu vào
2. ★ Nhận dạng chữ và tiền xử lý ảnh
3. ★ Tạo mục lục thông minh cho tài liệu
4. ★ Tìm kiếm ngữ nghĩa hai tầng
5. ★ Trích xuất có cấu trúc theo biểu mẫu
6. Lưu trữ đa tầng phục vụ tra cứu, thống kê

### B.1. Thu nhận và chuẩn hóa đầu vào

- **Nguồn**: tải lên thủ công (Web/Mobile/Telegram), quét hàng loạt từ kho lưu trữ, thu thập trực tuyến dữ liệu công khai liên quan.
- **Chuẩn hóa**: nhận diện loại tệp, tách trang, gom nhiều ảnh thành một tài liệu logic, gán định danh nguồn để truy vết suốt vòng đời.
- **Quản lý tiến trình theo trạng thái**: mỗi tài liệu là một bản ghi có trạng thái xử lý (chờ → đang chạy → hoàn tất / lỗi), bảo đảm chạy lại an toàn, tự động thử lại khi lỗi, dọn tiến trình treo, và xử lý lại hàng loạt khi nâng cấp.

### B.2. ★ Nhận dạng chữ và tiền xử lý ảnh

Đây là công đoạn nền tảng, ảnh hưởng trực tiếp tới chất lượng các bước sau. Quy trình xử lý ảnh gồm năm bước:

1. **Dựng ảnh độ phân giải cao** từ tệp PDF, giữ được nét chữ nhỏ và dấu thanh tiếng Việt.
2. **Tự động sửa hướng trang**: phát hiện trang bị xoay (ngang/úp ngược) và xoay về đúng chiều trước khi nhận dạng. Bản scan của cơ quan nhà nước thường bị xoay, nên đây là bước bắt buộc.
3. **Làm sạch ảnh**: khử nhiễu, tăng tương phản, làm thẳng dòng chữ, tách lớp con dấu đỏ chồng chữ để đọc được phần chữ bên dưới.
4. **Nhận dạng chữ** bằng mô hình **DeepSeek-OCR** thế hệ mới, xử lý tốt tiếng Việt có dấu, bảng biểu, văn bản nhiều cột, và giữ nguyên bố cục (bảng, danh sách điều khoản, đánh số mục) thay vì bẻ thành văn bản phẳng.
5. **Đầu ra** dùng chung cho cả bước tạo mục lục và bước trích xuất.

**Cam kết đo lường:**

| Chỉ tiêu | Mục tiêu |
|---|---|
| Tỷ lệ nhận dạng chữ chính xác (scan tốt) | ≥ 97% |
| Tỷ lệ nhận dạng chữ chính xác (scan kém) | ≥ 92% |
| Tỷ lệ trang được sửa đúng hướng | ≥ 99% |
| Độ chính xác vùng trọng yếu (số văn bản, ngày, số tiền) | ≥ 98% |
| Độ chính xác cấu trúc bảng | ≥ 90% |

Đánh giá trên bộ mẫu thực tế do cán bộ nghiệp vụ chấm.

### B.3. ★ Tạo mục lục thông minh cho tài liệu (PageIndex)

Hệ thống áp dụng công nghệ **PageIndex** — tự sinh mục lục cho từng tài liệu và tìm kiếm theo cấu trúc, thay cho cách cắt nhỏ máy móc thông thường.

**Một là, dựng cây mục lục.** Sau khi nhận dạng chữ, hệ thống tự nhận biết các tiêu đề và cấp độ (Mục lớn → nhóm vi phạm → từng vi phạm → điều khoản) và dựng thành cây mục lục. Mỗi mục con ghi rõ: tiêu đề, cấp độ, khoảng trang, và một bản tóm tắt ngắn để máy hiểu nhanh nội dung mục đó.

**Hai là, tìm kiếm điều hướng theo cấp.** Hệ thống đọc mục lục và tìm theo lập luận: bắt đầu từ mục lớn, chọn nhánh phù hợp, đi sâu xuống mục con; nếu nhánh đang đi không chứa câu trả lời thì quay ngược lên cấp trên và rẽ sang nhánh khác — tương tự cách một chuyên viên lật mục lục để tra tài liệu. Kết quả trả về kèm đường dẫn tới đúng mục và số trang gốc.

**Giá trị:**
- Trả lời chính xác câu hỏi mang tính định vị, ví dụ kiến nghị kinh tế của một vi phạm cụ thể, hoặc các vụ được nêu chuyển cơ quan điều tra trong Mục III.
- Trích dẫn ngược về trang tài liệu gốc, phục vụ kiểm chứng pháp lý.
- Giữ được ngữ cảnh phân cấp, hỗ trợ trực tiếp bài toán gán kiến nghị vào vi phạm ở bước trích xuất.
- Kết hợp với tìm kiếm ngữ nghĩa (bước B.4): câu hỏi cấu trúc đi theo mục lục, câu hỏi mở tìm theo ngữ nghĩa.

**Cam kết đo lường:**

| Chỉ tiêu | Mục tiêu |
|---|---|
| Độ chính xác nhận diện tiêu đề mục lục | ≥ 92% |
| Độ chính xác phân cấp mục lục | ≥ 90% |
| Tỷ lệ tìm đúng mục chứa câu trả lời (trong 3 lựa chọn đầu) | ≥ 93% |
| Tỷ lệ câu trả lời trích dẫn đúng trang nguồn | ≥ 95% |

### B.4. ★ Tìm kiếm ngữ nghĩa hai tầng (RAG)

Hệ thống áp dụng kiến trúc truy hồi tăng cường sinh (**RAG**) hai tầng, dữ liệu lưu trên kho vector **Weaviate**:

- **Tầng 1 — Tìm rộng (embedding)**: mô hình **NVIDIA Nemotron Embed** chuyển nội dung tài liệu sang dạng máy hiểu được về ngữ nghĩa, truy hồi nhanh một tập ứng viên rộng, ưu tiên không bỏ sót.
- **Tầng 2 — Lọc tinh (rerank)**: mô hình **NVIDIA Nemotron Rerank** đọc kỹ từng ứng viên cùng câu hỏi để xếp hạng lại, chỉ giữ vài kết quả liên quan nhất, ưu tiên chính xác và ít nhiễu.

Tầng lọc tinh giúp nâng độ chính xác đáng kể với câu hỏi pháp lý cần đúng từng điều khoản. Hệ thống xử lý riêng đặc thù tiếng Việt để không làm hỏng từ có dấu khi tìm kiếm.

**Cam kết đo lường:**

| Chỉ tiêu | Mục tiêu |
|---|---|
| Tỷ lệ không bỏ sót thông tin đúng (tầng tìm rộng) | ≥ 97% |
| Độ chính xác kết quả cuối (sau lọc tinh) | ≥ 85% |
| Tỷ lệ câu trả lời bám đúng tài liệu | ≥ 95% |

### B.5. ★ Trích xuất có cấu trúc theo biểu mẫu

- **Mô hình ngôn ngữ Gemma 4 26B-A4B vận hành hoàn toàn nội bộ** (qua vLLM) — chất lượng cao, chi phí vận hành hợp lý, dữ liệu thanh tra không rời hạ tầng của cơ quan.
- **Đọc trực tiếp ảnh trang** (đa phương thức) cùng biểu mẫu đích để bóc tách thông tin về đúng cấu trúc cần dùng.
- **Cấu trúc dữ liệu thiết kế ngược từ báo cáo** (xem A.2), gồm ba khối: thông tin chung; danh sách vi phạm (mỗi vi phạm có hành vi, căn cứ pháp luật, hậu quả định tính/định lượng, nguyên nhân, trách nhiệm, kiến nghị theo ba loại hình sự/hành chính/kinh tế, giá trị thiệt hại, dấu hiệu tội phạm); và kiến nghị xử lý chung.
- **Liên kết hai cấp**: kiến nghị trong văn bản thường viết gộp một mục, không gắn vi phạm cụ thể. Giải pháp gắn kiến nghị vào đúng vi phạm khi văn bản nêu rõ (qua số thứ tự, đối tượng, số tiền, hành vi); phần chung giữ ở cấp tài liệu, cân bằng giữa không suy diễn và bảo đảm báo cáo đầy đủ.
- **Bảo toàn số liệu**: chuẩn hóa tiền tệ, ngày tháng; không tự cộng tổng; thông tin không có trong văn bản thì để trống, không suy diễn.

**Cam kết đo lường:**

| Chỉ tiêu | Mục tiêu |
|---|---|
| Độ chính xác trường khóa (số văn bản, ngày ban hành) | ≥ 98% |
| Độ chính xác trường tiền (giá trị thiệt hại) | ≥ 95% |
| Độ chính xác trường nội dung (hành vi, căn cứ, hậu quả) | ≥ 88% |
| Độ chính xác nhận diện số lượng vi phạm | ≥ 90% |
| Độ chính xác gán kiến nghị vào đúng vi phạm | ≥ 85% |
| Tỷ lệ thông tin không có trong văn bản bị đưa vào | ≤ 2% |

### B.6. Lưu trữ đa tầng phục vụ tra cứu, thống kê

| Tầng lưu trữ | Công nghệ | Vai trò | Trạng thái |
|---|---|---|---|
| Kho tài liệu gốc | **MinIO** (object storage) | Lưu PDF/ảnh gốc bất biến, phục vụ truy vết pháp lý | Sẵn sàng |
| Kho dữ liệu sạch / trích xuất | MinIO + **Apache Iceberg** | Văn bản đã nhận dạng, mục lục, dữ liệu trích xuất | Theo lộ trình |
| Kho tìm kiếm thông minh | **Weaviate** (vector DB) | Dữ liệu đã chỉ mục cho tra cứu ngữ nghĩa | Sẵn sàng |
| Kho truy vấn, thống kê | **MongoDB** (tạm) → **Apache Iceberg / Big Data** | Dữ liệu trích xuất cho tra cứu/thống kê | Đang chuyển sang nền dữ liệu lớn |

> **Minh bạch kỹ thuật**: dữ liệu trích xuất hiện đặt tạm trên MongoDB để sớm có tính năng tra cứu/thống kê phục vụ kiểm chứng. Lộ trình chuyển sang nền dữ liệu lớn (Apache Iceberg trên Data Lake) để phân tích quy mô hàng trăm nghìn hồ sơ. Tầng truy vấn được thiết kế trừu tượng hóa, nên việc chuyển kho không ảnh hưởng tới Trợ lý AI hay báo cáo đang chạy.

---

## C. CẤU PHẦN 2 — NỀN TẢNG TRỢ LÝ AI (AI AGENT HARNESS)

Trợ lý AI được xây trên nền **AI Agent harness** (khung điều phối tác tử AI, nền LangGraph) — vận hành trên kho dữ liệu đã số hóa: tra cứu, phân tích, thống kê, xuất báo cáo qua hội thoại tự nhiên, có kiểm soát của con người (HITL — Human-in-the-loop).

### C.1. Năng lực Trợ lý AI

| Năng lực | Mô tả nghiệp vụ |
|---|---|
| Trích xuất | Đưa một kết luận thanh tra (PDF/ảnh) thành dữ liệu có cấu trúc |
| Tra cứu | Tìm theo số văn bản; tìm toàn văn theo nội dung vi phạm/kiến nghị |
| Lọc | Lọc theo lĩnh vực, cơ quan, năm, có dấu hiệu tội phạm |
| Phân tích, thống kê | Thống kê tổng hợp theo lĩnh vực/cơ quan/năm/nhóm vi phạm: đếm số lượng, tổng giá trị thiệt hại, giá trị trung bình |
| Báo cáo | Sinh báo cáo theo đúng biểu mẫu |
| Tài liệu gốc | Lấy lại PDF gốc khi cần đối chiếu |
| Cập nhật dữ liệu | Lưu / sửa / xóa, bắt buộc có người duyệt |
| Tra cứu tri thức | Hỏi đáp trên kho tài liệu nội bộ kèm trích dẫn nguồn |

Năng lực phân tích, thống kê cho phép trả lời tức thì bằng câu hỏi tiếng Việt những nội dung thông thường phải dựng báo cáo riêng, ví dụ thống kê các cơ quan có nhiều kết luận nhất, tổng thiệt hại theo năm theo lĩnh vực, hoặc hành vi vi phạm phổ biến nhất trong một ngành.

### C.2. ★ Tra cứu tri thức nội bộ kèm trích dẫn

Đây là nơi ba công nghệ — nhận dạng chữ, mục lục thông minh, tìm kiếm hai tầng — kết hợp thành một dịch vụ tra cứu tri thức. Trợ lý truy vấn kho tài liệu nội bộ (kết luận thanh tra đã số hóa và tài liệu pháp luật liên quan), tự đặt lại câu hỏi cho rõ, đi theo mục lục, tìm và lọc tinh, rồi tổng hợp câu trả lời kèm trích dẫn nguồn tới trang tài liệu gốc, bảo đảm tính kiểm chứng.

### C.3. Kiểm soát của con người (HITL)

Với dữ liệu thanh tra, tính toàn vẹn dữ liệu có giá trị pháp lý:

- Mọi thao tác ghi, sửa, xóa dữ liệu đều tạm dừng, hiển thị đầy đủ nội dung sắp thực hiện và yêu cầu người dùng bấm Duyệt hoặc Từ chối mới được chạy.
- Thao tác chỉ tra cứu/thống kê không bị chặn, phản hồi tức thì.
- Mỗi thay đổi dữ liệu tự động đồng bộ tới hệ thống khác qua Trục trao đổi dữ liệu theo thời gian thực.

### C.4. Sinh báo cáo theo biểu mẫu

- Báo cáo trình bày đúng biểu mẫu (nhận diện cơ quan thanh tra, in / xuất PDF được): thông tin chung → trích lược vi phạm → bảng chi tiết → kiến nghị xử lý.
- Ổn định: cùng dữ liệu đầu vào luôn ra cùng báo cáo. Thông tin thiếu ghi rõ "Chưa rõ".
- Giao tận tay người dùng qua mọi kênh, không cần thao tác kỹ thuật.

### C.5. Đa kênh và đồng bộ

- Một bộ não, dùng được trên Web, ứng dụng nhắn tin, và tích hợp vào ứng dụng sẵn có.
- Đồng bộ thời gian thực tới hệ thống khác; xử lý hàng loạt chạy nền, có kiểm soát tiến độ và tự thử lại khi lỗi.

---

## D. CÁC HẠNG MỤC TRỌNG YẾU TẠO KHÁC BIỆT

| # | Hạng mục | Công nghệ | Độ phức tạp kỹ thuật | Giá trị mang lại |
|---|---|---|---|---|
| 1 | Nhận dạng chữ + sửa hướng trang | DeepSeek-OCR | Scan nghiêng/mờ/đóng dấu; tiếng Việt có dấu | Nền tảng cho mọi bước sau |
| 2 | Mục lục thông minh, tìm theo cấu trúc | PageIndex | Tự dựng và đi theo cây mục lục pháp lý | Tra đúng nhánh, trích dẫn ngược trang |
| 3 | Tìm kiếm hai tầng | RAG + Nemotron Embed/Rerank, Weaviate | Tầng tìm rộng kết hợp tầng lọc tinh | Câu trả lời chính xác, ít nhiễu |
| 4 | Thiết kế dữ liệu ngược từ báo cáo + liên kết hai cấp | Gemma 4 26B-A4B | Hiểu cả biểu mẫu lẫn cấu trúc văn bản | Dữ liệu dùng được ngay |
| 5 | Tra cứu tri thức có trích dẫn | OCR + PageIndex + RAG hợp nhất | Kết nối ba công nghệ thành một dịch vụ | Tri thức kiểm chứng được |
| 6 | Kiểm soát con người + truy vết + đồng bộ | AI Agent harness (HITL) | Quản trị toàn vẹn dữ liệu pháp lý xuyên suốt | Đạt yêu cầu cơ quan nhà nước |

---

## E. CÔNG NGHỆ NỀN TẢNG

Toàn bộ mô hình AI vận hành nội bộ qua vLLM; dữ liệu thanh tra không rời hạ tầng của cơ quan.

| Thành phần | Công nghệ / mô hình | Lý do lựa chọn |
|---|---|---|
| Mô hình ngôn ngữ (trích xuất & trợ lý) | **Gemma 4 26B-A4B** (vận hành nội bộ qua vLLM) | Chất lượng cao, chi phí hợp lý, an toàn dữ liệu |
| Nhận dạng chữ | **DeepSeek-OCR** | Phù hợp scan tiếng Việt, giữ bố cục |
| Tìm kiếm — tầng tìm rộng | **NVIDIA Nemotron Embed** | Truy hồi ngữ nghĩa, không bỏ sót |
| Tìm kiếm — tầng lọc tinh | **NVIDIA Nemotron Rerank** | Xếp hạng lại, độ chính xác cao |
| Mục lục thông minh | **PageIndex** (tạo & tra cứu theo cây cấu trúc) | Giữ cấu trúc pháp lý, trích dẫn được |
| Kho tìm kiếm thông minh | **Weaviate** (vector DB) | Tra cứu ngữ nghĩa quy mô lớn (RAG) |
| Kho tài liệu gốc | **MinIO** (object storage) | Lưu file gốc bất biến, truy vết |
| Nền dữ liệu lớn (phân tích) | **MongoDB** (tạm) → **Apache Iceberg / Big Data** | Quy mô lớn, mở rộng, time-travel |
| Thu nhận dữ liệu | **Airbyte**, **Tavily** | Tích hợp nội bộ và thu thập trực tuyến |
| Nền tảng Trợ lý AI | **AI Agent harness** (LangGraph) có HITL | An toàn, đa kênh, mở rộng |

---

## F. LỘ TRÌNH TRIỂN KHAI

| Giai đoạn | Nội dung | Kết quả nghiệm thu |
|---|---|---|
| 1 | Nhận dạng chữ + sửa hướng + quản lý tiến trình | Số hóa được lô tài liệu mẫu, ổn định |
| 2 | Trích xuất theo biểu mẫu thiết kế ngược | Đạt chỉ tiêu độ chính xác trường |
| 3 | Mục lục thông minh + tìm kiếm hai tầng | Tra cứu có trích dẫn nguồn |
| 4 | Trợ lý AI + tra cứu/thống kê + kiểm soát con người | Hỏi đáp, thống kê tự nhiên, có duyệt |
| 5 | Sinh báo cáo theo biểu mẫu; đa kênh; đồng bộ | Báo cáo đúng mẫu, giao đa kênh |
| 6 | Chuyển sang nền dữ liệu lớn; tối ưu, giám sát | Phân tích quy mô lớn |

Các giai đoạn 2, 4, 5 đã có bản chạy thực tế (trích xuất, trợ lý và công cụ, báo cáo, xử lý hàng loạt, kiểm soát con người, đa kênh), chứng minh năng lực thực thi.

---

## G. PHƯƠNG PHÁP ĐÁNH GIÁ & CAM KẾT NGHIỆM THU

### G.1. Tổng hợp cam kết chất lượng

| Cấu phần | Cam kết chính |
|---|---|
| Nhận dạng chữ | Chính xác ≥ 97% (scan tốt); sửa đúng hướng ≥ 99% |
| Mục lục thông minh | Nhận diện mục lục ≥ 92%; trích dẫn đúng trang ≥ 95% |
| Tìm kiếm | Không bỏ sót ≥ 97%; bám đúng tài liệu ≥ 95% |
| Trích xuất | Trường khóa ≥ 98%; thông tin ngoài văn bản ≤ 2% |
| Báo cáo | Khớp biểu mẫu ≥ 95%; ổn định tuyệt đối |

### G.2. Cách đánh giá bảo đảm khách quan

- **Bộ mẫu chuẩn** do hai cán bộ nghiệp vụ chấm độc lập; chỉ dùng làm chuẩn khi hai người đồng thuận ở mức cao.
- **Tách riêng tập kiểm thử** không dùng trong quá trình tinh chỉnh, phản ánh năng lực thật và tránh tối ưu cục bộ.
- **So sánh theo phiên bản**: mỗi lần nâng cấp đều đo lại trên cùng bộ mẫu để chứng minh tiến bộ bằng số liệu.
- **Đo tự động kết hợp đo người**: chỉ tiêu cấu trúc đo tự động định kỳ; chỉ tiêu ngữ nghĩa do nghiệp vụ chấm.

### G.3. Cam kết vận hành & an toàn

| Chỉ tiêu | Cam kết |
|---|---|
| Tỷ lệ xử lý thành công (sau thử lại) | ≥ 98% |
| Mức sẵn sàng dịch vụ | ≥ 99,5% |
| Thao tác thay đổi dữ liệu có người duyệt | 100% |
| Tài liệu gốc truy vết được tới nguồn | 100% |
| Dữ liệu rời hạ tầng nội bộ | 0 |

---

## H. RỦI RO & GIẢI PHÁP GIẢM THIỂU

| Rủi ro | Giải pháp |
|---|---|
| Scan quá xấu, nhận dạng sai | Sửa hướng và làm sạch ảnh; đánh dấu để cán bộ rà thủ công; xử lý lại khi nâng cấp |
| Sai số liệu do suy diễn | Quy tắc bảo toàn số liệu, không tự cộng tổng; thiếu thì để trống hoặc "Chưa rõ" |
| Gán kiến nghị sai vi phạm | Quy tắc gán thận trọng; giữ kiến nghị chung ở cấp tài liệu; nghiệp vụ duyệt lại |
| Tải hạ tầng tính toán | Dùng mô hình gọn cho tìm kiếm; điều tiết xử lý hàng loạt |
| Thay đổi kho dữ liệu | Tầng truy vấn trừu tượng hóa, trợ lý và báo cáo không đổi |
| An toàn dữ liệu | Toàn bộ nội bộ; phân quyền; người duyệt; nhật ký kiểm toán; truy vết nguồn |

---

## I. HƯỚNG ĐI TƯƠNG LAI & TẦM NHÌN

Tầm nhìn ba giai đoạn: từ kho dữ liệu, tới trợ lý nghiệp vụ, tới nền tảng tri thức thanh tra toàn ngành.

### I.1. Ngắn hạn — Củng cố và mở rộng nền tảng

- Hoàn tất chuyển sang nền dữ liệu lớn, phục vụ thống kê quy mô hàng trăm nghìn kết luận toàn ngành.
- Học từ chỉnh sửa của chuyên viên: mỗi lần cán bộ duyệt và sửa, hệ thống tích lũy thành dữ liệu cải thiện độ chính xác theo thời gian.
- Bảng điều khiển trực quan: biểu đồ xu hướng vi phạm theo năm/lĩnh vực/cơ quan, bản đồ thiệt hại.

### I.2. Trung hạn — Trí tuệ nghiệp vụ chuyên sâu

- Tinh chỉnh mô hình theo miền pháp lý thanh tra (fine-tuning / LoRA trên Gemma) để hiểu sâu ngôn ngữ chuyên ngành, giảm sai sót.
- **Bản đồ tri thức thanh tra (Knowledge Graph)**: liên kết đối tượng – vi phạm – căn cứ pháp luật – kiến nghị – cơ quan xuyên nhiều kết luận, trả lời được câu hỏi liên văn bản.
- Phát hiện bất thường và cảnh báo sớm phục vụ thanh tra có trọng điểm.
- Đối chiếu pháp luật tự động: kiểm tra hiệu lực điều khoản tại thời điểm vi phạm.

### I.3. Dài hạn — Trợ lý hỗ trợ ra quyết định

- Trợ lý gợi ý dự thảo kết luận thanh tra từ hồ sơ vụ việc, có trích dẫn pháp luật; con người quyết định cuối cùng.
- Liên thông Trục trao đổi dữ liệu quốc gia, chia sẻ dữ liệu chuẩn hóa cho hệ thống liên ngành.
- Mở rộng đa phương thức: bóc tách số liệu từ bảng biểu phụ lục, chuyển âm thanh buổi làm việc thành văn bản.
- Kiến trúc không phụ thuộc một mô hình: nâng cấp mô hình mới không phải làm lại hệ thống.

> **Tầm nhìn**: đưa kho kết luận thanh tra rời rạc trên giấy và PDF thành tài sản tri thức có thể tra cứu, thống kê, cảnh báo và hỗ trợ ra quyết định, đặt nền cho thanh tra dựa trên dữ liệu ở quy mô toàn ngành.

---

*Tài liệu thuộc hồ sơ đề xuất kỹ thuật. Các hạng mục đánh dấu ★ là phần lõi tạo lợi thế cạnh tranh và đã/đang có bản hiện thực kiểm chứng được.*
