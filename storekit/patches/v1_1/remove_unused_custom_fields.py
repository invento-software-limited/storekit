import frappe

# Custom fields StoreKit no longer defines or reads. The Item Group set is the old
# Webshop website block; the Item fields are legacy Hub/Odoo sync fields; the Sales
# Order fields were never synced (that file has sync_on_migrate off).
UNUSED_FIELDS = {
	"Item Group": [
		"custom_website_settings",
		"show_in_website",
		"route",
		"website_title",
		"description",
		"website_specifications",
		"website_filters_section",
		"filter_fields",
		"filter_attributes",
		"include_descendants",
		"column_break_16",
		"weightage",
		"slideshow",
	],
	"Item": ["hub_sync_id", "odooerpid", "published_in_website"],
	"Sales Order": ["test", "add_shipping_and_taxes1", "internal_picking_list_note"],
}


def execute():
	for doctype, fieldnames in UNUSED_FIELDS.items():
		remove_fields(doctype, fieldnames)


def remove_fields(doctype: str, fieldnames: list[str]) -> None:
	names = frappe.get_all(
		"Custom Field", filters={"dt": doctype, "fieldname": ["in", fieldnames]}, pluck="name"
	)
	for name in names:
		frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)
	frappe.db.delete("Property Setter", {"doc_type": doctype, "field_name": ["in", fieldnames]})
	if names:
		frappe.clear_cache(doctype=doctype)
