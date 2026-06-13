# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from erpnext.accounts.doctype.journal_entry.journal_entry import get_default_bank_cash_account
from erpnext.accounts.doctype.bank_account.bank_account import (
	get_default_company_bank_account,
	get_party_bank_account,
)
from erpnext.accounts.party import get_party_account
from erpnext.accounts.utils import get_account_currency
from erpnext.setup.utils import get_exchange_rate


@frappe.whitelist()
def bulk_create_grouped_payments(invoices):
	"""
	Nhận danh sách Purchase Invoice names, nhóm theo Supplier+Company+Currency+CreditTo,
	tạo 1 Payment Entry (Draft) cho mỗi nhóm với nhiều references.

	Args:
		invoices: JSON string hoặc list các Purchase Invoice name

	Returns:
		dict: {
			"created": [{"payment_entry": "PE-00001", "supplier": "...", "total": 1000, "invoice_count": 3}],
			"skipped": [{"invoice": "PINV-001", "reason": "..."}],
			"failed": [{"invoice": "PINV-002", "error": "..."}]
		}
	"""
	if isinstance(invoices, str):
		invoices = json.loads(invoices)

	if not invoices:
		frappe.throw(_("Vui lòng chọn ít nhất 1 hóa đơn."))

	result = {
		"created": [],
		"skipped": [],
		"failed": []
	}

	# Lấy thông tin tất cả invoices
	valid_invoices = []
	today = getdate(nowdate())

	for inv_name in invoices:
		try:
			inv = frappe.get_doc("Purchase Invoice", inv_name)

			# Kiểm tra điều kiện
			if inv.docstatus != 1:
				result["skipped"].append({
					"invoice": inv_name,
					"reason": _("Hóa đơn chưa được submit (docstatus={0})").format(inv.docstatus)
				})
				continue

			if inv.is_return:
				result["skipped"].append({
					"invoice": inv_name,
					"reason": _("Hóa đơn là phiếu trả hàng (Debit Note)")
				})
				continue

			if flt(inv.outstanding_amount) <= 0:
				result["skipped"].append({
					"invoice": inv_name,
					"reason": _("Hóa đơn đã thanh toán đầy đủ (outstanding={0})").format(inv.outstanding_amount)
				})
				continue

			if inv.on_hold:
				if not inv.release_date or getdate(inv.release_date) > today:
					result["skipped"].append({
						"invoice": inv_name,
						"reason": _("Hóa đơn đang bị tạm giữ (On Hold)")
					})
					continue

			valid_invoices.append(inv)

		except Exception as e:
			result["skipped"].append({
				"invoice": inv_name,
				"reason": str(e)
			})

	if not valid_invoices:
		return result

	# Nhóm theo (supplier, company, currency, credit_to)
	groups = defaultdict(list)
	for inv in valid_invoices:
		key = (inv.supplier, inv.company, inv.currency, inv.credit_to)
		groups[key].append(inv)

	# Tạo Payment Entry cho mỗi nhóm
	for (supplier, company, currency, credit_to), group_invoices in groups.items():
		try:
			pe = _create_grouped_payment_entry(
				supplier=supplier,
				company=company,
				currency=currency,
				credit_to=credit_to,
				invoices=group_invoices
			)

			result["created"].append({
				"payment_entry": pe.name,
				"supplier": supplier,
				"supplier_name": group_invoices[0].supplier_name,
				"total": flt(pe.paid_amount),
				"invoice_count": len(group_invoices),
				"invoices": [inv.name for inv in group_invoices]
			})

		except Exception as e:
			frappe.db.rollback()
			frappe.clear_messages()
			for inv in group_invoices:
				result["failed"].append({
					"invoice": inv.name,
					"error": str(e)
				})

	if result["created"]:
		frappe.db.commit()

	return result


def _create_grouped_payment_entry(supplier, company, currency, credit_to, invoices):
	"""
	Tạo 1 Payment Entry Draft cho 1 nhóm hóa đơn cùng supplier.
	"""
	company_currency = frappe.get_cached_value("Company", company, "default_currency")
	party_account_currency = get_account_currency(credit_to)

	# Tính tổng outstanding
	total_outstanding = sum(flt(inv.outstanding_amount) for inv in invoices)

	# Lấy bank/cash account mặc định
	bank = get_default_bank_cash_account(
		company, "Bank", fetch_balance=False
	)
	if not bank:
		bank = get_default_bank_cash_account(
			company, "Cash", fetch_balance=False
		)

	if not bank:
		frappe.throw(
			_("Không tìm thấy tài khoản ngân hàng/tiền mặt mặc định cho công ty {0}. "
			  "Vui lòng thiết lập trong Company Settings.").format(company)
		)

	# Xác định payment type
	payment_type = "Pay"

	# Tính paid/received amounts
	if party_account_currency == bank.account_currency:
		paid_amount = received_amount = abs(total_outstanding)
	else:
		paid_amount = abs(total_outstanding)
		if company_currency != bank.account_currency:
			posting_date = nowdate()
			conversion_rate = get_exchange_rate(
				bank.account_currency, party_account_currency, posting_date
			)
			received_amount = paid_amount / conversion_rate if conversion_rate else paid_amount
		else:
			# Lấy conversion rate từ invoice đầu tiên
			conversion_rate = invoices[0].conversion_rate or 1
			received_amount = paid_amount * conversion_rate

	# Tạo Payment Entry
	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = payment_type
	pe.company = company
	pe.posting_date = nowdate()
	pe.party_type = "Supplier"
	pe.party = supplier
	pe.paid_from = bank.account
	pe.paid_to = credit_to
	pe.paid_from_account_currency = bank.account_currency
	pe.paid_to_account_currency = party_account_currency
	pe.paid_amount = paid_amount
	pe.received_amount = received_amount
	pe.reference_no = _("Thanh toán gộp")
	pe.reference_date = nowdate()

	# Set bank account
	pe.bank_account = frappe.db.get_value(
		"Bank Account", {"is_company_account": 1, "is_default": 1, "company": company}, "name"
	)

	# Party bank account
	party_bank_account = get_party_bank_account("Supplier", supplier)
	if party_bank_account:
		pe.party_bank_account = party_bank_account
		pe.set_bank_account_data()

	# Thêm references cho từng invoice
	for inv in invoices:
		if party_account_currency == company_currency:
			grand_total = inv.base_rounded_total or inv.base_grand_total
		else:
			grand_total = inv.rounded_total or inv.grand_total

		pe.append("references", {
			"reference_doctype": "Purchase Invoice",
			"reference_name": inv.name,
			"bill_no": inv.get("bill_no"),
			"due_date": inv.get("due_date"),
			"total_amount": flt(grand_total),
			"outstanding_amount": flt(inv.outstanding_amount),
			"allocated_amount": flt(inv.outstanding_amount),
		})

	pe.setup_party_account_field()
	pe.set_missing_values()
	pe.set_missing_ref_details()

	if bank:
		pe.set_exchange_rate()
		pe.set_amounts()

	pe.flags.ignore_permissions = True
	pe.insert()

	return pe


@frappe.whitelist()
def get_grouped_payment_preview(invoices):
	"""
	Xem trước: nhóm các invoice theo supplier và trả về tóm tắt.
	Dùng cho dialog xác nhận trước khi tạo PE.
	"""
	if isinstance(invoices, str):
		invoices = json.loads(invoices)

	if not invoices:
		return {"groups": [], "skipped": []}

	groups = defaultdict(lambda: {
		"invoices": [],
		"total_outstanding": 0,
		"supplier_name": ""
	})
	skipped = []
	today = getdate(nowdate())

	for inv_name in invoices:
		try:
			inv = frappe.db.get_value("Purchase Invoice", inv_name, [
				"name", "supplier", "supplier_name", "company", "currency",
				"credit_to", "outstanding_amount", "docstatus", "is_return",
				"on_hold", "release_date", "grand_total"
			], as_dict=True)

			if not inv:
				skipped.append({"invoice": inv_name, "reason": _("Không tìm thấy")})
				continue
			if inv.docstatus != 1:
				skipped.append({"invoice": inv_name, "reason": _("Chưa submit")})
				continue
			if inv.is_return:
				skipped.append({"invoice": inv_name, "reason": _("Phiếu trả hàng")})
				continue
			if flt(inv.outstanding_amount) <= 0:
				skipped.append({"invoice": inv_name, "reason": _("Đã thanh toán")})
				continue
			if inv.on_hold:
				if not inv.release_date or getdate(inv.release_date) > today:
					skipped.append({"invoice": inv_name, "reason": _("Đang tạm giữ")})
					continue

			key = f"{inv.supplier}||{inv.company}||{inv.currency}"
			groups[key]["invoices"].append({
				"name": inv.name,
				"outstanding": flt(inv.outstanding_amount),
				"grand_total": flt(inv.grand_total)
			})
			groups[key]["total_outstanding"] += flt(inv.outstanding_amount)
			groups[key]["supplier_name"] = inv.supplier_name or inv.supplier

		except Exception as e:
			skipped.append({"invoice": inv_name, "reason": str(e)})

	result_groups = []
	for key, data in groups.items():
		parts = key.split("||")
		result_groups.append({
			"supplier": parts[0],
			"supplier_name": data["supplier_name"],
			"company": parts[1],
			"currency": parts[2],
			"invoice_count": len(data["invoices"]),
			"total_outstanding": data["total_outstanding"],
			"invoices": data["invoices"]
		})

	return {
		"groups": result_groups,
		"skipped": skipped
	}
