"""Move records owned by the legacy invento_webshop/hopkins apps over to storekit.

Runs after install; a no-op on sites that never had the legacy apps. Uses direct SQL so
no controller hooks (Builder exports, notifications) fire mid-migration.
"""

import frappe

from storekit.setup.legacy_names import APP, LEGACY_APPS, LEGACY_MODULES, MODULE, has_legacy_reference, rewrite

# DocTypes whose stored code/markup may call legacy method paths or asset URLs.
CONTENT_DOCTYPES = (
	"Builder Page",
	"Builder Component",
	"Builder Client Script",
	"Builder Variable",
	"Builder Settings",
	"Notification",
	"Email Template",
	"Print Format",
	"Server Script",
	"Client Script",
	"Web Page",
	"Website Settings",
	"Custom HTML Block",
	"Webshop Theme",
	"Webshop Settings",
)
TEXT_FIELDTYPES = (
	"Data", "Small Text", "Text", "Long Text", "Code", "HTML Editor",
	"Text Editor", "JSON", "Markdown Editor", "Attach", "Attach Image",
)  # fmt: skip


def execute():
	ensure_project_folder()
	if not frappe.db.exists("Module Def", {"name": ("in", LEGACY_MODULES)}):
		return
	reassign_modules()
	reassign_builder_ownership()
	rewrite_contents()
	drop_legacy_records()
	regenerate_builder_assets()
	frappe.clear_cache()


def reassign_modules():
	"""Point every record with a `module` link at the StoreKit module."""
	for doctype in frappe.get_all("DocField", filters={"fieldname": "module", "options": "Module Def"}, pluck="parent"):
		if is_real_table(doctype):
			frappe.db.sql(
				f"update `tab{doctype}` set module = %s where module in %s",
				(MODULE, LEGACY_MODULES),
			)


def reassign_builder_ownership():
	"""Move standard pages and project folders from the legacy apps to storekit."""
	frappe.db.sql("update `tabBuilder Page` set app = %s where app in %s", (APP, LEGACY_APPS))
	frappe.db.sql(
		"update `tabBuilder Page` set project_folder = %s where project_folder in %s", (APP, LEGACY_APPS)
	)
	frappe.db.delete("Builder Project Folder", {"name": ("in", LEGACY_APPS)})


def ensure_project_folder():
	"""Fixture pages link to the storekit folder, and fixtures import before Builder syncs it."""
	if not frappe.db.exists("Builder Project Folder", APP):
		frappe.get_doc({"doctype": "Builder Project Folder", "folder_name": APP, "is_standard": 1}).insert(
			ignore_permissions=True
		)


def rewrite_contents():
	for doctype in CONTENT_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		fields = text_fields(doctype)
		if frappe.get_meta(doctype).issingle:
			rewrite_single(doctype, fields)
		elif is_real_table(doctype):
			rewrite_table(doctype, fields)


def rewrite_single(doctype, fields):
	for field in fields:
		value = frappe.db.get_single_value(doctype, field)
		if has_legacy_reference(value):
			frappe.db.set_single_value(doctype, field, rewrite(value), update_modified=False)


def rewrite_table(doctype, fields):
	for field in fields:
		rows = frappe.db.sql(
			f"select name, `{field}` from `tab{doctype}` where `{field}` regexp %s",
			("invento_webshop|hopkins",),
		)
		for name, value in rows:
			new_value = rewrite(value)
			if new_value != value:
				frappe.db.set_value(doctype, name, field, new_value, update_modified=False)


def drop_legacy_records():
	"""Remove records the legacy apps owned that storekit now ships under its own name."""
	for app in LEGACY_APPS:
		frappe.db.delete("Scheduled Job Type", {"method": ("like", f"{app}.%")})
	frappe.db.delete("Desktop Icon", {"name": "Hopkins", "app": ("in", LEGACY_APPS)})
	# Workspace Sidebar.module is a plain Text field, so reassign_modules() skips it.
	for sidebar in frappe.get_all("Workspace Sidebar", filters={"app": ("in", LEGACY_APPS)}, pluck="name"):
		frappe.db.delete("Workspace Sidebar Item", {"parent": sidebar, "parenttype": "Workspace Sidebar"})
		frappe.db.delete("Workspace Sidebar", sidebar)
	frappe.db.delete("Module Def", {"name": ("in", LEGACY_MODULES)})


def regenerate_builder_assets():
	"""Builder serves settings and client scripts from generated files; rebuild them from the rewritten DB."""
	settings = frappe.get_doc("Builder Settings")
	settings.update_script_file("style", "css", "css", "page_styles")
	settings.update_script_file("script", "JavaScript", "js", "page_scripts")
	for name in frappe.get_all("Builder Client Script", pluck="name"):
		frappe.get_doc("Builder Client Script", name).update_script_file()


def text_fields(doctype):
	return [field.fieldname for field in frappe.get_meta(doctype).fields if field.fieldtype in TEXT_FIELDTYPES]


def is_real_table(doctype):
	meta = frappe.get_meta(doctype)
	return not (meta.issingle or meta.is_virtual) and frappe.db.table_exists(doctype)
