# degoErp - ERPNext Customizations

Đây là kho mã nguồn của ứng dụng **ERPNext** đã được tùy chỉnh (customized) dành riêng cho hệ thống ERP của **DEGO**. Phiên bản này bổ sung các tính năng nâng cao liên quan đến Quản lý mua hàng (Procurement), Hóa đơn (Purchase Invoice), và thông tin Nhà cung cấp (Supplier).

---

## 🚀 Các Tính Năng Tùy Chỉnh (Custom Features)

### 1. Quy Trình Yêu Cầu Thu Mua (Procurement Request)
* **Quy trình tối giản**: Loại bỏ bước phê duyệt trung gian (`Approved`). Ngay sau khi Yêu cầu thu mua được **Xác nhận (Submitted)**, nhóm nút **Tạo (Create)** bao gồm:
  - *Đơn mua hàng (Purchase Order)*
  - *Khảo sát nhà cung cấp (Supplier Survey)*
  - *Khảo sát sản phẩm (Product Survey)*
  sẽ xuất hiện ngay lập tức để người dùng tiếp tục luồng mua hàng mà không cần chờ duyệt.
* **Nút Hoàn thành chủ động**: Bổ sung nút **"Hoàn thành" (Complete)** cạnh nhóm nút Tạo khi yêu cầu ở trạng thái đã gửi (`docstatus === 1`) giúp người phụ trách đóng yêu cầu mua hàng chủ động.
* **Xem trước tài liệu đính kèm**: Hỗ trợ xem trực tiếp các file báo giá/tài liệu định dạng PDF hoặc hình ảnh (PNG, JPG, etc.) ngay trên giao diện Yêu cầu thu mua.

### 2. Liên Kết Dữ Liệu & Mapped Fields
* Khi tạo Đơn mua hàng (Purchase Order) và Hóa đơn mua hàng (Purchase Invoice) từ Yêu cầu thu mua, hệ thống tự động ánh xạ thông tin nguồn gốc ở mức chi tiết từng mặt hàng (`procurement_request` và `procurement_request_item`).
* Hỗ trợ liên kết hai chiều giữa các tài liệu trên màn hình bảng điều khiển liên kết (Connections/Dashboard).

### 3. Đồng Bộ Trạng Thái Thanh Toán
* **Đơn mua hàng (Purchase Order)**: Bổ sung 2 trường ảo tự động tính toán từ các Hóa đơn liên kết:
  - *Đã thanh toán* (`custom_paid_amount`)
  - *Còn lại* (`custom_outstanding_amount`)
* **Hóa đơn mua hàng (Purchase Invoice)**: Đưa 2 trường *Đã thanh toán* (`paid_amount`) và *Còn lại* (`outstanding_amount`) hiển thị trực quan ngay cạnh tổng tiền hóa đơn giúp kế toán dễ dàng theo dõi.

### 4. Tên Trên Hóa Đơn (custom_invoice_name)
* Thêm trường **Tên trên hóa đơn** (`custom_invoice_name`) vào chi tiết hàng hóa ở cả Đơn mua hàng và Hóa đơn mua hàng.
* Trường này được bật tùy chọn luôn luôn hiển thị trực tiếp trên lưới sản phẩm (`in_list_view = 1`) mà không cần click mở rộng dòng.

### 5. Thông Tin Số & Ngày Hóa Đơn (bill_no / bill_date)
* Khắc phục lỗi ẩn trường khi hóa đơn ở trạng thái đã gửi/thanh toán (Paid/Submitted) bằng cách loại bỏ Section Break gập (`collapsible`).
* Đưa trường **Số hóa đơn** (`bill_no`) và **Ngày hóa đơn** (`bill_date`) lên phần Header chính của Hóa đơn mua hàng để kế toán nhập liệu thủ công thuận tiện nhất.

### 6. Quản Lý Thông Tin Nhà Cung Cấp (Supplier)
* **Hợp đồng & Hạn hợp đồng**:
  - Trường **Hợp đồng** (`custom_contract`, kiểu `Attach`) để tải lên file hợp đồng.
  - Trường **Thời gian hết hạn hợp đồng** (`custom_contract_expiry`, kiểu `Date`) để theo dõi hạn hợp đồng.
  - Cột ngày hết hạn được tối ưu hiển thị trực tiếp ngoài danh sách nhà cung cấp, đứng ngay trước cột *Nhóm nhà cung cấp*.
* **Người đại diện pháp luật**: Bổ sung 4 trường thông tin đại diện pháp luật của nhà cung cấp dưới mục **Thông tin thêm**:
  - *Người đại diện pháp luật* (`custom_rep_name`)
  - *Chức vụ người đại diện* (`custom_rep_designation`)
  - *Số điện thoại người đại diện* (`custom_rep_phone`)
  - *Email người đại diện* (`custom_rep_email`)
* **Tối ưu Danh sách & Popup Tạo nhanh**:
  - Ẩn cột *Tiền tệ thanh toán* (`default_currency`) khỏi màn hình danh sách.
  - Đưa trường **Mã số thuế** (`tax_id`) và **Chi tiết nhà cung cấp** (`supplier_details`) vào popup tạo nhanh để nhập liệu tức thì khi tạo nhà cung cấp.

---

## 🛠 Hướng Dẫn Deploy (VPS Deployment)

Hệ thống sử dụng kịch bản deploy tự động tại thư mục `/scratch` để đồng bộ code local lên các container Docker của VPS sản xuất:

```bash
python d:\erp\scratch\deploy_po_pi_enhancements.py
```

Kịch bản deploy sẽ tự động:
1. Đồng bộ các tệp `.js`, `.py`, `.json` tùy chỉnh vào các container Docker của VPS.
2. Thực hiện `bench migrate` để di trú database schema.
3. Chạy `bench clear-cache` để xóa cache frontend.
4. Restart các container backend, queue, và scheduler để áp dụng cập nhật.

---
*Bản quyền tùy chỉnh thuộc về DEGO ERP Team.*
