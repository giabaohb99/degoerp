def get_data():
	return {
		"fieldname": "procurement_request",
		"internal_links": {
			"Purchase Order": ["items", "procurement_request"],
		},
		"transactions": [
			{"items": ["Supplier Survey", "Product Survey"]},
			{"label": "Related", "items": ["Purchase Order"]},
		],
	}
