extract_system_prompt = """Extract the information from these Vietnamese images of multiple Certificate of Land Use Rights and format it into a strict JSON structure.

IMPORTANT:
- MUST HAVE Số phát hành Một trong 3 dạng:
    1. ^\\d{10,15}$
    2. ^[A-Z]{1,2}\\s?\\d+$
    3. Tiền tố "SO" + dạng 2 → bỏ "SO"
- May have multiple Certificate of Land Use Rights with different information as Số phát hành. (chú ý) Và Giấy loại cũ sẽ có biến động và đưa ra loại các giấy mới khác đồng thời kiểu số phát hành cũng có thể khác.
- Return JSON ONLY. No explanation, no markdown.
- Output MUST match the structure EXACTLY.
- Do NOT add any extra fields.
- Do NOT remove any fields.
- If information is missing → use "" for string, [] for arrays.
- Do NOT hallucinate.
- Keep Vietnamese text as is.

Hướng dẫn chi tiết cho các trường quan trọng cần trích xuất:
Giấy chứng nhận:
  - 'Số phát hành': str. 
  - 'Số vào sổ': Kiểu dữ liệu - str. 
  - 'Ngày cấp': CHỈ điền giá trị ngày dạng dd/mm/yyyy, KHÔNG kèm tên tỉnh, cơ quan, hay bất kỳ text nào khác. Vị trí nhận biết: trước đó là tên 1 tỉnh (ví dụ: Hưng Yên, Hải Phòng,...) và ngay sau là tên 1 cơ quan tổ chức — nhưng output CHỈ giữ phần ngày tháng.
Chủ sử dụng:
  - 'Loại đối tượng': Dữ liệu kiểu str, chọn một trong các giá trị:  \n- 'Cá nhân' – quyền thuộc về một người.  \n- 'Vợ chồng' – văn bản đề cập ông và vợ (bà).  \n- 'Hộ gia đình' – nhiều người đứng tên.  \n- 'Đồng sử dụng' – văn bản có cụm 'Đồng sử dụng'.  \n- 'Cộng đồng dân cư' – đối tượng là cộng đồng cụ thể.  \n- 'Tổ chức' – quyền thuộc về tổ chức, cơ quan.
  - 'Tên chủ': Tên người, là chủ sở hữu đất và các tài sản gắn liền với đất.
  - 'Năm sinh': Kiểu dữ liệu - int, Năm sinh của chủ sử dụng đất.
  - 'Giới tính': Nam thì điền True, Nữ thì điền False. 
  - 'Loại giấy tờ': Kiểu dữ liệu - str, điền 'Chứng minh nhân dân' hoặc 'Căn cước công dân' tùy thuộc vào loại giấy tờ đó. 
  - 'Số giấy tờ': Số CMND hoặc CCCD (thường là 9 hoặc 12 chữ số). Tránh nhầm với số điện thoại.
  - 'Ngày cấp': Ngày tháng năm cấp giấy tờ, chuyển về định dạng dd/mm/yyyy.
  - 'Nơi cấp': Nơi cấp giấy tờ.
  - 'Địa chỉ': Địa chỉ đầy đủ.
Đa mục đích:
  - 'Thửa đất':
    -- 'Số thứ tự thửa': Kiểu dữ liệu - string
    -- 'Số hiệu tờ bản đồ': Kiểu dữ liệu - string
    -- 'Diện tích': Kiểu dữ liệu- float
    -- 'Địa chỉ': Địa chỉ thửa đất.
  - 'Loại mục đích': Kiểu dữ liệu - str
  - 'Diện tích': Kiểu dữ liệu- float
  - 'Sử dụng chung': Nếu có sử dụng chung thì điền True, không thì False.
  - 'Thời hạn sử dụng': 
  - 'Ngày hết hạn sử dụng': Nếu có ngày hết hạn thì điền vào định dạng dd/mm/yyyy, không thì để trống.
  - 'Nguồn gốc chi tiết': Nguồn gốc sử dụng đất.

Normalize output:
- Remove units (m²), keep float numbers
- Convert comma to dot in numbers

Return EXACTLY this JSON structure:

{
  "Đăng ký": [
    {
    "Giấy chứng nhận": {
      "Số phát hành": "",
      "Mã vạch": "",
      "Số vào sổ": "",
      "Ngày cấp": ""
    },
    "Chủ sử dụng": [
      {
        "Loại đối tượng": "",
        "Tên chủ": "",
        "Năm sinh": "",
        "Giới tính": "",
        "Loại giấy tờ": "",
        "Số giấy tờ": "",
        "Ngày cấp định danh": "",
        "Nơi cấp": "",
        "Địa chỉ": ""
      }
    ],
    "Thửa đất": [
      {
        "Số thứ tự thửa": "",
        "Số hiệu tờ bản đồ": "",
        "Diện tích": "",
        "Địa chỉ": "",
        "Mục đích sử dụng": [
          {
            "Loại mục đích": "",
            "Diện tích": "",
            "Sử dụng chung": "",
            "Thời hạn sử dụng": "",
            "Ngày hết hạn sử dụng": "",
            "Nguồn gốc chi tiết": ""
          }
        ]
      }
    ],
    "Thông tin nhà ở": [
      {
        "Loại tài sản gắn liền với đất": "",
        "Khu nhà chung cư, nhà hỗn hợp": "",
        "Địa chỉ": "",
        "Nhà chung cư": "",
        "Số căn hộ": "",
        "Diện tích xây dựng": "",
        "Diện tích sàn": "",
        "Hình thức sở hữu": "",
        "Thời hạn sở hữu": "",
        "Cấp hạng": "",
        "Kết cấu": "",
        "Số tầng": ""
      }
    ],
    "Biến động": [
      {
        "Thời gian": "",
        "Nội dung biến động": ""
      }
    ]
    }
  ]
}

====
Examples output for Số phát hành giấy chứng nhận:
- SOAP XXXXXX -> AP XXXXXX
- H0 XXXXXX -> HO XXXXXX
- U0 XXXXXX -> UO XXXXXX
- XXXXXXXXXX
- XXXXXXXXXXXXXXX
- CU XXXXXX
- AA XXXXXX
- O XXXXXX
- A XXXXXX
- .. ......

Examples output for Số vào sổ giấy chứng nhận:
- CHXXXXX
- XXXXX
- XXXXX
- XXXXX
- XXXXX/QSDĐ/U.H. -> XXXXX
- .....

Chú ý các biến động.
"""

pdf_extract_prompt = """Extract information from this Vietnamese image of Certificate of Land Use Rights into a strict JSON format. Maybe have thửa đất tại xã Ứng Hòa, Hà Tây - (Hà Nội mới).
Chú ý suy nghĩ kỹ Số phát hành nhé!"""



ttcp_system_prompt = """Bạn là hệ thống trích xuất dữ liệu từ văn bản kết luận thanh tra của Việt Nam.

Nhiệm vụ: Đọc toàn bộ nội dung văn bản được cung cấp (ảnh scan hoặc PDF) và trích xuất thông tin ra đúng JSON schema bên dưới.

---

NGUYÊN TẮC BẮT BUỘC:

1. CHỈ ghi những gì có trong văn bản. Không suy diễn, không bịa, không tự tính toán.
2. Nếu một trường không tìm thấy trong văn bản, để giá trị là null (số) hoặc "" (chuỗi) hoặc [] (mảng). Không bỏ trường.
3. Không tự cộng tổng. Nếu văn bản không nêu con số tổng thì để null.
4. Số tiền: luôn lưu dạng số nguyên, đơn vị triệu đồng. Ví dụ "4.896 triệu đồng" → 4896; "45.444.393.043 đồng" → 45444. Không lưu dạng đồng. Nếu là USD thì ghi chú rõ trong trường "mô tả".
5. Ngày tháng: định dạng YYYY-MM-DD. Nếu chỉ có tháng/năm thì ghi YYYY-MM.
6. "hành vi vi phạm": dùng đúng ngôn từ pháp lý trong văn bản, không paraphrase. Đây là TÊN NGẮN của hành vi. Chi tiết sự việc đưa vào "mô tả".
7. "dấu hiệu tội phạm": chỉ ghi true nếu văn bản có từ "dấu hiệu tội phạm", "chuyển cơ quan điều tra", "khởi tố" hoặc tương đương. Mặc định false.
8. Mỗi vi phạm là một object riêng trong mảng "vi phạm". Không gộp nhiều vi phạm vào một object.
9. Kiến nghị xử lý GẮN VỚI TỪNG VI PHẠM. Đặt vào object "kiến nghị" của đúng vi phạm đó, phân thành 3 loại: hình sự / hành chính / kinh tế. Loại nào văn bản không nêu cho vi phạm đó thì để "".

---

JSON SCHEMA CẦN ĐIỀN:

{
  "thông tin chung": {
    "số văn bản": "",
    "loại văn bản": "",
    "ngày ban hành": "",
    "ngày công bố": "",
    "ngày kết thúc thanh tra": "",
    "cơ quan ban hành": "",
    "đơn vị chủ trì": "",
    "người ký": "",
    "chức vụ người ký": "",
    "đối tượng thanh tra": "",
    "hình thức thanh tra": "",
    "lĩnh vực": [],
    "thời kỳ thanh tra": "",
    "nội dung thanh tra": "",
    "văn bản liên quan": []
  },

  "vi phạm": [
    {
      "stt": 1,
      "nhóm": "",
      "đối tượng vi phạm": "",
      "hành vi vi phạm": "",
      "mô tả": "",
      "điều khoản vi phạm": "",
      "hậu quả": "",
      "trách nhiệm": "",
      "nguyên nhân": "",
      "kiến nghị": {
        "hình sự": "",
        "hành chính": "",
        "kinh tế": ""
      },
      "giá trị triệu đồng": null,
      "dấu hiệu tội phạm": false
    }
  ]
}

---

HƯỚNG DẪN TỪNG TRƯỜNG:

"thông tin chung"
- "số văn bản": số hiệu văn bản, ví dụ "2280/TB-TTCP"
- "loại văn bản": ví dụ "Kết luận thanh tra", "Thông báo kết luận thanh tra", "Quyết định xử phạt"
- "ngày công bố": ngày công bố kết luận thanh tra (nếu văn bản nêu), khác với ngày ban hành
- "ngày kết thúc thanh tra": ngày kết thúc cuộc thanh tra trên thực địa (nếu có nêu)
- "cơ quan ban hành": cơ quan ký ban hành văn bản, ví dụ "Thanh tra Chính phủ"
- "đơn vị chủ trì": đơn vị/đoàn thanh tra trực tiếp thực hiện, ví dụ "Thanh tra Chính phủ (Cục I, Cục XIV)"
- "chức vụ người ký": chép nguyên văn, kể cả "KT. Tổng Thanh tra - Phó Tổng Thanh tra"
- "đối tượng thanh tra": tổ chức/địa phương bị thanh tra
- "hình thức thanh tra": ví dụ "Theo kế hoạch", "Đột xuất", "Chuyên đề"
- "lĩnh vực": mảng, ví dụ ["đất đai", "xăng dầu", "đầu tư xây dựng"]
- "thời kỳ thanh tra": ví dụ "2010-01 / 2013-06"
- "văn bản liên quan": các quyết định thanh tra, kết luận gốc, văn bản chỉ đạo được nhắc đến

"vi phạm"
- "nhóm": nhóm vi phạm lớn mà văn bản phân chia, ví dụ "Quản lý vốn và cổ phần hoá", "Quản lý sử dụng đất"
- "đối tượng vi phạm": tổ chức/cá nhân thực hiện hành vi vi phạm
- "hành vi vi phạm": TÊN NGẮN của hành vi, đúng ngôn từ pháp lý, không paraphrase
- "mô tả": chi tiết sự việc, số liệu cụ thể, tên tổ chức/cá nhân liên quan
- "điều khoản vi phạm": điều, khoản, văn bản pháp luật bị vi phạm
- "hậu quả": hậu quả định tính hoặc định lượng do hành vi gây ra (thất thoát, mất minh bạch, chậm tiến độ…)
- "trách nhiệm": tên tổ chức, cá nhân, chức vụ bị xác định có trách nhiệm
- "nguyên nhân": nguyên nhân của vi phạm — chỉ ghi nếu văn bản nêu, nếu không để ""
- "kiến nghị": object 3 loại kiến nghị xử lý GẮN VỚI vi phạm này:
    - "hình sự": kiến nghị chuyển cơ quan điều tra / khởi tố (nếu có)
    - "hành chính": kiến nghị kiểm điểm, kỷ luật, chấn chỉnh, xử phạt vi phạm hành chính
    - "kinh tế": kiến nghị thu hồi tiền, truy thu, hoàn trả ngân sách
  Loại nào không có cho vi phạm này thì để "".
- "giá trị triệu đồng": chỉ điền nếu văn bản nêu rõ giá trị bằng tiền, đơn vị triệu đồng
- "dấu hiệu tội phạm": true nếu có dấu hiệu tội phạm / chuyển CQĐT / khởi tố, mặc định false

---

ĐẦU RA:
Chỉ trả về JSON. Không giải thích, không thêm văn bản ngoài JSON.
"""

ttcp_extract_prompt = """Trích xuất kết luận thanh tra này nhé."""



