// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Product Survey", {
	setup: function (frm) {
		frm.trigger("set_item_filters");
	},

	refresh: function (frm) {
		// Inject CSS to force show all form-groups, section breaks and empty sections
		frappe.dom.inject_css(`
			[data-doctype="Product Survey"] .form-group {
				display: block !important;
			}
			[data-doctype="Product Survey"] .empty-section {
				display: block !important;
			}
			[data-doctype="Product Survey"] .frappe-control.hide-control {
				display: block !important;
			}
		`);

		// Force show important sections and empty fields after approval
		setTimeout(() => {
			if (frm.meta && frm.meta.fields) {
				frm.meta.fields.forEach(df => {
					if (!df.hidden) {
						frm.toggle_display(df.fieldname, true);
						let field = frm.fields_dict[df.fieldname];
						if (field && field.$wrapper) {
							field.$wrapper.removeClass("hide-control").show();
							field.$wrapper.find(".form-group").addClass("has-value").show();
						}
					}
				});
				// Force show all empty sections
				$(frm.wrapper).find(".empty-section").removeClass("empty-section").show();
				$(frm.wrapper).find(".hide-control").each(function() {
					let fieldname = $(this).attr("data-fieldname");
					let df = frm.meta.fields.find(f => f.fieldname === fieldname);
					if (df && !df.hidden) {
						$(this).removeClass("hide-control").show();
						$(this).find(".form-group").addClass("has-value").show();
					}
				});
			}
		}, 150);

		frm.trigger("set_item_filters");

		if (frm.doc.docstatus === 1) {
			// Role-based Allow on Submit permission check
			let is_manager = frappe.user.has_role("Purchase Manager") || 
			                 frappe.user.has_role("Manufacturing Manager") || 
			                 frappe.user.has_role("System Manager") || 
			                 frappe.user.has_role("Administrator") ||
			                 frappe.session.user === "Administrator";
			
			frm.meta.fields.forEach(df => {
				if (df.allow_on_submit) {
					frm.set_df_property(df.fieldname, "read_only", !is_manager);
				}
			});
			frm.set_df_property("items", "read_only", !is_manager);

			frm.add_custom_button(__("Tạo Sản Phẩm"), () => {
				frappe.model.with_doctype("Item", () => {
					let item_doc = frappe.model.get_new_doc("Item");
					item_doc.item_name = frm.doc.item_name;
					frappe.ui.form.make_quick_entry("Item", null, null, item_doc);
				});
			});

			if (is_manager) {
				frm.add_custom_button(__("Đưa về bản nháp"), () => {
					frappe.confirm(__("Bạn có chắc chắn muốn đưa phiếu này về bản nháp không?"), () => {
						frappe.call({
							method: "erpnext.buying.doctype.product_survey.product_survey.revert_to_draft",
							args: { name: frm.doc.name },
							callback: function(r) {
								if (!r.exc) {
									frappe.show_alert({message: __("Đã chuyển về bản nháp"), indicator: 'green'});
									frm.reload_doc();
								}
							}
						});
					});
				});
			}
		}
	},

	procurement_request: function (frm) {
		frm.set_value("item_code", "");
		frm.set_value("requester", "");
		frm.trigger("set_item_filters");

		if (frm.doc.procurement_request) {
			// Fetch and set requester
			frappe.db.get_value("Procurement Request", frm.doc.procurement_request, "requester", (r) => {
				if (r && r.requester) {
					frm.set_value("requester", r.requester);
				}
			});

			frappe.model.with_doc("Procurement Request", frm.doc.procurement_request, function () {
				let pr = frappe.model.get_doc("Procurement Request", frm.doc.procurement_request);
				let items = (pr.items || []).map(row => row.item_code);
				// If only 1 item in procurement request, auto fill it
				if (items.length === 1 && !frm.doc.item_code) {
					frm.set_value("item_code", items[0]);
				}
			});
		}
	},

	set_item_filters: function (frm) {
		if (frm.doc.procurement_request) {
			frappe.model.with_doc("Procurement Request", frm.doc.procurement_request, function () {
				let pr = frappe.model.get_doc("Procurement Request", frm.doc.procurement_request);
				let items = (pr.items || []).map(row => row.item_code);
				if (items.length > 0) {
					frm.set_query("item_code", function () {
						return {
							filters: [
								["Item", "name", "in", items]
							]
						};
					});
				}
			});
		} else {
			frm.set_query("item_code", function () {
				return {};
			});
		}
	},

	item_code: function (frm) {
		if (frm.doc.item_code) {
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Item",
					filters: { name: frm.doc.item_code },
					fieldname: ["item_name", "stock_uom"]
				},
				callback: function (r) {
					if (r.message) {
						frm.set_value("item_name", r.message.item_name);
						frm.set_value("item_class", r.message.stock_uom);
					}
				}
			});
		} else {
			frm.set_value("item_name", "");
			frm.set_value("item_class", "");
		}
	}
});

frappe.ui.form.on("Product Survey Item", {
	supplier: function (frm, cdt, cdn) {
		let d = locals[cdt][cdn];
		if (d.supplier) {
			frappe.db.get_value("Supplier", d.supplier, "supplier_name", (r) => {
				if (r) {
					frappe.model.set_value(cdt, cdn, "supplier_name", r.supplier_name);
				}
			});
		} else {
			frappe.model.set_value(cdt, cdn, "supplier_name", "");
		}
	},

	rate: function (frm, cdt, cdn) {
		calculate_row_amount(frm, cdt, cdn);
	},

	vat: function (frm, cdt, cdn) {
		calculate_row_amount(frm, cdt, cdn);
	}
});

function calculate_row_amount(frm, cdt, cdn) {
	let d = locals[cdt][cdn];
	let rate = flt(d.rate) || 0;
	let vat = flt(d.vat) || 0;
	let amount = rate * (1.0 + vat / 100.0);
	
	frappe.model.set_value(cdt, cdn, "amount", amount);
	
	// Default converted_amount to amount if not explicitly set
	if (!d.converted_amount) {
		frappe.model.set_value(cdt, cdn, "converted_amount", amount);
	}
}
