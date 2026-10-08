"""Jinja helper for the order Notifications: `order_email_context(doc)` returns display-ready order data."""

import frappe
from frappe.contacts.doctype.address.address import get_default_address
from frappe.utils import fmt_money, formatdate, get_url, validate_email_address

PAYMENT_METHOD = "Cash on Delivery"


# ERPNext Sales Order status -> customer-facing label
STATUS_LABELS = {
	"To Deliver and Bill": "Confirmed",
	"To Deliver": "Confirmed",
	"To Bill": "Shipped",
	"Completed": "Delivered",
	"Cancelled": "Cancelled",
	"Draft": "Pending",
}


def order_email_context(doc) -> frappe._dict:
	"""Display-ready data for the email layout. `doc` is a Sales Order, or a Delivery Note / Sales Invoice linked to one.

	Never raises: a bad value must not block the transaction that triggered the email.
	"""
	try:
		return _build(_resolve_order(doc))
	except Exception:
		frappe.log_error(title=f"order_email_context failed for {doc.name}")
		return frappe._dict(order_number=doc.name, lines=[], **_company())


def _resolve_order(doc):
	if doc.doctype == "Sales Order":
		return doc
	field = "against_sales_order" if doc.doctype == "Delivery Note" else "sales_order"
	return frappe.get_doc("Sales Order", next(i.get(field) for i in doc.items if i.get(field)))


def _build(order) -> frappe._dict:
	def money(v):
		return fmt_money(v or 0, currency=order.currency)

	shipping, tax = _split_charges(order)
	total = order.rounded_total or order.grand_total
	ctx = frappe._dict(
		customer_name=order.customer_name,
		customer_phone=order.contact_mobile or order.contact_phone or "",
		customer_email=order.get("custom_notification_email") or "",
		order_number=order.name,
		order_date=formatdate(order.transaction_date),
		order_status="Cancelled" if order.docstatus == 2 else STATUS_LABELS.get(order.status, order.status),
		order_notes=order.get("custom_customer_notes") or "",
		lines=[_line(i, money) for i in order.items],
		subtotal=money(order.total),
		discount=money(order.discount_amount) if order.discount_amount else "",
		tax=money(tax) if tax else "",
		shipping_charge=money(shipping) if shipping else "",
		order_total=money(total),
		cod_amount=money(total),
		payment_method=order.get("custom_payment_method") or PAYMENT_METHOD,
		billing_address=(order.address_display or "").strip(),
		shipping_address=(order.shipping_address or "").strip(),
		delivery_date=formatdate(order.delivery_date) if order.delivery_date else "",
		cancellation_reason=order.get("custom_cancellation_reason") or "",
		cancellation_date=formatdate(frappe.utils.nowdate()),
		view_order_url=get_url("/profile"),
		tracking_number="",
		tracking_url="",
		courier="",
		dispatch_date="",
	)
	ctx.update(_delivery_details(order))
	ctx.update(_company(order.company))
	return ctx


def get_customer_email(order) -> str:
	"""Best valid email for the customer (contact_email can hold a user id or a typo'd value)."""
	candidates = [order.contact_email, order.get("custom_quotation_owner"), order.owner]
	if order.contact_person:
		candidates.insert(
			1,
			frappe.db.get_value(
				"Contact Email", {"parent": order.contact_person, "is_primary": 1}, "email_id"
			),
		)
	return next((c for c in candidates if c and validate_email_address(c)), "")


def _line(item, money) -> dict:
	return {
		"item_name": item.item_name,
		"item_code": item.item_code,
		"qty": item.qty,
		"rate": money(item.rate),
		"amount": money(item.amount),
	}


def _split_charges(order) -> tuple[float, float]:
	"""Split tax rows into (delivery charge, other tax). Shipping rows are named after the shipping rule."""
	rule = order.shipping_rule
	label = frappe.db.get_value("Shipping Rule", rule, "label") if rule else None
	shipping = tax = 0.0
	for row in order.taxes:
		desc = (row.description or "").lower()
		if (
			(rule and desc in (rule.lower(), (label or "").lower()))
			or "shipping" in desc
			or "delivery" in desc
		):
			shipping += row.tax_amount or 0
		else:
			tax += row.tax_amount or 0
	return shipping, tax


def _delivery_details(order) -> dict:
	"""Latest submitted Delivery Note for the order: courier, tracking and dispatch date."""
	parents = frappe.get_all(
		"Delivery Note Item", {"against_sales_order": order.name, "docstatus": 1}, pluck="parent"
	)
	if not parents:
		return {}
	dn = frappe.db.get_value(
		"Delivery Note",
		{"name": ("in", parents)},
		["posting_date", "transporter_name", "lr_no", "custom_tracking_url"],
		order_by="creation desc",
		as_dict=True,
	)
	return {
		"courier": dn.transporter_name or "",
		"tracking_number": dn.lr_no or "",
		"tracking_url": dn.custom_tracking_url or "",
		"dispatch_date": formatdate(dn.posting_date),
	}


def _company(name: str | None = None) -> dict:
	"""Branding and support details from the Company record and Webshop Settings (no separate settings doctype)."""
	name = name or frappe.defaults.get_global_default("company")
	c = (
		frappe.db.get_value("Company", name, ["company_name", "email", "phone_no", "website"], as_dict=True)
		or {}
	)
	addr = get_default_address("Company", name) if name else None
	logo = frappe.db.get_single_value("Webshop Settings", "logo")
	return {
		"company_name": c.get("company_name") or name or "Our Store",
		"support_email": c.get("email") or "",
		"support_phone": c.get("phone_no") or "",
		"company_address": _address_line(addr),
		"logo_url": get_url(logo) if logo else "",
		"logo_data_uri": _logo_data_uri(logo or frappe.db.get_value("Company", name, "company_logo")),
		"brand_color": frappe.db.get_single_value("Webshop Settings", "primary_color") or "#1f3a5f",
	}


def _address_line(name: str | None) -> str:
	"""One-line postal address from the Company's default Address (empty parts skipped)."""
	if not name:
		return ""
	a = frappe.db.get_value(
		"Address", name, ["address_line1", "address_line2", "city", "pincode", "country"], as_dict=True
	)
	return (
		", ".join(p for p in (a.address_line1, a.address_line2, a.city, a.pincode, a.country) if p)
		if a
		else ""
	)


def _logo_data_uri(file_url: str | None) -> str:
	"""Embed the logo so PDFs can show it even when it is a private file or the site hostname is not resolvable."""
	import base64
	import mimetypes
	import os

	if not file_url or not file_url.startswith(("/files/", "/private/files/")):
		return ""
	path = (
		frappe.get_site_path(file_url.lstrip("/"))
		if file_url.startswith("/private/")
		else frappe.get_site_path("public", file_url.lstrip("/"))
	)
	if not os.path.isfile(path):
		return ""
	with open(path, "rb") as f:
		return f"data:{mimetypes.guess_type(path)[0] or 'image/png'};base64,{base64.b64encode(f.read()).decode()}"
