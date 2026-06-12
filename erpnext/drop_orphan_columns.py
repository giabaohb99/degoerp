import frappe

def main():
    frappe.init(site="dego")
    frappe.connect()
    
    tables = [
        "tabPurchase Order Item",
        "tabPurchase Receipt Item",
        "tabPurchase Invoice Item"
    ]
    
    columns = [
        "custom_tax_rate",
        "custom_tax_amount",
        "custom_amount_with_tax"
    ]
    
    for table in tables:
        print(f"Checking table: {table}")
        for column in columns:
            try:
                # Check if column exists
                existing = frappe.db.sql(f"SHOW COLUMNS FROM `{table}` LIKE '{column}'")
                if existing:
                    frappe.db.sql(f"ALTER TABLE `{table}` DROP COLUMN `{column}`")
                    print(f"  Dropped {column} successfully.")
                else:
                    print(f"  {column} does not exist.")
            except Exception as e:
                print(f"  Error checking/dropping {column}: {e}")
                
    frappe.db.commit()
    print("Cleanup complete!")

if __name__ == "__main__":
    main()
