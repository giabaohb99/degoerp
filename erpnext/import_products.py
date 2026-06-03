import csv
import os
import re
import frappe

def clean_category(cat):
    if not cat:
        return "VTBB"
    # Remove square brackets and double quotes
    cat = cat.replace('[', '').replace(']', '').replace('"', '')
    cat = cat.strip()
    
    # Check for uppercase exceptions
    cat_upper = cat.upper()
    if cat_upper in ["NL", "NDT", "ICARE"]:
        return cat_upper
        
    # Standardize casing to Title Case (e.g. "nhãn phụ" -> "Nhãn Phụ")
    return cat.title()

def ensure_parent_item_group():
    parent_id = "VTBB"
    if not frappe.db.exists("Item Group", parent_id):
        try:
            ig_doc = frappe.get_doc({
                "doctype": "Item Group",
                "item_group_name": parent_id,
                "parent_item_group": "All Item Groups",
                "is_group": 1
            })
            ig_doc.insert(ignore_permissions=True)
            print(f"Created main parent Item Group: {parent_id}")
        except Exception as e:
            print(f"Error creating main parent {parent_id}: {e}")

def ensure_child_item_group(cat):
    if cat == "VTBB":
        return
    if not frappe.db.exists("Item Group", cat):
        try:
            ig_doc = frappe.get_doc({
                "doctype": "Item Group",
                "item_group_name": cat,
                "parent_item_group": "VTBB",
                "is_group": 0
            })
            ig_doc.insert(ignore_permissions=True)
            print(f"Created child Item Group: {cat} under VTBB")
        except Exception as e:
            print(f"Error creating child Item Group {cat}: {e}")

def ensure_uom(uom_name):
    if not frappe.db.exists("UOM", uom_name):
        try:
            uom_doc = frappe.get_doc({
                "doctype": "UOM",
                "uom_name": uom_name
            })
            uom_doc.insert(ignore_permissions=True)
            print(f"Created UOM: {uom_name}")
        except Exception as e:
            print(f"Error creating UOM {uom_name}: {e}")

def get_or_create_uom(uom_name):
    # Try multiple standard capitalization variations to match existing database UOMs
    alternatives = [uom_name, uom_name.lower(), uom_name.capitalize()]
    for alt in alternatives:
        if frappe.db.exists("UOM", alt):
            return alt
            
    # If it doesn't exist, create it
    ensure_uom(uom_name)
    return uom_name

def guess_uom(name, category):
    if not name:
        return "Cái"
        
    name_lower = name.lower()
    
    # 1. Special case: Băng keo -> Cuộn
    if category == "Băng Keo" or "băng keo" in name_lower or "cuộn" in name_lower:
        return "Cuộn"
        
    # 2. Special case: Tấm vách -> Tấm
    if category == "Tấm Vách" or "tấm vách" in name_lower or "tấm" in name_lower:
        return "Tấm"
        
    # 3. Special case: NL (Nguyên liệu)
    if category == "NL":
        if any(kw in name_lower for kw in ["lít", "lit", "ml", " 1l ", " 2l ", " 5l "]):
            return "Lít"
        return "Kg"
        
    # 4. Special case: ICARE (Sanitizer finished goods)
    if category == "ICARE":
        if any(kw in name_lower for kw in ["can", " 4l ", " 10l ", " 4 lít ", " 10 lít "]):
            return "Can"
        return "Chai"
        
    # 5. Default stock UOM for other packaging materials (Thùng, Chai, Hộp, Nắp, Nhãn, etc.)
    return "Cái"

def run():
    print("==> STARTING ITEM IMPORT MIGRATION...")
    
    filepath = "/home/frappe/frappe-bench/apps/erpnext/erpnext/productdata.txt"
    if not os.path.exists(filepath):
        print(f"Error: productdata.txt not found at {filepath}")
        return
        
    # 1. Ensure parent VTBB exists
    ensure_parent_item_group()
    
    # 2. Read and parse items
    imported_count = 0
    updated_count = 0
    error_count = 0
    
    print("\n==> Processing rows from productdata.txt...")
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)
        
        # Identify column indices
        try:
            cat_idx = header.index("Phân Loại")
            code_idx = header.index("Mã VTBB/NL")
            name_idx = header.index("Tên VTBB/NL")
        except ValueError:
            print("Error: Required columns not found in header!")
            return
            
        for idx, row in enumerate(reader, 2):
            if len(row) <= max(cat_idx, code_idx, name_idx):
                continue
                
            raw_cat = row[cat_idx].strip()
            raw_code = row[code_idx].strip()
            raw_name = row[name_idx].strip()
            
            # Skip if both code and name are blank
            if not raw_code and not raw_name:
                continue
                
            # Use name as code if code is missing, or auto-generate
            code = raw_code if raw_code else f"AUTO-VTBB-{idx}"
            name = raw_name if raw_name else code
            
            # Clean and ensure Item Group
            category = clean_category(raw_cat)
            ensure_child_item_group(category)
            
            # Guess and resolve UOM
            uom_candidate = guess_uom(name, category)
            uom = get_or_create_uom(uom_candidate)
            
            # Identify stock vs sales vs purchase permissions
            # Raw materials (NL) are for stock and purchase, not sales
            # Sanitizers (ICARE) are for stock, purchase, and sales
            # Packaging (VTBB) is for stock and purchase, not sales
            is_stock = 1
            is_purchase = 1
            is_sales = 1 if category == "ICARE" else 0
            
            try:
                if frappe.db.exists("Item", code):
                    item_doc = frappe.get_doc("Item", code)
                    # Update fields
                    item_doc.item_name = name
                    item_doc.item_group = category
                    item_doc.stock_uom = uom
                    item_doc.is_stock_item = is_stock
                    item_doc.is_sales_item = is_sales
                    item_doc.is_purchase_item = is_purchase
                    item_doc.save(ignore_permissions=True)
                    updated_count += 1
                else:
                    item_doc = frappe.get_doc({
                        "doctype": "Item",
                        "item_code": code,
                        "item_name": name,
                        "item_group": category,
                        "stock_uom": uom,
                        "is_stock_item": is_stock,
                        "is_sales_item": is_sales,
                        "is_purchase_item": is_purchase
                    })
                    item_doc.insert(ignore_permissions=True)
                    imported_count += 1
                    
            except Exception as e:
                error_count += 1
                if error_count <= 20:
                    print(f"   [Error Row {idx}] Failed to import {code}: {e}")
                    
            # Commit periodically to keep transactions clean
            if (imported_count + updated_count) % 500 == 0 and (imported_count + updated_count) > 0:
                frappe.db.commit()
                print(f"   Processed {imported_count + updated_count} items... (Imported: {imported_count}, Updated: {updated_count})")
                
    # Rebuild Item Group tree just to ensure nestedset is fully synced and stable
    try:
        from frappe.utils.nestedset import rebuild_tree
        rebuild_tree("Item Group", "parent_item_group")
        print("\n==> Rebuilt Item Group tree successfully!")
    except Exception as e:
        print(f"Error rebuilding Item Group tree: {e}")
        
    # Final database commit
    frappe.db.commit()
    
    print(f"\n==> MIGRATION SUMMARY:")
    print(f"   Total Imported: {imported_count}")
    print(f"   Total Updated: {updated_count}")
    print(f"   Total Errors: {error_count}")
    print("==> MIGRATION COMPLETED SUCCESSFULLY!")
