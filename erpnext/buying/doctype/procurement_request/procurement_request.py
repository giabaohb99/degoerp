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

	def check_permission(self, permtype="read", permlevel=None):
		user = frappe.session.user
		roles = frappe.get_roles(user)
		is_manager = "Purchase Manager" in roles or "System Manager" in roles or user == "Administrator"

		# If it's a submitted document and the user is authorized to edit it (PIC),
		# allow saving/updating without check_permission failure
		if self.docstatus == 1 and not is_manager:
			is_purchase_user = "Purchase User" in roles
			if is_purchase_user:
				is_pic = any(item.person_in_charge == user for item in self.items)
				if is_pic and permtype in ["write", "submit"]:
					self.flags.ignore_permissions = True
					return

		super().check_permission(permtype, permlevel)

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
		
		# Format naming series sequence as PYC.DDMMYYYY.##
		self.name = make_autoname(f"PYC.{date_str}.##")

	def before_save(self):
		self.ignore_pricing_rule = 1
		if not self.requester:
			self.requester = frappe.session.user
		if not self.company:
			self.company = frappe.db.get_default("company") or frappe.db.get_single_value("Global Defaults", "default_company")
			if not self.company:
				companies = frappe.get_all("Company", limit=1)
				if companies:
					self.company = companies[0].name

	def validate(self):
		self.ignore_pricing_rule = 1

		# 1. Sửa tên ngày validate: ngày cần hàng phải sau hoặc bằng ngày yêu cầu
		if self.schedule_date and self.transaction_date:
			from frappe.utils import getdate
			if getdate(self.schedule_date) < getdate(self.transaction_date):
				frappe.throw(_("Ngày cần hàng (Ngày giao hàng dự kiến) phải sau hoặc bằng Ngày yêu cầu."))

		# 2. Phân quyền cập nhật purchase_status cấp dòng vật tư
		if not self.is_new():
			old_doc = self.get_doc_before_save() or (frappe.get_doc(self.doctype, self.name) if not self.is_new() else None)
			if old_doc:
				old_statuses = {item.name: item.purchase_status for item in old_doc.items}
				for item in self.items:
					old_status = old_statuses.get(item.name) or "Chưa đặt hàng"
					new_status = item.purchase_status or "Chưa đặt hàng"
					if new_status != old_status:
						user = frappe.session.user
						roles = frappe.get_roles(user)
						is_authorized = any(r in ["Purchase Manager", "Purchase User", "System Manager"] for r in roles) or user == "Administrator"
						if not is_authorized:
							frappe.throw(_("Chỉ Quản lý hoặc Nhân sự thu mua phụ trách mới được cập nhật Trạng thái xử lý của vật tư."))

		# 3. Logic tự động đồng bộ trạng thái tổng dựa trên trạng thái của item con
		self.sync_status_from_items()
		
		# Sync item_class_description for items
		for item in self.items:
			if item.item_class:
				item.item_class_description = frappe.db.get_value("UOM", item.item_class, "description")
			else:
				item.item_class_description = None

		self.validate_procurement_items()
		self.calculate_totals()

		# Tự động xóa nhân sự phụ trách khi đơn bị trả về (Returned)
		if self.status == "Returned":
			for item in self.items:
				item.person_in_charge = None

		if self.docstatus < 1:
			if not self.status:
				self.status = "Draft"

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

			# 2. Kiểm soát chỉnh sửa của Nhân sự phụ trách (Purchase User) ở trạng thái Submitted / Processing
			if db_status in ["Submitted", "Processing"]:
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
						
						# Chặn thêm, bớt mặt hàng
						if len(self.items) != len(old_doc.items):
							frappe.throw(_("Nhân sự phụ trách không được phép thêm hoặc bớt mặt hàng. Vui lòng trả lại đơn nếu cần thay đổi mặt hàng."))
						
						old_items_dict = {item.name: item for item in old_doc.items}
						for item in self.items:
							if not item.name or item.name not in old_items_dict:
								frappe.throw(_("Nhân sự phụ trách không được phép thêm mặt hàng mới."))
							
							old_item = old_items_dict[item.name]
							
							# Nếu user không phải là người phụ trách của item này (cả cũ và mới)
							if old_item.person_in_charge != user and item.person_in_charge != user:
								# Chặn không cho sửa bất kỳ thông tin nào của dòng này
								if (item.item_code != old_item.item_code or 
									int(item.qty or 0) != int(old_item.qty or 0) or 
									item.uom != old_item.uom or 
									float(item.proposed_rate or 0) != float(old_item.proposed_rate or 0) or 
									item.warehouse != old_item.warehouse or
									item.person_in_charge != old_item.person_in_charge or
									item.purchase_status != old_item.purchase_status or
									item.progress_details != old_item.progress_details or
									item.other_notes != old_item.other_notes):
									frappe.throw(_("Bạn không được phép chỉnh sửa dòng mặt hàng {0} do được gán cho nhân sự khác phụ trách.").format(item.item_code))
							
							# Nếu là dòng của user phụ trách, chặn sửa thông tin cốt lõi (chỉ được sửa proposed_rate, warehouse hoặc các trường phụ)
							if old_item.person_in_charge == user or item.person_in_charge == user:
								if item.item_code != old_item.item_code:
									frappe.throw(_("Nhân sự phụ trách không được phép đổi mã mặt hàng từ {0} sang {1}.").format(old_item.item_code, item.item_code))
								if int(item.qty or 0) != int(old_item.qty or 0):
									frappe.throw(_("Nhân sự phụ trách không được phép thay đổi số lượng mặt hàng {0}.").format(item.item_code))
								if item.uom != old_item.uom:
									frappe.throw(_("Nhân sự phụ trách không được phép thay đổi đơn vị tính mặt hàng {0}.").format(item.item_code))

		# Chỉ Quản lý hoặc Admin mới được phép gán hoặc thay đổi người phụ trách của mặt hàng
		user = frappe.session.user
		roles = frappe.get_roles(user)
		is_manager = "Purchase Manager" in roles or "System Manager" in roles or user == "Administrator"
		
		if not is_manager:
			if self.is_new():
				if any(item.person_in_charge for item in self.items):
					frappe.throw(_("Chỉ Quản lý hoặc Admin mới có quyền gán hoặc thay đổi Nhân sự phụ trách."))
			else:
				old_doc = self.get_doc_before_save() or (frappe.get_doc(self.doctype, self.name) if not self.is_new() else None)
				if old_doc:
					old_items_dict = {item.name: item for item in old_doc.items}
					for item in self.items:
						old_pic = None
						if item.name and item.name in old_items_dict:
							old_pic = old_items_dict[item.name].person_in_charge
						
						if item.person_in_charge != old_pic:
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

	def before_update_after_submit(self):
		self.sync_status_from_items()

	def sync_status_from_items(self):
		if self.docstatus == 1:
			item_statuses = [item.purchase_status for item in self.items if item.purchase_status]
			if item_statuses:
				new_status = self.status
				if all(s in ["Hoàn thành", "Hủy đơn"] for s in item_statuses):
					if any(s == "Hoàn thành" for s in item_statuses):
						new_status = "Completed"
					else:
						new_status = "Processing"
				elif any(s != "Chưa đặt hàng" for s in item_statuses):
					if self.status in ["Submitted", "Cancelled"]:
						new_status = "Processing"
				else:
					if self.status in ["Processing", "Cancelled"]:
						new_status = "Submitted"

				if new_status != self.status:
					self.status = new_status
					if not self.is_new():
						self.db_set("status", new_status)

	def on_submit(self):
		self.db_set("status", "Submitted")
	def on_cancel(self):
		self.db_set("status", "Cancelled")
		for item in self.items:
			item.db_set("purchase_status", "Hủy đơn")
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
					"department": "requester_department"
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
					"requester": "requester",
					"department": "requester_department"
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
	
	if not is_manager:
		frappe.throw(_("Chỉ Quản lý mới có quyền hoàn thành yêu cầu."))
		
	frappe.db.set_value("Procurement Request", name, "status", "Completed")
	frappe.db.commit()
	return True

def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user
	
	roles = frappe.get_roles(user)
	if "Purchase Manager" in roles or "System Manager" in roles or user == "Administrator":
		return None
	
	return f"`tabProcurement Request`.owner = '{user}' OR `tabProcurement Request`.requester = '{user}' OR EXISTS (SELECT 1 FROM `tabProcurement Request Item` WHERE parent = `tabProcurement Request`.name AND person_in_charge = '{user}')"

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
		is_allowed_user = (
			doc.owner == user or 
			getattr(doc, "requester", None) == user or 
			any(item.person_in_charge == user for item in getattr(doc, "items", []))
		)
		if not is_allowed_user:
			return False
		
		if ptype == "write":
			if doc.owner == user or getattr(doc, "requester", None) == user:
				if doc_status in ["Draft", "Returned"]:
					return True
			if any(item.person_in_charge == user for item in getattr(doc, "items", [])):
				if doc_status in ["Submitted", "Processing"]:
					return True
			return False
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


