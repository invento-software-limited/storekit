"""Document events that fire the standard order Notifications ERPNext cannot trigger by itself.

ERPNext updates a Sales Order's status with direct DB writes (when a Delivery Note or Sales Invoice is
submitted), so Value Change Notifications never see it. These hooks call the Notifications' "Method" events instead.
"""

import functools
import json
import re

import frappe

from storekit.order_emails.jinja_methods import get_customer_email

STAFF_ROLES = {"System Manager", "Sales Manager", "Sales User", "Stock User", "Stock Manager"}
ORDER_SHIPPED = "order_shipped"
ORDER_COMPLETED = "order_completed"


def safe(fn):
	"""Email problems must never block delivery notes, invoices or orders: log and swallow."""

	@functools.wraps(fn)
	def wrapper(doc, method=None):
		try:
			fn(doc, method)
		except Exception:
			frappe.log_error(title=f"Order email event failed: {fn.__name__} {doc.name}")

	return wrapper


def fill_notification_email(doc, method=None):
	"""Sales Order / Delivery Note validate: keep an editable, valid recipient for the customer Notifications."""
	from frappe.utils import validate_email_address

	if doc.doctype == "Delivery Note":
		order = _first_order(doc)
		doc.custom_notification_email = (
			frappe.db.get_value("Sales Order", order, "custom_notification_email") if order else None
		)
	elif not (doc.get("custom_notification_email") and validate_email_address(doc.custom_notification_email)):
		doc.custom_notification_email = get_customer_email(doc)


def remember_order_status(doc, method=None):
	"""Delivery Note / Sales Invoice before_submit: note each order's status so a change can be detected later."""
	frappe.flags.order_status_before = {
		n: frappe.db.get_value("Sales Order", n, "status") for n in linked_orders(doc)
	}


@safe
def after_delivery_note_submit(doc, method=None):
	"""Each dispatched Delivery Note triggers the 'Order Shipped' Notification, then the completion check."""
	for name in linked_orders(doc):
		frappe.get_doc("Sales Order", name).run_method(ORDER_SHIPPED)
	_notify_if_completed(doc)


@safe
def after_invoice_submit(doc, method=None):
	_notify_if_completed(doc)


def _notify_if_completed(doc):
	"""Fire 'Order Delivered' once, when the order's status moves to Completed."""
	before = frappe.flags.get("order_status_before") or {}
	for name in linked_orders(doc):
		if (
			before.get(name) != "Completed"
			and frappe.db.get_value("Sales Order", name, "status") == "Completed"
		):
			frappe.get_doc("Sales Order", name).run_method(ORDER_COMPLETED)


def linked_orders(doc) -> set[str]:
	field = "against_sales_order" if doc.doctype == "Delivery Note" else "sales_order"
	return {i.get(field) for i in doc.items if i.get(field)}


def _first_order(doc) -> str | None:
	return next(iter(sorted(linked_orders(doc))), None)


def render_print_attachments(doc, method=None):
	"""Email Queue before_insert: turn 'attach print' requests into stored PDF files, safely.

	ERPNext otherwise renders the PDF at send time, and one failed render (e.g. wkhtmltopdf cannot reach the
	site URL) leaves the whole email stuck as Not Sent. Here a failed render just drops the attachment.
	"""
	if doc.reference_doctype != "Sales Order" or not doc.attachments:
		return
	kept = []
	for att in json.loads(doc.attachments):
		if att.get("print_format_attachment") != 1:
			kept.append(att)
		elif file_url := _print_file_url(att, doc.reference_name):
			kept.append({"file_url": file_url})
	doc.attachments = json.dumps(kept)


def _print_file_url(att: dict, order: str) -> str | None:
	pdf = _render_pdf(att["doctype"], att["name"], att.get("print_format"))
	if not pdf:
		return None
	from frappe.utils.file_manager import save_file

	return save_file(f"{order}.pdf", pdf, "Sales Order", order, is_private=1).file_url


def _render_pdf(doctype: str, name: str, print_format: str | None) -> bytes | None:
	"""Render as the system user: the order is often placed by a website customer, who may not be allowed to
	print a Sales Order. Standard render first; if the PDF engine cannot fetch the print stylesheet, retry
	without it (the print format carries its own inline CSS). Returns None when both fail."""
	from frappe.utils.pdf import get_pdf

	user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		try:
			return frappe.get_print(doctype, name, print_format=print_format, as_pdf=True)
		except Exception:
			pass
		html = frappe.get_print(doctype, name, print_format=print_format, as_pdf=False)
		return get_pdf(re.sub(r"<link[^>]+print\.bundle[^>]+>", "", html))
	except Exception:
		frappe.log_error(title=f"Order PDF attachment failed for {name}")
		return None
	finally:
		frappe.set_user(user)


def repair_stuck_order_emails():
	"""One-off helper: re-render attachments for order emails stuck as Not Sent, then send them."""
	for name in frappe.get_all(
		"Email Queue", {"status": "Not Sent", "reference_doctype": "Sales Order"}, pluck="name"
	):
		q = frappe.get_doc("Email Queue", name)
		render_print_attachments(q)
		q.db_set("attachments", q.attachments)
		q.send()


def send_queued_now(doc, method=None):
	"""Email Queue after_insert: push order emails out right away instead of waiting for the scheduler."""
	if doc.reference_doctype in ("Sales Order", "Delivery Note"):
		frappe.enqueue(send_queued, queue_name=doc.name, queue="short", enqueue_after_commit=True)


def send_queued(queue_name: str):
	doc = frappe.get_doc("Email Queue", queue_name)
	if doc.status == "Not Sent":
		doc.send()
