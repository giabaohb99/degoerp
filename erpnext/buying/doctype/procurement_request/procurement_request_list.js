frappe.listview_settings["Procurement Request"] = {
	add_fields: ["purchase_status"],
	get_indicator: function (doc) {
		if (doc.status === "Completed") {
			return [__("Hoàn thành"), "green", "status,=,Completed"];
		}
		if (doc.status === "Processing") {
			return [__("Đang xử lý"), "orange", "status,=,Processing"];
		}
		if (doc.status === "Returned") {
			return [__("Trả lại"), "red", "status,=,Returned"];
		}
		if (doc.status === "Cancelled") {
			return [__("Đã hủy"), "red", "status,=,Cancelled"];
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
	},
	formatters: {
		purchase_status: function (value, df, doc) {
			if (!value) return "";

			let color = "grey";
			if (value === "Đã đặt hàng") color = "blue";
			else if (value === "Đã gửi ĐMH cho KT") color = "cyan";
			else if (value === "Đã nhận hàng") color = "purple";
			else if (value === "Hoàn thành") color = "green";
			else if (value === "Tạm ngưng") color = "yellow";
			else if (value === "Hủy đơn") color = "red";

			return `<span class="indicator-pill ${color} ellipsis">
				<span class="ellipsis">${__(value)}</span>
			</span>`;
		}
	}
};
