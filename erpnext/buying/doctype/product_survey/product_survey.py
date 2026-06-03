# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ProductSurvey(Document):
	def autoname(self):
		from frappe.model.naming import make_autoname
		from frappe.utils import getdate
		
		# Parse contact_date to DDMMYYYY format
		date = getdate(self.contact_date or frappe.utils.today())
		date_str = date.strftime("%d%m%Y")
		
		# Format naming series sequence as KS.SP.DDMMYYYY.##
		self.name = make_autoname(f"KS.SP.{date_str}.##")

	def validate(self):
		self.survey_id = self.name
		self.calculate_row_amounts()

		if self.docstatus < 1:
			if not self.status:
				self.status = "Draft"

	def calculate_row_amounts(self):
		"""Calculate amount and converted_amount for each comparison row."""
		for item in self.get("items") or []:
			rate = float(item.rate or 0)
			vat = float(item.vat or 0)
			# Amount including VAT
			item.amount = rate * (1.0 + vat / 100.0)
			# Default converted_amount to amount if not populated
			if not item.converted_amount:
				item.converted_amount = item.amount

	def on_submit(self):
		self.db_set("status", "Approved")

	def on_cancel(self):
		self.db_set("status", "Cancelled")

@frappe.whitelist()
def revert_to_draft(name):
	frappe.has_permission("Product Survey", ptype="write", throw=True)
	frappe.db.set_value("Product Survey", name, "docstatus", 0)
	frappe.db.set_value("Product Survey", name, "status", "Draft")
	return True

def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user
	
	roles = frappe.get_roles(user)
	if "Purchase Manager" in roles or "System Manager" in roles or user == "Administrator":
		return None
	
	return f"`tabProduct Survey`.owner = '{user}' OR `tabProduct Survey`.person_in_charge = '{user}' OR `tabProduct Survey`.requester = '{user}' OR EXISTS (SELECT 1 FROM `tabProcurement Request` pr WHERE pr.name = `tabProduct Survey`.procurement_request AND pr.owner = '{user}')"

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


