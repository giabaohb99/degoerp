frappe.listview_settings["Product Survey"] = {
	get_indicator: function (doc) {
		if (doc.status === "Approved") {
			return [__("Đã duyệt"), "green", "status,=,Approved"];
		} else if (doc.status === "Returned") {
			return [__("Trả lại"), "red", "status,=,Returned"];
		} else if (doc.status === "Rejected") {
			return [__("Từ chối"), "red", "status,=,Rejected"];
		} else if (doc.status === "Cancelled") {
			return [__("Đã hủy"), "red", "status,=,Cancelled"];
		} else if (doc.status === "Submitted") {
			return [__("Đã gửi"), "blue", "status,=,Submitted"];
		} else if (doc.status === "Surveying") {
			return [__("Đang khảo sát"), "orange", "status,=,Surveying"];
		} else if (doc.status === "Under Review") {
			return [__("Đang đánh giá"), "orange", "status,=,Under Review"];
		} else {
			return [__("Nháp"), "grey", "status,=,Draft"];
		}
	}
};
