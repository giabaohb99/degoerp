
import frappe

def run():
    print("=== SEARCHING ALL CUSTOM FIELDS GLOBALLY ===")
    cfs = frappe.get_all("Custom Field", fields=["dt", "fieldname", "label", "fieldtype", "options"])
    found = False
    for cf in cfs:
        fn_lower = cf.fieldname.lower()
        lbl_lower = cf.label.lower() if cf.label else ""
        if "phu_trach" in fn_lower or "nhan_su" in fn_lower or "phụ trách" in lbl_lower or "nhân sự" in lbl_lower:
            print(f"DocType: {cf.dt}, Fieldname: {cf.fieldname}, Label: {cf.label}, Fieldtype: {cf.fieldtype}")
            found = True
            
    if not found:
        print("No matching custom fields found on local database.")

    print("\n=== SEARCHING ALL CUSTOM SCRIPTS GLOBALLY ===")
    client_scripts = frappe.get_all("Client Script", fields=["name", "dt", "enabled"])
    for c in client_scripts:
        doc = frappe.get_doc("Client Script", c.name)
        if "phụ trách" in doc.script or "phu_trach" in doc.script:
            print(f"Client Script Name: {c.name}, Doctype: {c.dt}, Enabled: {c.enabled}")
            print(doc.script)
            print("-" * 50)
            
    server_scripts = frappe.get_all("Server Script", fields=["name", "reference_doctype", "disabled"])
    for s in server_scripts:
        doc = frappe.get_doc("Server Script", s.name)
        if "phụ trách" in doc.script or "phu_trach" in doc.script:
            print(f"Server Script Name: {s.name}, Doctype: {s.reference_doctype}, Disabled: {s.disabled}")
            print(doc.script)
            print("-" * 50)
