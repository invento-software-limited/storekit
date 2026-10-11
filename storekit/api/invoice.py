import frappe

from storekit.order_emails.events import STAFF_ROLES

# Same Notification the Sales Order confirmation email attaches a PDF from (see
# storekit.order_emails.events.render_print_attachments) - keep "Download Invoice" on the
# customer's order page producing the identical document instead of a separately configured one.
ORDER_CONFIRMATION_NOTIFICATION = "Order Confirmation (Customer)"


def _can_view(sales_order) -> bool:
	"""Staff can view any order; customers only their own."""
	if set(frappe.get_roles()) & STAFF_ROLES:
		return True
	owners = {sales_order.owner, sales_order.contact_email, sales_order.get("custom_quotation_owner")}
	return frappe.session.user in owners


def _get_order_and_print_format(sales_order):
	"""Returns (doc, print_format, error_message)."""
	if not frappe.db.exists("Sales Order", sales_order):
		return None, None, "Order not found."

	doc = frappe.get_doc("Sales Order", sales_order)
	if not _can_view(doc):
		return None, None, "You are not permitted to view this order."

	print_format = (
		frappe.db.get_value("Notification", ORDER_CONFIRMATION_NOTIFICATION, "print_format") or "Standard"
	)
	return doc, print_format, None


@frappe.whitelist()
def get_sales_invoice_for_order(sales_order):
	"""Return the Sales Order (not a Sales Invoice) and the print format used for its confirmation email,
	so "Download Invoice" on the customer's order page matches what they were emailed when they ordered."""
	_doc, print_format, error = _get_order_and_print_format(sales_order)
	if error:
		return {"success": False, "message": error}

	return {
		"success": True,
		"doctype": "Sales Order",
		"docname": sales_order,
		"print_format": print_format,
	}


@frappe.whitelist()
def download_order_pdf(sales_order):
	"""Stream the Sales Order PDF directly, instead of routing through
	frappe.utils.print_format.download_pdf. That generic endpoint enforces ERPNext's portal
	permission check (erpnext.controllers.website_list_for_contact.has_website_permission), which
	requires the customer's User to carry the "Customer" role - something storekit's guest/checkout
	user creation (storekit.webshop_functions.cart.create_user) never assigns. We've already verified
	ownership in _can_view above, so render as Administrator the same safe way
	storekit.order_emails.events._render_pdf does for the confirmation email attachment: snapshot and
	fully restore the session, since frappe.set_user() alone leaves it corrupted (see that function's
	docstring for the full story).
	"""
	doc, print_format, error = _get_order_and_print_format(sales_order)
	if error:
		frappe.throw(error, frappe.PermissionError)

	session_backup = dict(frappe.local.session)
	frappe.set_user("Administrator")
	try:
		pdf = frappe.get_print(doc.doctype, doc.name, print_format=print_format, as_pdf=True)
	finally:
		frappe.local.session.clear()
		frappe.local.session.update(session_backup)

	frappe.local.response.filename = f"{sales_order.replace(' ', '-').replace('/', '-')}.pdf"
	frappe.local.response.filecontent = pdf
	frappe.local.response.type = "pdf"
