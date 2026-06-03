# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc

from erpnext.buying.utils import validate_for_items
from erpnext.controllers.buying_controller import BuyingController


class ProcurementRequest(BuyingController):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from erpnext.buying.doctype.procurement_request_item.procurement_request_item import (
			ProcurementRequestItem,
		)

		amended_from: DF.Link | None
		company: DF.Link
		invoice_company: DF.Link | None
		items: DF.Table[ProcurementRequestItem]
		letter_head: DF.Link | None
		naming_series: DF.Literal["PUR-PR-.YYYY.-"]
		person_in_charge: DF.Link | None
		receiving_warehouse: DF.Link | None
		remarks: DF.TextEditor | None
		requester: DF.Link
		requester_department: DF.Link | None
		schedule_date: DF.Date | None
		select_print_heading: DF.Link | None
		shipping_cost: DF.Currency
		status: DF.Literal["", "Draft", "Submitted", "Cancelled"]
		tc_name: DF.Link | None
		terms: DF.TextEditor | None
		title: DF.Data | None
		total_amount: DF.Currency
		total_qty: DF.Float
		transaction_date: DF.Date
	# end: auto-generated types

	def calculate_taxes_and_totals(self):
		pass

	def set_item_rate_and_discounts(self, item_obj, item_details):
		from frappe.utils import flt
		item_obj.proposed_rate = flt(item_details.price_list_rate or item_details.rate or 0.0)
		item_obj.amount = flt(item_obj.qty or 0) * flt(item_obj.proposed_rate or 0.0)

	@frappe.whitelist()
	def process_item_selection(self, item_idx):
		from frappe.utils import flt
		item_obj = self.get("items", {"idx": item_idx})[0]
		if not item_obj.item_code:
			return
		
		item_details = frappe.db.get_value(
			"Item", 
			item_obj.item_code, 
			["item_name", "description", "stock_uom", "item_group", "brand", "image"], 
			as_dict=True
		)
		if item_details:
			item_obj.item_name = item_details.item_name
			item_obj.description = item_details.description
			item_obj.uom = item_details.stock_uom
			item_obj.item_group = item_details.item_group
			item_obj.brand = item_details.brand
			item_obj.image = item_details.image
			
		item_obj.proposed_rate = 0.0
		item_obj.amount = 0.0

	def autoname(self):
		from frappe.model.naming import make_autoname
		from frappe.utils import getdate
		
		# Parse transaction_date to DDMMYYYY format
		date = getdate(self.transaction_date or frappe.utils.today())
		date_str = date.strftime("%d%m%Y")
		
		# Format naming series sequence as PYC.NM.DDMMYYYY.##
		self.name = make_autoname(f"PYC.NM.{date_str}.##")

	def before_save(self):
		self.ignore_pricing_rule = 1
		if not self.requester:
			self.requester = frappe.session.user

	def validate(self):
		self.ignore_pricing_rule = 1
		self.validate_procurement_items()
		self.calculate_totals()

		# Tự động xóa nhân sự phụ trách khi đơn bị trả về (Returned)
		if self.status == "Returned":
			self.person_in_charge = None

		if self.docstatus < 1:
			if not self.status:
				self.status = "Draft"
			if self.person_in_charge and self.status in ["Draft", "Submitted"]:
				self.status = "Assigned"
			elif not self.person_in_charge and self.status == "Assigned":
				self.status = "Submitted"

		# Đảm bảo người yêu cầu
		if not self.requester:
			self.requester = frappe.session.user

		if not self.is_new():
			db_status = frappe.db.get_value("Procurement Request", self.name, "status")
			user = frappe.session.user
			roles = frappe.get_roles(user)

			# 1. Ngăn người yêu cầu chỉnh sửa ở trạng thái không cho phép
			if db_status and db_status not in ["Draft", "Returned"]:
				is_requester_only = "Purchase Requester" in roles and not (
					"Purchase Manager" in roles or 
					"System Manager" in roles or 
					user == "Administrator"
				)
				if is_requester_only:
					frappe.throw(_("Yêu cầu thu mua đang ở trạng thái {0}. Bạn không có quyền chỉnh sửa ở trạng thái này.").format(_(db_status)))

			# 2. Kiểm soát chỉnh sửa của Nhân sự phụ trách (Purchase User) ở trạng thái Assigned
			if db_status == "Assigned":
				is_purchase_user_only = "Purchase User" in roles and not (
					"Purchase Manager" in roles or 
					"System Manager" in roles or 
					user == "Administrator"
				)
				if is_purchase_user_only:
					old_doc = self.get_doc_before_save() or (frappe.get_doc(self.doctype, self.name) if not self.is_new() else None)
					if old_doc:
						# Chặn sửa trường quan trọng ở form chính
						blocked_parent_fields = ["company", "requester", "transaction_date", "schedule_date"]
						for fieldname in blocked_parent_fields:
							if self.get(fieldname) != old_doc.get(fieldname):
								frappe.throw(_("Nhân sự phụ trách không được phép chỉnh sửa trường quan trọng: {0}").format(self.meta.get_label(fieldname)))
						
						# Chặn thêm, bớt mặt hàng hoặc sửa item_code, qty, uom
						if len(self.items) != len(old_doc.items):
							frappe.throw(_("Nhân sự phụ trách không được phép thêm hoặc bớt mặt hàng. Vui lòng trả lại đơn nếu cần thay đổi mặt hàng."))
						
						old_items_dict = {item.name: item for item in old_doc.items}
						for item in self.items:
							if not item.name or item.name not in old_items_dict:
								frappe.throw(_("Nhân sự phụ trách không được phép thêm mặt hàng mới."))
							
							old_item = old_items_dict[item.name]
							if item.item_code != old_item.item_code:
								frappe.throw(_("Nhân sự phụ trách không được phép đổi mã mặt hàng từ {0} sang {1}.").format(old_item.item_code, item.item_code))
							if int(item.qty or 0) != int(old_item.qty or 0):
								frappe.throw(_("Nhân sự phụ trách không được phép thay đổi số lượng mặt hàng {0}.").format(item.item_code))
							if item.uom != old_item.uom:
								frappe.throw(_("Nhân sự phụ trách không được phép thay đổi đơn vị tính mặt hàng {0}.").format(item.item_code))

		# Chỉ Quản lý hoặc Admin mới được phép gán hoặc thay đổi người phụ trách
		db_val = None if self.is_new() else frappe.db.get_value("Procurement Request", self.name, "person_in_charge")
		val_now = self.person_in_charge or None
		val_old = db_val or None
		if val_now != val_old:
			user = frappe.session.user
			roles = frappe.get_roles(user)
			if not ("Purchase Manager" in roles or "System Manager" in roles or user == "Administrator"):
				frappe.throw(_("Chỉ Quản lý hoặc Admin mới có quyền gán hoặc thay đổi Nhân sự phụ trách."))

	def validate_procurement_items(self):
		from erpnext.buying.utils import set_stock_levels, validate_item_and_get_basic_data, validate_stock_item_warehouse
		from erpnext.stock.doctype.item.item import validate_end_of_life
		
		items = []
		for d in self.get("items"):
			if not d.item_code:
				continue
			set_stock_levels(row=d)
			item = validate_item_and_get_basic_data(row=d)
			validate_stock_item_warehouse(row=d, item=item)
			validate_end_of_life(d.item_code, item.end_of_life, item.disabled)
			items.append(d.item_code)
			
		if (
			items
			and len(items) != len(set(items))
			and not frappe.db.get_single_value("Buying Settings", "allow_multiple_items")
		):
			frappe.throw(_("Same item cannot be entered multiple times."))

	def calculate_totals(self):
		"""Calculate total_qty and total_amount from child items."""
		self.total_qty = 0
		self.total_amount = 0

		for item in self.get("items"):
			# Calculate item amount: qty (Int) * proposed_rate (Currency)
			qty = int(item.qty or 0)
			rate = float(item.proposed_rate or 0)
			item.amount = qty * rate
			self.total_qty += qty
			self.total_amount += (item.amount or 0)

	def on_submit(self):
		self.db_set("status", "Submitted")

	def on_cancel(self):
		self.db_set("status", "Cancelled")


@frappe.whitelist()
def make_purchase_order(source_name, target_doc=None):
	doclist = get_mapped_doc(
		"Procurement Request",
		source_name,
		{
			"Procurement Request": {
				"doctype": "Purchase Order",
				"validation": {"docstatus": ["=", 1]},
			},
			"Procurement Request Item": {
				"doctype": "Purchase Order Item",
				"field_map": {
					"name": "procurement_request_item",
					"parent": "procurement_request",
					"uom": "uom",
					"qty": "qty",
					"item_code": "item_code",
					"item_name": "item_name",
					"description": "description",
					"schedule_date": "schedule_date",
				},
			},
		},
		target_doc,
	)
	return doclist

@frappe.whitelist()
def make_supplier_survey(source_name, target_doc=None):
	doclist = get_mapped_doc(
		"Procurement Request",
		source_name,
		{
			"Procurement Request": {
				"doctype": "Supplier Survey",
				"validation": {"docstatus": ["=", 1]},
				"field_map": {
					"name": "procurement_request",
					"requester": "requester",
					"person_in_charge": "department"
				}
			},
		},
		target_doc,
	)
	return doclist

@frappe.whitelist()
def make_product_survey(source_name, target_doc=None):
	doclist = get_mapped_doc(
		"Procurement Request",
		source_name,
		{
			"Procurement Request": {
				"doctype": "Product Survey",
				"validation": {"docstatus": ["=", 1]},
				"field_map": {
					"name": "procurement_request",
					"requester": "requester"
				}
			},
		},
		target_doc,
	)
	return doclist

@frappe.whitelist()
def revert_to_draft(name):
	frappe.has_permission("Procurement Request", ptype="write", throw=True)
	frappe.db.set_value("Procurement Request", name, "docstatus", 0)
	frappe.db.set_value("Procurement Request", name, "status", "Draft")
	return True

@frappe.whitelist()
def approve_request(name):
	frappe.has_permission("Procurement Request", ptype="submit", throw=True)
	frappe.db.set_value("Procurement Request", name, "status", "Approved")
	return True

@frappe.whitelist()
def set_as_completed(name):
	doc = frappe.get_doc("Procurement Request", name)
	user = frappe.session.user
	roles = frappe.get_roles(user)
	
	is_manager = "Purchase Manager" in roles or "System Manager" in roles or user == "Administrator"
	is_pic = doc.person_in_charge == user
	
	if not (is_manager or is_pic):
		frappe.throw(_("Chỉ Nhân sự phụ trách hoặc Quản lý mới có quyền hoàn thành yêu cầu."))
		
	frappe.db.set_value("Procurement Request", name, "status", "Completed")
	frappe.db.commit()
	return True

def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user
	
	roles = frappe.get_roles(user)
	if "Purchase Manager" in roles or "System Manager" in roles or user == "Administrator":
		return None
	
	return f"`tabProcurement Request`.owner = '{user}' OR `tabProcurement Request`.person_in_charge = '{user}' OR `tabProcurement Request`.requester = '{user}'"

def has_permission(doc, ptype=None, user=None):
	if not user:
		user = frappe.session.user
	
	roles = frappe.get_roles(user)
	if "Purchase Manager" in roles or "System Manager" in roles or user == "Administrator":
		return True
		
	if isinstance(doc, str) or doc is None:
		if "Purchase User" in roles or "Purchase Requester" in roles:
			if ptype in ["cancel", "amend"]:
				return False
			return True
		return False

	if getattr(doc, "is_new", None) and doc.is_new():
		return True

	doc_status = getattr(doc, "status", "Draft")
	
	if "Purchase User" in roles:
		is_allowed_user = doc.owner == user or getattr(doc, "person_in_charge", None) == user or getattr(doc, "requester", None) == user
		if not is_allowed_user:
			return False
		
		if ptype == "write":
			return doc_status == "Assigned"
		return True
	
	if "Purchase Requester" in roles:
		if ptype in ["cancel", "amend"]:
			return False
		
		is_allowed_user = doc.owner == user or getattr(doc, "requester", None) == user
		if not is_allowed_user:
			return False
		
		if ptype == "write":
			return doc_status in ["Draft", "Returned"]
		return True
	
	return False


