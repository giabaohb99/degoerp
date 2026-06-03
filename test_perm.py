import frappe

def run_test():
	try:
		user = "hb.giabao99@gmail.com"
		print(f"Setting user to: {user}")
		frappe.set_user(user)
		print(f"Current User: {frappe.session.user}")
		print(f"Roles: {frappe.get_roles(user)}")
		
		# Test permission check on doctype level
		print("Checking doctype level read permission:")
		print(frappe.has_permission("Procurement Request", ptype="read"))
		
		# Test get_list
		print("Getting list of Procurement Requests:")
		res = frappe.get_list("Procurement Request", fields=["name", "owner", "person_in_charge", "requester"])
		print(res)
	except Exception as e:
		import traceback
		traceback.print_exc()

if __name__ == "__main__":
	run_test()
