# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class ProcurementRequestItem(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amount: DF.Currency
		brand: DF.Link | None
		buyer: DF.Link | None
		description: DF.TextEditor | None
		image: DF.Attach | None
		item_class: DF.Link | None
		item_code: DF.Link | None
		item_group: DF.Link | None
		item_name: DF.Data
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		proposed_rate: DF.Currency
		qty: DF.Int
		warehouse: DF.Link | None
		schedule_date: DF.Date | None
		uom: DF.Link | None
	# end: auto-generated types

	def __getattr__(self, name):
		try:
			return super().__getattr__(name)
		except AttributeError:
			# Fallback for virtual pricing/margin/discount fields to prevent AttributeErrors
			virtual_fields = {
				"margin_type": "",
				"margin_rate_or_amount": 0.0,
				"rate_with_margin": 0.0,
				"base_rate_with_margin": 0.0,
				"discount_percentage": 0.0,
				"discount_amount": 0.0,
				"price_list_rate": 0.0,
				"base_price_list_rate": 0.0,
				"rate": 0.0,
				"base_rate": 0.0,
				"base_amount": 0.0,
				"net_rate": 0.0,
				"net_amount": 0.0,
				"base_net_rate": 0.0,
				"base_net_amount": 0.0,
				"pricing_rules": "",
				"item_tax_rate": "",
				"item_tax_template": "",
				"pricing_rule_removed": 0,
				"remove_free_item": 0,
				"stock_qty": 0.0,
				"conversion_factor": 1.0,
			}
			if name in virtual_fields:
				return virtual_fields[name]
			raise

	def __setattr__(self, name, value):
		# Allow setting virtual attributes without raising AttributeError
		virtual_fields = {
			"margin_type",
			"margin_rate_or_amount",
			"rate_with_margin",
			"base_rate_with_margin",
			"discount_percentage",
			"discount_amount",
			"price_list_rate",
			"base_price_list_rate",
			"rate",
			"base_rate",
			"base_amount",
			"net_rate",
			"net_amount",
			"base_net_rate",
			"base_net_amount",
			"pricing_rules",
			"item_tax_rate",
			"item_tax_template",
			"pricing_rule_removed",
			"remove_free_item",
			"stock_qty",
			"conversion_factor",
		}
		if name in virtual_fields:
			self.__dict__[name] = value
		else:
			super().__setattr__(name, value)
