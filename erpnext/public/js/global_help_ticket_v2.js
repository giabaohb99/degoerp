frappe.provide("frappe.ui");

frappe.send_it_ticket = function() {
    let user_email = frappe.session.user;
    let user_name = frappe.session.user_fullname;
    let current_url = window.location.href;
    
    // Lấy số điện thoại
    let user_info = frappe.user_info(user_email);
    let user_phone = (user_info && user_info.mobile_no) ? user_info.mobile_no : '';
    
    let google_form_url = `https://docs.google.com/forms/d/e/1FAIpQLSdCNItn-j9tZ1iCoeUQ-4-oLrvw7LbuJ8bY8E3413N7fFkUSw/viewform?usp=pp_url`
        + `&entry.1092956449=${encodeURIComponent(user_name)}`
        + `&entry.514762407=${encodeURIComponent(user_email)}`
        + `&entry.757474614=${encodeURIComponent(user_phone)}`
        + `&entry.595534741=${encodeURIComponent(current_url)}`;
    
    window.open(google_form_url, '_blank');
};

// Hàm patch prototype của SidebarHeader
function patch_sidebar_header(SidebarHeaderClass) {
    if (SidebarHeaderClass && SidebarHeaderClass.prototype && !SidebarHeaderClass.prototype.add_navbar_items._patched) {
        const original_add_navbar_items = SidebarHeaderClass.prototype.add_navbar_items;
        SidebarHeaderClass.prototype.add_navbar_items = function() {
            const reloadIndex = this.dropdown_items.findIndex(item => item.label === "Reload");
            if (reloadIndex !== -1) {
                // Tránh trùng lặp
                const hasTicket = this.dropdown_items.some(item => item.name === "help_ticket" || item.label === __("Báo lỗi hệ thống (Gửi Ticket)") || item.label === "Báo lỗi hệ thống (Gửi Ticket)");
                if (!hasTicket) {
                    this.dropdown_items.splice(reloadIndex + 1, 0, {
                        name: "help_ticket",
                        label: __("Báo lỗi hệ thống (Gửi Ticket)"),
                        action: "frappe.send_it_ticket()",
                        onClick: function() {
                            frappe.send_it_ticket();
                        },
                        is_standard: 1,
                        icon: "alert-circle"
                    });
                }
            }
            original_add_navbar_items.apply(this, arguments);
        };
        SidebarHeaderClass.prototype.add_navbar_items._patched = true;
    }
}

// Sử dụng getter/setter trên frappe.ui.SidebarHeader để tránh lỗi race condition khi load bundle
let _SidebarHeader = frappe.ui.SidebarHeader;
if (_SidebarHeader) {
    patch_sidebar_header(_SidebarHeader);
}

Object.defineProperty(frappe.ui, 'SidebarHeader', {
    get() {
        return _SidebarHeader;
    },
    set(val) {
        _SidebarHeader = val;
        patch_sidebar_header(val);
    },
    configurable: true
});
