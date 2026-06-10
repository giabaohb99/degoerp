window.erpnext = window.erpnext || {};
erpnext.buying = erpnext.buying || {};

if (erpnext.buying.setup_buying_controller) {
	try {
		erpnext.buying.setup_buying_controller();
	} catch (e) {
		console.error("Error in setup_buying_controller:", e);
	}
}

frappe.ui.form.on("Procurement Request", {
	onload: function (frm) {
		if (frm.is_new() && !frm.doc.invoice_company) {
			let comp = frm.doc.company || frappe.defaults.get_default("company");
			if (comp) {
				frappe.db.get_value("Company", comp, "custom_default_invoice_company", (r) => {
					if (r && r.custom_default_invoice_company && !frm.doc.invoice_company) {
						frm.set_value("invoice_company", r.custom_default_invoice_company);
					} else if (!frm.doc.invoice_company) {
						frm.set_value("invoice_company", "CÔNG TY TNHH DEGO HOLDING");
					}
				});
			} else {
				frm.set_value("invoice_company", "CÔNG TY TNHH DEGO HOLDING");
			}
		}
	},

	setup: function (frm) {
		try {
			frm.custom_make_buttons = {
				"Purchase Order": "Create",
				"Supplier Survey": "Create",
				"Product Survey": "Create",
			};

			frm.set_query("receiving_warehouse", () => ({
				filters: {
					company: frm.doc.company,
					is_group: 0,
				},
			}));

			frm.set_query("warehouse", "items", () => ({
				filters: {
					company: frm.doc.company,
					is_group: 0,
				},
			}));
		} catch (e) {
			console.error("Error in Procurement Request setup:", e);
		}
	},

	refresh: function (frm) {
		try {
			if (frm.get_docfield("terms_section_break")) {
				frm.set_df_property("terms_section_break", "hidden", 1);
			}
			if (frm.get_docfield("printing_settings")) {
				frm.set_df_property("printing_settings", "hidden", 1);
			}

			if (frm.is_new() && !frm.doc.owner) {
				frm.doc.owner = frappe.session.user;
			}

			// Render attachment preview if any
			frm.trigger("render_attachment_preview");

			// Render purchase status indicator
			frm.trigger("render_purchase_status_indicator");

			// Setup roles and flags
			let user_roles = frappe.user_roles || [];
			let is_manager = user_roles.includes("Purchase Manager") ||
				user_roles.includes("Manufacturing Manager") ||
				user_roles.includes("System Manager") ||
				user_roles.includes("Administrator") ||
				frappe.session.user === "Administrator";

			let is_requester = user_roles.includes("Purchase Requester") && !is_manager;
			let is_purchase_user = user_roles.includes("Purchase User") && !is_manager;

			let status = frm.doc.status || "Draft";
			let is_assigned_user = (frm.doc.items || []).some(item => item.person_in_charge === frappe.session.user);

			// Handle field-level & form-level locking dynamically
			if (frm.doc.docstatus === 0) {
				// Reset read-only states for fields to standard defaults first
				let standard_fields = ["company", "requester", "transaction_date", "schedule_date", "person_in_charge", "invoice_company"];
				standard_fields.forEach(field => {
					frm.set_df_property(field, "read_only", 0);
				});


				let items_grid = frm.fields_dict && frm.fields_dict.items ? frm.fields_dict.items.grid : null;
				if (items_grid) {
					items_grid.cannot_add_rows = false;
					items_grid.cannot_delete_rows = false;
					items_grid.update_docfield_property("item_code", "read_only", 0);
					items_grid.update_docfield_property("item_name", "read_only", 0);
					items_grid.update_docfield_property("qty", "read_only", 0);
					items_grid.update_docfield_property("uom", "read_only", 0);
					items_grid.update_docfield_property("proposed_rate", "read_only", 0);
					items_grid.update_docfield_property("warehouse", "read_only", 0);
					items_grid.refresh();
				}

				// Enforce restrictions based on role & status ONLY for saved/existing documents
				if (!frm.is_new()) {
					if (is_requester) {
						if (status !== "Draft" && status !== "Returned") {
							// Lock completely if Submitted or Assigned or Approved
							frm.disable_form();
						}
					} else if (is_purchase_user) {
						if (status === "Assigned" && is_assigned_user) {
							// Lock key fields for Assigned Purchase User
							let fields_to_lock = ["company", "requester", "transaction_date", "schedule_date", "person_in_charge"];
							fields_to_lock.forEach(field => {
								frm.set_df_property(field, "read_only", 1);
							});

							// Keep invoice_company and remarks editable
							frm.set_df_property("invoice_company", "read_only", 0);
							frm.set_df_property("remarks", "read_only", 0);

							// Lock specific grid columns & row modification
							if (items_grid) {
								items_grid.cannot_add_rows = true;
								items_grid.cannot_delete_rows = true;
								items_grid.update_docfield_property("item_code", "read_only", 1);
								items_grid.update_docfield_property("item_name", "read_only", 1);
								items_grid.update_docfield_property("qty", "read_only", 1);
								items_grid.update_docfield_property("uom", "read_only", 1);
								items_grid.update_docfield_property("proposed_rate", "read_only", 1);
								items_grid.update_docfield_property("warehouse", "read_only", 1);
								items_grid.refresh();
							}
						} else {
							// Locked for other states where they are not assigned or not Assigned status
							frm.disable_form();
						}
					}
				}
			}

			// Custom action buttons based on status
			if (frm.doc.docstatus === 0) {
				// No custom Confirm button here, as the native "Xác nhận" (Submit) button is now available to the Requester

				// Button "Trả lại đơn" for Admin or Assigned Purchase User
				if (status === "Submitted" && is_manager) {
					frm.add_custom_button(__("Trả lại đơn"), () => {
						frappe.prompt([
							{
								label: __("Lý do trả lại"),
								fieldname: "reason",
								fieldtype: "Small Text",
								reqd: 1
							}
						], (values) => {
							frm.set_value("status", "Returned");
							frm.set_value("person_in_charge", "");
							let note = `\n\n<b>[Admin trả lại lúc ${frappe.datetime.now_datetime()}]</b>: ${values.reason}`;
							frm.set_value("remarks", (frm.doc.remarks || "") + note);
							frm.save().then(() => {
								frappe.show_alert({ message: __("Đã trả lại đơn yêu cầu"), indicator: 'orange' });
								frm.reload_doc();
							});
						}, __("Nhập lý do trả lại"));
					}, __("Hành động"));
				}

				if (status === "Assigned" && (is_manager || (is_purchase_user && is_assigned_user))) {
					frm.add_custom_button(__("Trả lại đơn"), () => {
						frappe.prompt([
							{
								label: __("Lý do trả lại"),
								fieldname: "reason",
								fieldtype: "Small Text",
								reqd: 1
							}
						], (values) => {
							frm.set_value("status", "Returned");
							frm.set_value("person_in_charge", "");
							let note = `\n\n<b>[Nhân sự mua hàng trả lại lúc ${frappe.datetime.now_datetime()}]</b>: ${values.reason}`;
							frm.set_value("remarks", (frm.doc.remarks || "") + note);
							frm.save().then(() => {
								frappe.show_alert({ message: __("Đã trả lại đơn yêu cầu"), indicator: 'orange' });
								frm.reload_doc();
							});
						}, __("Nhập lý do trả lại"));
					}, __("Hành động"));
				}
			}

			// Actions when document is submitted (docstatus === 1)
			if (frm.doc.docstatus === 1) {
				// Create PO, Survey, etc., shown when the request is submitted
				frm.add_custom_button(
					__("Đơn mua hàng"),
					function () {
						frappe.model.open_mapped_doc({
							method: "erpnext.buying.doctype.procurement_request.procurement_request.make_purchase_order",
							frm: frm,
						});
					},
					__("Create")
				);

				frm.add_custom_button(
					__("Khảo sát nhà cung cấp"),
					function () {
						frappe.model.open_mapped_doc({
							method: "erpnext.buying.doctype.procurement_request.procurement_request.make_supplier_survey",
							frm: frm,
						});
					},
					__("Create")
				);

				frm.add_custom_button(
					__("Khảo sát sản phẩm"),
					function () {
						frappe.model.open_mapped_doc({
							method: "erpnext.buying.doctype.procurement_request.procurement_request.make_product_survey",
							frm: frm,
						});
					},
					__("Create")
				);

				try {
					frm.page.set_inner_btn_group_as_primary(__("Create"));
				} catch (btn_err) {
					console.error("Error setting inner button group as primary:", btn_err);
				}

				// Button "Hoàn thành" (Complete) to mark request as completed
				if (status !== "Completed") {
					frm.add_custom_button(__("Hoàn thành"), () => {
						frappe.confirm(__("Xác nhận hoàn thành yêu cầu thu mua này?"), () => {
							frappe.call({
								method: "erpnext.buying.doctype.procurement_request.procurement_request.set_as_completed",
								args: { name: frm.doc.name },
								callback: function (r) {
									if (!r.exc) {
										frappe.show_alert({ message: __("Đã hoàn thành yêu cầu!"), indicator: 'green' });
										frm.reload_doc();
									}
								}
							});
						});
					});
				}

				// Button "Trả lại đơn" (Revert to Draft) for Admin/Manager to reject/return the request
				if (is_manager && status !== "Approved") {
					frm.add_custom_button(__("Trả lại đơn"), () => {
						frappe.prompt([
							{
								label: __("Lý do trả lại"),
								fieldname: "reason",
								fieldtype: "Small Text",
								reqd: 1
							}
						], (values) => {
							frappe.call({
								method: "erpnext.buying.doctype.procurement_request.procurement_request.revert_to_draft",
								args: { name: frm.doc.name },
								callback: function (r) {
									if (!r.exc) {
										// Set status to Returned and save reason
										frappe.call({
											method: "frappe.client.set_value",
											args: {
												doctype: "Procurement Request",
												name: frm.doc.name,
												fieldname: {
													"status": "Returned",
													"person_in_charge": "",
													"remarks": (frm.doc.remarks || "") + `\n\n<b>[Admin trả lại lúc ${frappe.datetime.now_datetime()}]</b>: ${values.reason}`
												}
											},
											callback: function () {
												frappe.show_alert({ message: __("Đã trả lại đơn yêu cầu"), indicator: 'orange' });
												frm.reload_doc();
											}
										});
									}
								}
							});
						}, __("Nhập lý do trả lại"));
					});
				}
			}
		} catch (e) {
			console.error("Error in Procurement Request refresh:", e);
		}
	},

	schedule_date(frm) {
		// Sync header Required Date to all items
		if (frm.doc.schedule_date) {
			(frm.doc.items || []).forEach((item) => {
				frappe.model.set_value(item.doctype, item.name, "schedule_date", frm.doc.schedule_date);
			});
			frm.refresh_field("items");
		}
	},

	receiving_warehouse(frm) {
		if (frm.doc.receiving_warehouse) {
			(frm.doc.items || []).forEach((item) => {
				frappe.model.set_value(item.doctype, item.name, "warehouse", frm.doc.receiving_warehouse);
			});
			frm.refresh_field("items");
		}
	},

	transaction_date(frm) {
		// Sync header Date to all items' schedule_date if schedule_date is not set
		if (frm.doc.transaction_date && !frm.doc.schedule_date) {
			(frm.doc.items || []).forEach((item) => {
				if (!item.schedule_date) {
					frappe.model.set_value(item.doctype, item.name, "schedule_date", frm.doc.transaction_date);
				}
			});
			frm.refresh_field("items");
		}
	},

	company(frm) {
		if (frm.doc.company) {
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Company",
					filters: { name: frm.doc.company },
					fieldname: ["custom_default_warehouse", "custom_default_invoice_company"]
				},
				callback: function (r) {
					if (r.message) {
						if (r.message.custom_default_warehouse) {
							frm.set_value("receiving_warehouse", r.message.custom_default_warehouse);
						}
						if (r.message.custom_default_invoice_company) {
							frm.set_value("invoice_company", r.message.custom_default_invoice_company);
						}
					}
				}
			});
		}
	},

	before_save: function (frm) {
		// Tự động chuyển trạng thái sang Assigned khi gán nhân sự phụ trách ở trạng thái Draft/Submitted
		let has_pic = (frm.doc.items || []).some(item => item.person_in_charge);
		if (has_pic && (frm.doc.status === "Submitted" || frm.doc.status === "Draft")) {
			frm.doc.status = "Assigned";
		}
	},

	attachment: function (frm) {
		frm.trigger("render_attachment_preview");
	},

	render_attachment_preview: function (frm) {
		let attachment = frm.doc.attachment;
		let preview_container_id = "procurement-attachment-preview";

		// Remove existing preview if any
		$(`#${preview_container_id}`).remove();

		if (attachment) {
			let is_pdf = attachment.toLowerCase().endsWith(".pdf");
			let is_img = attachment.toLowerCase().match(/\.(jpg|jpeg|png|gif)$/);

			let html = "";
			if (is_pdf) {
				html = `<div id="${preview_container_id}" style="margin-top: 15px; border: 1px solid #ddd; border-radius: 8px; padding: 10px; background-color: #fcfcfc; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
					<div style="font-weight: bold; margin-bottom: 8px; color: #555; display: flex; justify-content: space-between; align-items: center;">
						<span><i class="fa fa-file-pdf-o" style="color: #e74c3c; margin-right: 6px;"></i> Xem trước báo giá/tài liệu PDF</span>
						<a href="${attachment}" target="_blank" class="btn btn-xs btn-default" style="color: #555;"><i class="fa fa-external-link"></i> Mở tab mới</a>
					</div>
					<iframe src="${attachment}" style="width: 100%; height: 500px; border: none; border-radius: 4px;"></iframe>
				</div>`;
			} else if (is_img) {
				html = `<div id="${preview_container_id}" style="margin-top: 15px; border: 1px solid #ddd; border-radius: 8px; padding: 10px; background-color: #fcfcfc; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center;">
					<div style="font-weight: bold; margin-bottom: 8px; color: #555; text-align: left; display: flex; justify-content: space-between; align-items: center;">
						<span><i class="fa fa-file-image-o" style="color: #2ecc71; margin-right: 6px;"></i> Xem trước tài liệu hình ảnh</span>
						<a href="${attachment}" target="_blank" class="btn btn-xs btn-default" style="color: #555;"><i class="fa fa-external-link"></i> Mở tab mới</a>
					</div>
					<img src="${attachment}" style="max-width: 100%; max-height: 450px; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); cursor: pointer; transition: transform 0.2s;" class="preview-img" onclick="window.open('${attachment}', '_blank')"/>
				</div>`;
			} else {
				html = `<div id="${preview_container_id}" style="margin-top: 15px; border: 1px solid #ddd; border-radius: 8px; padding: 15px; background-color: #fcfcfc; box-shadow: 0 4px 6px rgba(0,0,0,0.05); display: flex; align-items: center; justify-content: space-between;">
					<div style="display: flex; align-items: center;">
						<i class="fa fa-file-o" style="font-size: 24px; color: #95a5a6; margin-right: 12px;"></i>
						<div>
							<div style="font-weight: bold; color: #333;">Tài liệu đã đính kèm</div>
							<div style="font-size: 11px; color: #7f8c8d;">Định dạng không hỗ trợ xem trước trực tiếp</div>
						</div>
					</div>
					<a href="${attachment}" target="_blank" class="btn btn-sm btn-default" style="border: 1px solid #ccc;"><i class="fa fa-download"></i> Tải về máy</a>
				</div>`;
			}

			frm.fields_dict.attachment.$wrapper.append(html);
		}
	},

	purchase_status: function (frm) {
		frm.trigger("render_purchase_status_indicator");
	},

	render_purchase_status_indicator: function (frm) {
		let indicator_area = frm.page.wrapper.find(".title-area");
		indicator_area.find(".purchase-status-indicator").remove();

		if (frm.doc.purchase_status) {
			let color = "grey";
			if (frm.doc.purchase_status === "Đã đặt hàng") color = "blue";
			else if (frm.doc.purchase_status === "Đã gửi ĐMH cho KT") color = "cyan";
			else if (frm.doc.purchase_status === "Đã nhận hàng") color = "purple";
			else if (frm.doc.purchase_status === "Hoàn thành") color = "green";
			else if (frm.doc.purchase_status === "Tạm ngưng") color = "yellow";
			else if (frm.doc.purchase_status === "Hủy đơn") color = "red";

			let pill_html = `<span class="indicator-pill ${color} purchase-status-indicator" style="margin-left: 10px; font-size: var(--text-xs); line-height: 1.5;">${__(frm.doc.purchase_status)}</span>`;
			let default_indicator = indicator_area.find(".indicator-pill").first();
			if (default_indicator.length) {
				$(pill_html).insertAfter(default_indicator);
			} else {
				indicator_area.find(".title-text").after(pill_html);
			}
		}
	},
});

frappe.ui.form.on("Procurement Request Item", {
	items_add(frm, cdt, cdn) {
		// Set schedule_date from header when adding new item
		let schedule = frm.doc.schedule_date || frm.doc.transaction_date;
		if (schedule) {
			frappe.model.set_value(cdt, cdn, "schedule_date", schedule);
		}
		// Set warehouse from header receiving_warehouse if set
		if (frm.doc.receiving_warehouse) {
			frappe.model.set_value(cdt, cdn, "warehouse", frm.doc.receiving_warehouse);
		}
	},

	item_code(frm, cdt, cdn) {
		var d = locals[cdt][cdn];
		if (d.item_code) {
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Item",
					filters: { name: d.item_code },
					fieldname: [
						"item_name",
						"description",
						"stock_uom",
						"item_group",
						"brand",
						"image",
					],
				},
				callback: function (r) {
					if (r.message) {
						frappe.model.set_value(cdt, cdn, {
							item_name: r.message.item_name,
							description: r.message.description,
							uom: r.message.stock_uom,
							item_group: r.message.item_group,
							brand: r.message.brand,
							image: r.message.image,
						});
					}
				},
			});
		}
	},

	form_render: function (frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		let grid_form = frm.fields_dict.items.grid.grid_form;
		if (row.item_class) {
			frappe.db.get_value("UOM", row.item_class, "description", (r) => {
				let desc = r && r.description ? r.description : "";
				if (row.item_class_description !== desc) {
					frappe.model.set_value(cdt, cdn, "item_class_description", desc);
				}
				if (grid_form && grid_form.fields_dict && grid_form.fields_dict.item_class) {
					grid_form.fields_dict.item_class.set_description(desc);
				}
			});
		} else {
			if (row.item_class_description) {
				frappe.model.set_value(cdt, cdn, "item_class_description", "");
			}
			if (grid_form && grid_form.fields_dict && grid_form.fields_dict.item_class) {
				grid_form.fields_dict.item_class.set_description("");
			}
		}
	},

	item_class: function(frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		let grid_form = frm.fields_dict.items.grid.grid_form;
		if (row.item_class) {
			frappe.db.get_value("UOM", row.item_class, "description", (r) => {
				let desc = r && r.description ? r.description : "";
				frappe.model.set_value(cdt, cdn, "item_class_description", desc);
				if (grid_form && grid_form.fields_dict && grid_form.fields_dict.item_class) {
					grid_form.fields_dict.item_class.set_description(desc);
				}
			});
		} else {
			frappe.model.set_value(cdt, cdn, "item_class_description", "");
			if (grid_form && grid_form.fields_dict && grid_form.fields_dict.item_class) {
				grid_form.fields_dict.item_class.set_description("");
			}
		}
	},


	qty(frm, cdt, cdn) {
		calculate_item_amount(frm, cdt, cdn);
	},

	proposed_rate(frm, cdt, cdn) {
		calculate_item_amount(frm, cdt, cdn);
	},

	items_remove(frm) {
		calculate_totals(frm);
	},
});

function calculate_item_amount(frm, cdt, cdn) {
	let d = locals[cdt][cdn];
	let qty = cint(d.qty) || 0;
	let rate = flt(d.proposed_rate) || 0;
	let amount = qty * rate;
	frappe.model.set_value(cdt, cdn, "amount", amount);
	calculate_totals(frm);
}

function calculate_totals(frm) {
	let total_qty = 0;
	let total_amount = 0;

	(frm.doc.items || []).forEach((item) => {
		total_qty += cint(item.qty) || 0;
		total_amount += flt(item.amount) || 0;
	});

	frm.set_value("total_qty", total_qty);
	frm.set_value("total_amount", total_amount);
}

let BaseController = (window.erpnext && erpnext.buying && erpnext.buying.BuyingController) ?
	erpnext.buying.BuyingController : class { setup() { } refresh() { } };

erpnext.buying.ProcurementRequestController = class ProcurementRequestController extends BaseController {
	setup() {
		if (super.setup) super.setup();
	}
	refresh() {
		if (super.refresh) super.refresh();
	}

	calculate_taxes_and_totals() {
		return;
	}

	tc_name() {
		if (this.get_terms) {
			this.get_terms();
		}
	}
};

// for backward compatibility: combine new and previous states
if (window.cur_frm && window.extend_cscript) {
	try {
		extend_cscript(
			cur_frm.cscript,
			new erpnext.buying.ProcurementRequestController({ frm: cur_frm })
		);
	} catch (e) {
		console.error("Error extending cscript for Procurement Request:", e);
	}
}
