"""Order-email overrides of the cart/order APIs (wired in hooks.py)."""

import frappe
from storekit.webshop_functions.cart import place_order as _place_order

from storekit.order_emails.events import STAFF_ROLES

COD = "Cash on Delivery"


@frappe.whitelist(allow_guest=True)
def place_order(doc=None, cart_items=None):
	"""Hopkins takes Cash on Delivery only: any other payment mode is forced to COD, so no card flow can start."""
	if doc:
		doc = frappe.parse_json(doc)
		doc["mode_of_payment"] = COD
	return _place_order(doc=doc, cart_items=cart_items)


def _can_cancel(sales_order) -> bool:
	"""Staff can always cancel; customers only their own order, before anything is delivered."""
	if set(frappe.get_roles()) & STAFF_ROLES:
		return True
	owners = {sales_order.owner, sales_order.contact_email, sales_order.get("custom_quotation_owner")}
	return frappe.session.user in owners and not sales_order.per_delivered


@frappe.whitelist()
def cancel_order(order_id, reason=None):
	"""Cancel an order (own order only for customers) and store the reason; the cancellation Notifications do the emailing."""
	try:
		sales_order = frappe.get_doc("Sales Order", order_id)

		if sales_order.docstatus == 2:
			return {"status": "error", "message": "Sales Order is already canceled"}
		if not _can_cancel(sales_order):
			return {
				"status": "error",
				"message": "This order can no longer be cancelled online. Please contact support.",
			}

		if reason:
			sales_order.db_set("custom_cancellation_reason", reason, update_modified=False)
		sales_order.flags.ignore_permissions = True
		sales_order.cancel()

		return {"status": "success", "message": f"Sales Order {order_id} has been canceled"}

	except frappe.DoesNotExistError:
		return {"status": "error", "message": "Sales Order not found"}
	except Exception as e:
		return {"status": "error", "message": str(e)}
