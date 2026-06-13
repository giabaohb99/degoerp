// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

// render
frappe.listview_settings["Purchase Invoice"] = {
	add_fields: [
		"supplier",
		"supplier_name",
		"base_grand_total",
		"outstanding_amount",
		"due_date",
		"company",
		"currency",
		"is_return",
		"release_date",
		"on_hold",
		"represents_company",
		"is_internal_supplier",
	],
	get_indicator(doc) {
		if (doc.status == "Debit Note Issued") {
			return [__(doc.status), "gray", "status,=," + doc.status];
		}

		if (flt(doc.outstanding_amount) > 0 && doc.docstatus == 1 && cint(doc.on_hold)) {
			if (!doc.release_date) {
				return [__("On Hold"), "darkgrey"];
			} else if (frappe.datetime.get_diff(doc.release_date, frappe.datetime.nowdate()) > 0) {
				return [__("Temporarily on Hold"), "darkgrey"];
			}
		}

		const status_colors = {
			Unpaid: "orange",
			Paid: "green",
			Return: "gray",
			Overdue: "red",
			"Partly Paid": "yellow",
			"Internal Transfer": "darkgrey",
		};

		if (status_colors[doc.status]) {
			return [__(doc.status), status_colors[doc.status], "status,=," + doc.status];
		}
	},

	onload: function (listview) {
		if (frappe.model.can_create("Purchase Receipt")) {
			listview.page.add_action_item(__("Purchase Receipt"), () => {
				erpnext.bulk_transaction_processing.create(listview, "Purchase Invoice", "Purchase Receipt");
			});
		}

		if (frappe.model.can_create("Payment Entry")) {
			listview.page.add_action_item(__("Payment"), () => {
				erpnext.bulk_transaction_processing.create(listview, "Purchase Invoice", "Payment Entry");
			});

			listview.page.add_action_item(__("Thanh toán gộp"), () => {
				erpnext.bulk_grouped_payment.create(listview);
			});
		}
	},
};

// Thanh toán gộp - Group invoices by supplier and create one Payment Entry per group
frappe.provide("erpnext.bulk_grouped_payment");

$.extend(erpnext.bulk_grouped_payment, {
	create: function (listview) {
		let checked_items = listview.get_checked_items();
		if (!checked_items || checked_items.length === 0) {
			frappe.msgprint(__("Vui lòng chọn ít nhất 1 hóa đơn."));
			return;
		}

		let invoice_names = checked_items.map(item => item.name);

		// Gọi API preview trước
		frappe.call({
			method: "erpnext.accounts.doctype.payment_entry.bulk_payment.get_grouped_payment_preview",
			args: { invoices: invoice_names },
			freeze: true,
			freeze_message: __("Đang phân tích hóa đơn..."),
			callback: function (r) {
				if (!r.message) return;

				let data = r.message;
				let groups = data.groups || [];
				let skipped = data.skipped || [];

				if (groups.length === 0) {
					let msg = __("Không có hóa đơn nào hợp lệ để tạo thanh toán gộp.");
					if (skipped.length > 0) {
						msg += "<br><br><b>" + __("Hóa đơn bị bỏ qua:") + "</b><ul>";
						skipped.forEach(s => {
							msg += `<li>${s.invoice}: ${s.reason}</li>`;
						});
						msg += "</ul>";
					}
					frappe.msgprint(msg);
					return;
				}

				// Hiển thị dialog xác nhận
				erpnext.bulk_grouped_payment.show_confirm_dialog(invoice_names, groups, skipped);
			}
		});
	},

	show_confirm_dialog: function (invoice_names, groups, skipped) {
		let total_amount = groups.reduce((sum, g) => sum + g.total_outstanding, 0);
		let total_invoices = groups.reduce((sum, g) => sum + g.invoice_count, 0);

		let summary = `<div style="margin-bottom: 15px;">
			<p><b>${__("Tổng quan:")}</b></p>
			<ul>
				<li>${__("Số nhà cung cấp:")} <b>${groups.length}</b></li>
				<li>${__("Số hóa đơn hợp lệ:")} <b>${total_invoices}</b></li>
				<li>${__("Số Payment Entry sẽ tạo:")} <b>${groups.length}</b></li>
				<li>${__("Tổng tiền thanh toán:")} <b>${format_currency(total_amount)}</b></li>
			</ul>
		</div>`;

		summary += `<div style="margin-bottom: 15px;">
			<p><b>${__("Chi tiết theo nhà cung cấp:")}</b></p>
			<table class="table table-bordered table-condensed" style="font-size: 12px;">
				<thead>
					<tr>
						<th>${__("Nhà cung cấp")}</th>
						<th style="text-align:center">${__("Số hóa đơn")}</th>
						<th style="text-align:right">${__("Tổng thanh toán")}</th>
					</tr>
				</thead>
				<tbody>`;

		groups.forEach(g => {
			summary += `<tr>
				<td>${g.supplier_name || g.supplier}</td>
				<td style="text-align:center">${g.invoice_count}</td>
				<td style="text-align:right">${format_currency(g.total_outstanding, g.currency)}</td>
			</tr>`;
		});

		summary += `</tbody></table></div>`;

		if (skipped.length > 0) {
			summary += `<div style="margin-bottom: 10px;">
				<p><b>${__("Hóa đơn bị bỏ qua")} (${skipped.length}):</b></p>
				<ul style="font-size: 12px; color: #888;">`;
			skipped.forEach(s => {
				summary += `<li>${s.invoice}: ${s.reason}</li>`;
			});
			summary += `</ul></div>`;
		}

		summary += `<p style="color: #666; font-size: 12px;">
			<i>${__("Payment Entry sẽ được tạo ở trạng thái Draft để bạn review trước khi submit.")}</i>
		</p>`;

		let d = new frappe.ui.Dialog({
			title: __("Xác nhận Thanh toán gộp"),
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "summary_html",
					options: summary
				}
			],
			primary_action_label: __("Tạo thanh toán gộp"),
			primary_action: function () {
				d.hide();
				erpnext.bulk_grouped_payment.execute(invoice_names);
			}
		});

		d.show();
		d.$wrapper.find(".modal-dialog").css("max-width", "600px");
	},

	execute: function (invoice_names) {
		frappe.call({
			method: "erpnext.accounts.doctype.payment_entry.bulk_payment.bulk_create_grouped_payments",
			args: { invoices: invoice_names },
			freeze: true,
			freeze_message: __("Đang tạo phiếu thanh toán gộp..."),
			callback: function (r) {
				if (!r.message) return;

				let result = r.message;
				let created = result.created || [];
				let skipped_list = result.skipped || [];
				let failed = result.failed || [];

				let msg = "";

				if (created.length > 0) {
					msg += `<p style="color: green;"><b>✓ ${__("Đã tạo thành công")} ${created.length} ${__("phiếu thanh toán:")}</b></p><ul>`;
					created.forEach(c => {
						msg += `<li><a href="/app/payment-entry/${c.payment_entry}">${c.payment_entry}</a>
							- ${c.supplier_name || c.supplier}
							(${c.invoice_count} ${__("hóa đơn")},
							${format_currency(c.total)})</li>`;
					});
					msg += "</ul>";
				}

				if (skipped_list.length > 0) {
					msg += `<p style="color: orange;"><b>⚠ ${__("Bỏ qua")} ${skipped_list.length} ${__("hóa đơn:")}</b></p><ul>`;
					skipped_list.forEach(s => {
						msg += `<li>${s.invoice}: ${s.reason}</li>`;
					});
					msg += "</ul>";
				}

				if (failed.length > 0) {
					msg += `<p style="color: red;"><b>✗ ${__("Lỗi")} ${failed.length} ${__("hóa đơn:")}</b></p><ul>`;
					failed.forEach(f => {
						msg += `<li>${f.invoice}: ${f.error}</li>`;
					});
					msg += "</ul>";
				}

				frappe.msgprint({
					title: __("Kết quả Thanh toán gộp"),
					message: msg,
					indicator: created.length > 0 ? "green" : "red"
				});

				cur_list.refresh();
			}
		});
	}
});
