"""Login / existing-account helpers for the checkout page (guests can reach these)."""

import frappe
from frappe import _
from frappe.utils import cint


def user_exists(email):
	email = (email or "").strip().lower()
	return bool(email) and bool(frappe.db.exists("User", email))


@frappe.whitelist(allow_guest=True)
def email_has_account(email=None):
	"""Lets the checkout form warn about an already-registered email before the order is placed."""
	return {"exists": user_exists(email)}


@frappe.whitelist(allow_guest=True)
def checkout_login(email=None, password=None, cart_items=None):
	"""
	Log a guest in from the checkout page and fold their cookie cart into their saved cart,
	so they land back on /checkout with the same products.
	"""
	if frappe.session.user != "Guest":
		return {"success": True, "already_logged_in": True}

	email = (email or "").strip().lower()
	if not email or not password:
		return {"success": False, "message": _("Please enter your email and password.")}

	login_manager = frappe.local.login_manager
	try:
		login_manager.authenticate(email, password)
		login_manager.post_login()
	except frappe.AuthenticationError:
		frappe.clear_messages()
		return {"success": False, "message": _("Incorrect email or password.")}

	_merge_guest_cart(cart_items)
	return {"success": True, "full_name": login_manager.full_name}


def _merge_guest_cart(cart_items):
	from storekit.webshop_functions.cart import _get_cart_quotation, _run_as_system_user, set_cart_count

	items = frappe.parse_json(cart_items) if cart_items else []
	items = [item for item in items if item.get("item_code")]
	quotation = _get_cart_quotation()
	quotation.flags.ignore_permissions = True

	if items:
		# Replace, don't merge: checkout shows exactly what's in the guest cart right
		# now. An old saved cart from a previous, abandoned session must not silently
		# add its quantities back in on login - the guest cart the customer just built
		# is the one they mean to check out with.
		quotation.set("items", [])
		for item in items:
			qty = cint(item.get("qty")) or 1
			quotation.append(
				"items",
				{"doctype": "Quotation Item", "item_code": item["item_code"], "qty": qty},
			)
		quotation.payment_schedule = []
		# Force a fresh price list lookup: ERPNext only re-fills rate/price_list_rate
		# when the field is None, not when it's an explicit 0, so a row already stuck
		# at £0.00 from before (see cart.update_cart's matching reset) would otherwise
		# carry that £0.00 into the merged cart forever.
		for quotation_item in quotation.items:
			quotation_item.price_list_rate = quotation_item.rate = quotation_item.amount = None
		# The freshly-logged-in Website User may have no role granting Item read -
		# set_missing_values/save fetch Item details and check_permission() on them,
		# same reason place_order's own quotation work runs as system user.
		with _run_as_system_user():
			quotation.run_method("set_missing_values")
			quotation.save(ignore_permissions=True, ignore_version=True)

	frappe.local.cookie_manager.set_cookie("cart_items", [])
	set_cart_count(quotation=quotation)
