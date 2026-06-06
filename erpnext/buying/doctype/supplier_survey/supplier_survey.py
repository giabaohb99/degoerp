# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class SupplierSurvey(Document):
	def autoname(self):
		from frappe.model.naming import make_autoname
		from frappe.utils import getdate
		
		# Parse contact_date to DDMMYYYY format
		date = getdate(self.contact_date or frappe.utils.today())
		date_str = date.strftime("%d%m%Y")
		
		# Format naming series sequence as KS.NCC.DDMMYYYY.##
		self.name = make_autoname(f"KS.NCC.{date_str}.##")

	def validate(self):
		self.survey_id = self.name

		if self.docstatus == 1 and frappe.db.get_value(self.doctype, self.name, "docstatus") == 1:
			user = frappe.session.user
			roles = frappe.get_roles(user)
			is_manager = any(r in roles for r in ["Purchase Manager", "Manufacturing Manager", "System Manager", "Administrator"]) or user == "Administrator"
			if not is_manager:
				frappe.throw(_("Chỉ Quản lý hoặc Admin mới có quyền cập nhật tài liệu đã gửi."))

		if self.docstatus < 1:
			if not self.status:
				self.status = "Draft"

	def before_submit(self):
		self.validate_all_fields_filled()

	def validate_all_fields_filled(self):
		# 1. Parent fields
		exclude_parent = ["amended_from", "naming_series", "survey_id", "status", "attachment", "remarks", "technical_specs_notes", "procurement_request", "item_code", "item_name", "item_class"]
		for df in self.meta.fields:
			if df.fieldtype in ["Section Break", "Column Break", "Table", "Heading", "HTML"]:
				continue
			if df.fieldname in exclude_parent:
				continue
			
			val = self.get(df.fieldname)
			if val is None or (isinstance(val, str) and val.strip() == ""):
				frappe.throw(_("Trường '{0}' trên Form chính không được để trống khi gửi đơn.").format(df.label))

		# 2. Check child table
		if not self.items:
			frappe.throw(_("Bảng chi tiết so sánh các nhà cung cấp không được để trống."))

		# 3. Child fields
		exclude_child = [
			"parent", "parentfield", "parenttype", "doctype", "name", "idx", 
			"attachment", "survey_date", "manager_approval", "manager_requirements"
		]
		for row in self.items:
			for df in row.meta.fields:
				if df.fieldtype in ["Section Break", "Column Break", "Heading", "HTML"]:
					continue
				if df.fieldname in exclude_child:
					continue
				
				val = row.get(df.fieldname)
				if val is None or (isinstance(val, str) and val.strip() == ""):
					frappe.throw(_("Dòng {0}: Trường '{1}' không được để trống khi gửi đơn.").format(row.idx, df.label))

	def on_submit(self):
		self.db_set("status", "Submitted")

	def on_cancel(self):
		self.db_set("status", "Cancelled")

@frappe.whitelist()
def revert_to_draft(name):
	frappe.has_permission("Supplier Survey", ptype="write", throw=True)
	frappe.db.set_value("Supplier Survey", name, "docstatus", 0)
	frappe.db.set_value("Supplier Survey", name, "status", "Draft")
	return True

@frappe.whitelist()
def set_as_completed(name):
	frappe.has_permission("Supplier Survey", ptype="submit", throw=True)
	frappe.db.set_value("Supplier Survey", name, "status", "Approved")
	frappe.db.commit()
	return True

@frappe.whitelist()
def return_survey(name, reason):
	frappe.has_permission("Supplier Survey", ptype="submit", throw=True)
	doc = frappe.get_doc("Supplier Survey", name)
	doc.docstatus = 0
	doc.status = "Returned"
	note = f"\n\n<b>[Trả lại lúc {frappe.utils.now_datetime().strftime('%d-%m-%Y %H:%M:%S')}]</b>: {reason}"
	doc.remarks = (doc.remarks or "") + note
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return True

def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user
	
	roles = frappe.get_roles(user)
	if "Purchase Manager" in roles or "System Manager" in roles or user == "Administrator":
		return None
	
	return f"`tabSupplier Survey`.owner = '{user}' OR `tabSupplier Survey`.person_in_charge = '{user}' OR `tabSupplier Survey`.requester = '{user}' OR EXISTS (SELECT 1 FROM `tabProcurement Request` pr WHERE pr.name = `tabSupplier Survey`.procurement_request AND pr.owner = '{user}')"

def has_permission(doc, ptype=None, user=None):
	if not user:
		user = frappe.session.user
	
	roles = frappe.get_roles(user)
	if "Purchase Manager" in roles or "System Manager" in roles or user == "Administrator":
		return True
	
	if "Purchase User" in roles:
		if isinstance(doc, str) or doc is None or (hasattr(doc, "is_new") and doc.is_new()):
			return True
		
		if doc.owner == user or getattr(doc, "person_in_charge", None) == user or getattr(doc, "requester", None) == user:
			return True
		if getattr(doc, "procurement_request", None):
			pr_owner = frappe.db.get_value("Procurement Request", doc.procurement_request, "owner")
			if pr_owner == user:
				return True
	
	if "Purchase Requester" in roles:
		if ptype in ["submit", "cancel", "amend"]:
			return False
		
		if isinstance(doc, str) or doc is None or (hasattr(doc, "is_new") and doc.is_new()):
			return True
		
		if doc.owner == user or getattr(doc, "person_in_charge", None) == user or getattr(doc, "requester", None) == user:
			return True
		if getattr(doc, "procurement_request", None):
			pr_owner = frappe.db.get_value("Procurement Request", doc.procurement_request, "owner")
			if pr_owner == user:
				return True
	
	return False


