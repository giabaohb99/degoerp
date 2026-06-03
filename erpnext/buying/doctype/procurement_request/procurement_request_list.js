frappe.listview_settings["Procurement Request"] = {
	get_indicator: function (doc) {
		if (doc.status === "Completed") {
			return [__("Hoàn thành"), "green", "status,=,Completed"];
		}
		if (doc.docstatus === 1) {
			return [__("Đã gửi"), "blue", "docstatus,=,1"];
		}
		if (doc.docstatus === 0) {
			return [__("Nháp"), "grey", "docstatus,=,0"];
		}
		if (doc.docstatus === 2) {
			return [__("Đã hủy"), "red", "docstatus,=,2"];
		}
	}
};
