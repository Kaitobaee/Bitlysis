# Báo cáo đối chiếu đề tài và sản phẩm Bitlysis

## 1. Mục tiêu báo cáo

Báo cáo này đánh giá mức độ khớp giữa ý tưởng/đề tài Bitlysis và trạng thái sản phẩm hiện tại trong repository. Trọng tâm là xem webapp đã thể hiện đúng bản chất của đề tài hay chưa, đặc biệt ở phần đầu ra phân tích, tính minh bạch học thuật và vai trò hỗ trợ của AI.

## 2. Tóm tắt đề tài

Bitlysis được mô tả là một nền tảng phân tích dữ liệu trên đám mây cho người dùng không chuyên thống kê. Người dùng tải dữ liệu lên, hệ thống tự động profile, chọn pipeline phân tích phù hợp, hỗ trợ AI ở vai trò gợi ý/diễn giải, và xuất kết quả có cấu trúc, có thể kiểm chứng, kèm provenance.

Các ý chính của đề tài gồm:

- Phân tích dữ liệu theo quy trình tự động.
- Hỗ trợ các hướng phân tích như kiểm định giả thuyết, Cronbach’s Alpha, EFA, PLS-SEM, chuỗi thời gian.
- Có AI hỗ trợ nhưng không thay thế engine thống kê.
- Có cơ chế minh bạch học thuật: manifest, seed, version thư viện, hash dữ liệu, timestamp.
- Xuất báo cáo học thuật và dữ liệu đầu ra có cấu trúc.

## 3. Những gì sản phẩm hiện tại đã làm được

Qua cấu trúc repo và giao diện hiện có, sản phẩm đã thể hiện được một số phần quan trọng:

- Có luồng upload file, tạo job, theo dõi trạng thái và chạy phân tích.
- Có phân tách front-end Next.js và back-end FastAPI.
- Có pipeline R cho các phân tích nâng cao.
- Có hiển thị kết quả dạng cấu trúc ở `ResultSummary`.
- Có phần backend transparency: metadata job, profiling, analysis spec, raw JSON.
- Có cơ chế xuất ZIP và các thành phần phục vụ provenance.
- Có tài liệu methodology để giải thích khi nào dùng từng kiểu phân tích.

Nhìn chung, nền tảng kỹ thuật đã đi đúng hướng với đề tài.

## 4. Mức độ khớp với bản mô tả

### 4.1. Phần khớp tốt

- Ý tưởng cloud-based và không cần cài đặt đã có trong kiến trúc webapp.
- Có luồng phân tích theo job, phù hợp với mô tả “tải dữ liệu vào rồi hệ thống xử lý”.
- Có dữ liệu có cấu trúc, có kiểm tra trạng thái, có xuất kết quả.
- Có pipeline R đúng với phần nói về Cronbach’s Alpha, EFA, PLS-SEM.
- Có yếu tố minh bạch backend, phù hợp với narrative provenance.

### 4.2. Phần chưa khớp đủ mạnh

- Giao diện hiện tại chưa thể hiện rõ “bản chất phân tích” của hệ thống.
- Kết quả đầu ra còn thiên về hiển thị bảng, JSON, key-value; chưa đủ lớp diễn giải cho người không chuyên.
- Chưa thấy một khối tóm tắt học thuật nổi bật ở đầu kết quả, ví dụ:
  - loại dữ liệu
  - phương pháp được chọn
  - lý do chọn
  - giả định đã kiểm tra
  - kết luận cuối cùng
- AI đang xuất hiện ở một số luồng chat/web-analysis riêng, nhưng chưa được gắn chặt vào luồng phân tích dữ liệu chính.
- Báo cáo đề tài nói nhiều về “One-Click Comprehensive Analysis”, nhưng UI hiện tại chưa làm nổi bật logic ra quyết định của pipeline.

## 5. Đánh giá output hiện tại

Output hiện tại được xem là **đúng về mặt cấu trúc dữ liệu**, nhưng **chưa đủ giàu ngữ nghĩa**.

Điều này có nghĩa là:

- Người dùng có thể nhìn thấy kết quả kỹ thuật.
- Nhưng người dùng chưa hiểu ngay được tại sao hệ thống chọn phương pháp đó.
- Chưa có lớp “giải thích dễ hiểu” cho sinh viên, giảng viên, người không chuyên thống kê.
- Output chưa tạo cảm giác đây là một “statistical copilot” hoàn chỉnh mà mới giống một dashboard phân tích có vài lớp chi tiết kỹ thuật.

## 6. Những điểm cần chỉnh để khớp hơn với đề tài

### 6.1. Cần làm rõ lõi sản phẩm

Nên xác định Bitlysis xoay quanh 3 trụ cột:

- Tự động phân tích dữ liệu.
- AI hỗ trợ diễn giải và định hướng, không thay thế thống kê.
- Minh bạch học thuật và khả năng tái lập.

### 6.2. Cần nâng cấp output

Nên bổ sung 1 lớp tóm tắt đầu ra ngắn gọn, dễ đọc:

- Dữ liệu đầu vào có bao nhiêu cột, bao nhiêu dòng.
- Hệ thống đã chọn phương pháp nào.
- Vì sao chọn phương pháp đó.
- Các giả định nào đã được kiểm tra.
- Kết luận chính là gì.
- Có cảnh báo gì về dữ liệu hay không.

### 6.3. Cần tách rõ AI hỗ trợ và engine thống kê

Trong mô tả và trên UI, nên thể hiện rõ:

- AI chỉ hỗ trợ gợi ý và diễn giải.
- Phần tính toán và kiểm định do engine thống kê thực hiện.
- Người dùng có thể xem lại decision trace và provenance.

### 6.4. Cần giảm cảm giác “báo cáo kỹ thuật thô”

Các khối JSON/raw dữ liệu nên được để ở chế độ mở rộng, còn mặc định hiển thị:

- tóm tắt nhanh
- kết luận chính
- phương pháp
- biểu đồ quan trọng

## 7. Kết luận

Bitlysis hiện đã có nền tảng kỹ thuật tốt và khá khớp với ý tưởng đề tài, nhất là ở phần cloud workflow, pipeline phân tích và minh bạch backend. Tuy nhiên, output hiện tại chưa thể hiện trọn vẹn bản chất của đề tài như một nền tảng phân tích dữ liệu có AI hỗ trợ cho người dùng không chuyên.

Nếu muốn bản báo cáo và sản phẩm thuyết phục hơn, cần tập trung vào 3 việc:

1. Làm rõ output học thuật ở tầng đầu tiên.
2. Gắn AI vào đúng vai trò hỗ trợ diễn giải và định hướng.
3. Đưa provenance và decision trace ra thành điểm khác biệt cốt lõi.

## 8. Đề xuất ngắn

- Nếu dùng cho hồ sơ dự thi: nên viết lại mô tả theo hướng ngắn hơn, chắc hơn, ít khẳng định tuyệt đối hơn.
- Nếu dùng cho demo sản phẩm: nên ưu tiên một màn hình “Kết quả phân tích” có cấu trúc rõ ràng, thay vì để người dùng nhìn nhiều JSON thô.
- Nếu dùng cho hội đồng: nên chuẩn bị thêm 1 slide mô tả quy trình từ upload đến kết luận để chứng minh tính tự động hóa và minh bạch.
