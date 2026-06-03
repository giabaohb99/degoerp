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
		self.calculate_row_amounts()

		if self.docstatus < 1:
			if not self.status:
				self.status = "Draft"

	def calculate_row_amounts(self):
		"""Calculate amount for each item row."""
		for item in self.get("items") or []:
			qty = int(item.qty or 0)
			rate = float(item.rate or 0)
			item.amount = qty * rate

	def on_submit(self):
		self.db_set("status", "Approved")

	def on_cancel(self):
		self.db_set("status", "Cancelled")

@frappe.whitelist()
def revert_to_draft(name):
	frappe.has_permission("Supplier Survey", ptype="write", throw=True)
	frappe.db.set_value("Supplier Survey", name, "docstatus", 0)
	frappe.db.set_value("Supplier Survey", name, "status", "Draft")
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


