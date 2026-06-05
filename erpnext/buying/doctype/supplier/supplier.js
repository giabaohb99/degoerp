// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Supplier", {
	setup: function (frm) {
		frm.set_query("default_price_list", { buying: 1 });
		if (frm.doc.__islocal == 1) {
			frm.set_value("represents_company", "");
		}
		frm.set_query("account", "accounts", function (doc, cdt, cdn) {
			let d = locals[cdt][cdn];
			return {
				filters: {
					account_type: "Payable",
					root_type: "Liability",
					company: d.company,
					is_group: 0,
				},
			};
		});

		frm.set_query("advance_account", "accounts", function (doc, cdt, cdn) {
			let d = locals[cdt][cdn];
			return {
				filters: {
					account_type: "Payable",
					root_type: "Asset",
					company: d.company,
					is_group: 0,
				},
			};
		});

		frm.set_query("default_bank_account", function () {
			return {
				filters: {
					is_company_account: 1,
				},
			};
		});

		frm.set_query("supplier_primary_contact", function (doc) {
			return {
				query: "erpnext.buying.doctype.supplier.supplier.get_supplier_primary",
				filters: {
					supplier: doc.name,
					type: "Contact",
				},
			};
		});

		frm.set_query("supplier_primary_address", function (doc) {
			return {
				query: "erpnext.buying.doctype.supplier.supplier.get_supplier_primary",
				filters: {
					supplier: doc.name,
					type: "Address",
				},
			};
		});

		frm.set_query("user", "portal_users", function (doc) {
			return {
				filters: {
					ignore_user_type: true,
				},
			};
		});

		frm.make_methods = {
			"Bank Account": () => erpnext.utils.make_bank_account(frm.doc.doctype, frm.doc.name),
			"Pricing Rule": () => frm.trigger("make_pricing_rule"),
		};
	},

	supplier_group(frm) {
		if (frm.doc.supplier_group) {
			frm.trigger("get_supplier_group_details");
		}
	},

	refresh: function (frm) {
		if (frappe.defaults.get_default("supp_master_name") != "Naming Series") {
			frm.toggle_display("naming_series", false);
		} else {
			erpnext.toggle_naming_series();
		}

		if (frm.doc.__islocal) {
			hide_field(["address_html", "contact_html"]);
			frappe.contacts.clear_address_and_contact(frm);
			frm.toggle_display("contracts_section", false);
		} else {
			unhide_field(["address_html", "contact_html"]);
			frappe.contacts.render_address_and_contact(frm);

			// custom buttons
			frm.add_custom_button(
				__("Accounting Ledger"),
				function () {
					frappe.set_route("query-report", "General Ledger", {
						party_type: "Supplier",
						party: frm.doc.name,
						party_name: frm.doc.supplier_name,
					});
				},
				__("View")
			);

			frm.add_custom_button(
				__("Accounts Payable"),
				function () {
					frappe.set_route("query-report", "Accounts Payable", {
						party_type: "Supplier",
						party: frm.doc.name,
					});
				},
				__("View")
			);

			if (
				cint(frappe.defaults.get_default("enable_common_party_accounting")) &&
				frappe.model.can_create("Party Link")
			) {
				frm.add_custom_button(
					__("Link with Customer"),
					function () {
						frm.trigger("show_party_link_dialog");
					},
					__("Actions")
				);
			}

			// indicators
			erpnext.utils.set_party_dashboard_indicators(frm);

			// Render contracts table
			frm.toggle_display("contracts_section", true);
			render_contracts_table(frm);
		}
	},
	get_supplier_group_details: function (frm) {
		frappe.call({
			method: "get_supplier_group_details",
			doc: frm.doc,
			callback: function () {
				frm.refresh();
			},
		});
	},

	supplier_primary_address: function (frm) {
		if (frm.doc.supplier_primary_address) {
			frappe.call({
				method: "frappe.contacts.doctype.address.address.get_address_display",
				args: {
					address_dict: frm.doc.supplier_primary_address,
				},
				callback: function (r) {
					frm.set_value("primary_address", frappe.utils.html2text(r.message));
				},
			});
		}
		if (!frm.doc.supplier_primary_address) {
			frm.set_value("primary_address", "");
		}
	},

	supplier_primary_contact: function (frm) {
		if (!frm.doc.supplier_primary_contact) {
			frm.set_value("mobile_no", "");
			frm.set_value("email_id", "");
		}
	},

	is_internal_supplier: function (frm) {
		if (frm.doc.is_internal_supplier == 1) {
			frm.toggle_reqd("represents_company", true);
		} else {
			frm.toggle_reqd("represents_company", false);
		}
	},
	show_party_link_dialog: function (frm) {
		const dialog = new frappe.ui.Dialog({
			title: __("Select a Customer"),
			fields: [
				{
					fieldtype: "Link",
					label: __("Customer"),
					options: "Customer",
					fieldname: "customer",
					reqd: 1,
				},
			],
			primary_action: function ({ customer }) {
				frappe.call({
					method: "erpnext.accounts.doctype.party_link.party_link.create_party_link",
					args: {
						primary_role: "Supplier",
						primary_party: frm.doc.name,
						secondary_party: customer,
					},
					freeze: true,
					callback: function () {
						dialog.hide();
						frappe.msgprint({
							message: __("Successfully linked to Customer"),
							alert: true,
						});
					},
					error: function () {
						dialog.hide();
						frappe.msgprint({
							message: __("Linking to Customer Failed. Please try again."),
							title: __("Linking Failed"),
							indicator: "red",
						});
					},
				});
			},
			primary_action_label: __("Create Link"),
		});
		dialog.show();
	},
	make_pricing_rule: function (frm) {
		frappe.new_doc("Pricing Rule", {
			applicable_for: "Supplier",
			supplier: frm.doc.name,
			buying: 1,
		});
	},
});

function render_contracts_table(frm) {
	let wrapper = frm.fields_dict.contracts_html.$wrapper;
	wrapper.empty();

	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Contract",
			filters: {
				party_type: "Supplier",
				party_name: frm.doc.name,
			},
			fields: ["name", "company", "start_date", "end_date", "status", "contract_file"],
			order_by: "start_date desc",
			limit_page_length: 0,
		},
		callback: function (r) {
			let contracts = r.message || [];
			let html = "";

			if (contracts.length === 0) {
				html += `<div class="text-muted" style="padding: 15px 0;">
					Chưa có hợp đồng nào cho nhà cung cấp này.
				</div>`;
			} else {
				html += `<div class="table-responsive">
				<table class="table table-bordered table-hover" style="margin-bottom: 0;">
					<thead style="background-color: var(--subtle-fg);">
						<tr>
							<th style="width: 15%;">Mã hợp đồng</th>
							<th style="width: 20%;">Công ty</th>
							<th style="width: 14%;">Ngày bắt đầu</th>
							<th style="width: 14%;">Ngày kết thúc</th>
							<th style="width: 12%;">Trạng thái</th>
							<th style="width: 25%;">File đính kèm</th>
						</tr>
					</thead>
					<tbody>`;

				contracts.forEach(function (c) {
					let status_color = {
						"Unsigned": "orange",
						"Active": "green",
						"Inactive": "red",
					};
					let indicator = status_color[c.status] || "gray";
					let file_link = c.contract_file
						? `<a href="${c.contract_file}" target="_blank"><i class="fa fa-paperclip"></i> Xem file</a>`
						: `<span class="text-muted">—</span>`;
					let start = c.start_date ? frappe.datetime.str_to_user(c.start_date) : "—";
					let end = c.end_date ? frappe.datetime.str_to_user(c.end_date) : "—";

					html += `<tr>
						<td><a href="/app/contract/${c.name}">${c.name}</a></td>
						<td>${c.company || "—"}</td>
						<td>${start}</td>
						<td>${end}</td>
						<td><span class="indicator-pill ${indicator}">${__(c.status || "—")}</span></td>
						<td>${file_link}</td>
					</tr>`;
				});

				html += `</tbody></table></div>`;
			}

			wrapper.html(html);
		},
	});
}
