import frappe

def main():
    user = "hgbao.idagroup@gmail.com"
    print(f"=== Roles for User: {user} ===")
    if frappe.db.exists("User", user):
        roles = frappe.get_roles(user)
        print("Roles:", roles)
    else:
        print("User does not exist!")
