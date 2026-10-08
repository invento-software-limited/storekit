"""Idempotent setup for order emails: custom fields + standard Notification records.

Runs after every migrate and only creates what is missing, so edits made to the
Notifications (subject, body, recipients, sender) are never overwritten.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

LAYOUT = "storekit/templates/emails"
INC = '{% include "' + LAYOUT + "/"
SUMMARY = (
	INC
	+ 'order_status.html" %}\n'
	+ INC
	+ 'order_items.html" %}\n'
	+ INC
	+ 'order_addresses.html" %}\n'
	+ INC
	+ 'cod_notice.html" %}\n'
)
BUTTON = '{% set cta_url = o.view_order_url %}{% set cta_label = "View Order" %}' + INC + 'button.html" %}\n'
HI = "<p>Hi {{ o.customer_name }},</p>\n"
ETA = "{% if o.delivery_date %}<p><strong>Estimated delivery:</strong> {{ o.delivery_date }}</p>{% endif %}\n"
CANCEL_INFO = (
	"<p><strong>Cancellation date:</strong> {{ o.cancellation_date }}"
	"{% if o.cancellation_reason %}<br><strong>Reason:</strong> {{ o.cancellation_reason }}{% endif %}</p>\n"
)
CONTACT = (
	"<p><strong>Customer:</strong> {{ o.customer_name }}<br><strong>Phone:</strong> {{ o.customer_phone or '-' }}<br>"
	"<strong>Email:</strong> {{ o.customer_email or '-' }}</p>\n"
)


def _message(heading: str, body: str) -> str:
	"""Notification message: the shared layout plus an editable heading and body."""
	return (
		'{% extends "' + LAYOUT + '/order_layout.html" %}\n{% set o = order_email_context(doc) %}\n'
		'{% set heading = "' + heading + '" %}\n{% block body %}\n' + body + "{% endblock %}"
	)


METHODS = {"Order Shipped (Customer)": "order_shipped", "Order Delivered (Customer)": "order_completed"}
CUSTOMER_FIELD = "custom_notification_email"
# Admin recipient defaults to the Company email; replace it with any address in the Notification's CC column.
ADMIN_CC = '{{ frappe.db.get_value("Company", doc.company, "email") or "" }}'

NOTIFICATIONS = [
	# (name, subject, event, condition, audience, heading, body)
	(
		"Order Confirmation (Customer)",
		"Order Confirmation – Order #{{ doc.name }}",  # noqa: RUF001
		"Submit",
		"",
		"Customer",
		"Thank you for your order",
		HI
		+ "<p>Thank you for shopping with us. We have received your order and will contact you if we need anything else.</p>\n"
		+ ETA
		+ SUMMARY
		+ BUTTON,
	),
	(
		"New Order (Admin)",
		"New Online Order Received – #{{ doc.name }}",  # noqa: RUF001
		"Submit",
		"",
		"Admin",
		"New online order received",
		"<p>A new order has been placed (Sales Order <strong>{{ o.order_number }}</strong>).</p>\n"
		+ CONTACT
		+ "{% if o.order_notes %}<p><strong>Order notes:</strong> {{ o.order_notes }}</p>{% endif %}\n"
		+ SUMMARY
		+ "<p><a href=\"{{ frappe.utils.get_url_to_form('Sales Order', doc.name) }}\">Open in ERPNext</a></p>",
	),
	(
		"Order Shipped (Customer)",
		"Your Order #{{ doc.name }} Has Been Shipped",
		"Method",
		"",
		"Customer",
		"Your order is on its way",
		HI
		+ "<p>Your order has been dispatched.</p>\n<p><strong>Dispatch date:</strong> {{ o.dispatch_date or o.order_date }}"
		"{% if o.courier %}<br><strong>Courier:</strong> {{ o.courier }}{% endif %}"
		"{% if o.tracking_number %}<br><strong>Tracking number:</strong> {{ o.tracking_number }}{% endif %}"
		"{% if o.delivery_date %}<br><strong>Expected delivery:</strong> {{ o.delivery_date }}{% endif %}</p>\n"
		'{% if o.tracking_url %}{% set cta_url = o.tracking_url %}{% set cta_label = "Track Your Order" %}'
		+ INC
		+ 'button.html" %}{% endif %}\n'
		"<p><strong>Amount to Pay on Delivery: {{ o.cod_amount }}</strong></p>\n" + SUMMARY + BUTTON,
	),
	(
		"Order Delivered (Customer)",
		"Your Order #{{ doc.name }} Has Been Delivered",
		"Method",
		"",
		"Customer",
		"Your order has been delivered",
		HI
		+ "<p>Your order has been delivered. We hope you enjoy your purchase.</p>\n"
		+ INC
		+ 'order_status.html" %}\n'
		+ INC
		+ 'order_items.html" %}\n'
		+ BUTTON,
	),
	(
		"Order Cancelled (Customer)",
		"Order #{{ doc.name }} Has Been Cancelled",
		"Cancel",
		"",
		"Customer",
		"Your order has been cancelled",
		HI
		+ "<p>Your order has been cancelled.</p>\n"
		+ CANCEL_INFO
		+ "<p>This was a Cash on Delivery order, so no payment was taken and no refund is required.</p>\n"
		+ INC
		+ 'order_status.html" %}\n'
		+ INC
		+ 'order_items.html" %}\n',
	),
	(
		"Order Cancelled by Customer (Admin)",
		"Order Cancellation – #{{ doc.name }}",  # noqa: RUF001
		"Cancel",
		'frappe.db.get_value("User", doc.modified_by, "user_type") == "Website User"',
		"Admin",
		"Order cancelled by customer",
		"<p>The customer has cancelled order <strong>{{ o.order_number }}</strong>.</p>\n"
		+ CONTACT
		+ CANCEL_INFO
		+ INC
		+ 'order_status.html" %}\n'
		+ INC
		+ 'order_items.html" %}\n',
	),
]

CUSTOM_FIELDS = {
	"Sales Order": [
		{
			"fieldname": "custom_payment_method",
			"label": "Payment Method",
			"fieldtype": "Data",
			"default": "Cash on Delivery",
			"read_only": 1,
			"insert_after": "status",
		},
		{
			"fieldname": "custom_notification_email",
			"label": "Customer Notification Email",
			"fieldtype": "Data",
			"options": "Email",
			"allow_on_submit": 1,
			"insert_after": "custom_payment_method",
			"description": "Where order emails are sent. Filled from the checkout email; fix it here if it is wrong.",
		},
		{
			"fieldname": "custom_cancellation_reason",
			"label": "Cancellation Reason",
			"fieldtype": "Small Text",
			"allow_on_submit": 1,
			"insert_after": "custom_notification_email",
		},
	],
	"Delivery Note": [
		{
			"fieldname": "custom_notification_email",
			"label": "Customer Notification Email",
			"fieldtype": "Data",
			"options": "Email",
			"read_only": 1,
			"insert_after": "po_no",
			"description": "Copied from the Sales Order; used by the shipping Notification.",
		},
		{
			"fieldname": "custom_tracking_url",
			"label": "Tracking URL",
			"fieldtype": "Data",
			"options": "URL",
			"insert_after": "lr_no",
		},
	],
}


PRINT_FORMAT = "Order Confirmation"
ATTACH_PRINT_TO = ("Order Confirmation (Customer)", "New Order (Admin)")


def after_migrate():
	create_custom_fields(CUSTOM_FIELDS, update=True)
	ensure_cod_mode_of_payment()
	ensure_print_format()
	for spec in NOTIFICATIONS:
		ensure_notification(*spec)
	attach_print_format()
	disable_legacy_notification()


def ensure_cod_mode_of_payment():
	if not frappe.db.exists("Mode of Payment", "Cash on Delivery"):
		frappe.get_doc(
			{"doctype": "Mode of Payment", "mode_of_payment": "Cash on Delivery", "type": "Cash"}
		).insert(ignore_permissions=True)


def ensure_notification(name, subject, event, condition, audience, heading, body):
	if frappe.db.exists("Notification", name):
		return
	account = frappe.db.get_value(
		"Email Account", {"default_outgoing": 1, "enable_outgoing": 1}, ["name", "email_id"], as_dict=True
	)
	recipient = {"receiver_by_document_field": CUSTOMER_FIELD} if audience == "Customer" else {"cc": ADMIN_CC}
	frappe.get_doc(
		{
			"doctype": "Notification",
			"name": name,
			"enabled": 1,
			"channel": "Email",
			"document_type": "Sales Order",
			"event": event,
			"method": METHODS.get(name),
			"condition_type": "Python",
			"condition": condition,
			"subject": subject,
			"message_type": "HTML",
			"message": _message(heading, body),
			"sender": account.name if account else None,
			"sender_email": account.email_id if account else None,
			"recipients": [recipient],
		}
	).insert(ignore_permissions=True)


def disable_legacy_notification():
	"""The pre-existing empty 'Order email' Notification (Sales Order Submit) would duplicate the new ones."""
	if frappe.db.exists("Notification", "Order email"):
		frappe.db.set_value("Notification", "Order email", "enabled", 0)


def ensure_print_format():
	"""Sales Order print format (Jinja). The file is only the starting point: it is copied once, so admins can edit it in the UI."""
	if frappe.db.exists("Print Format", PRINT_FORMAT):
		return
	html = frappe.get_app_path("storekit", "templates", "print_formats", "sales_order_confirmation.html")
	with open(html) as f:
		frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": PRINT_FORMAT,
				"doc_type": "Sales Order",
				"module": "Selling",
				"print_format_type": "Jinja",
				"custom_format": 1,
				"standard": "No",
				"html": f.read(),
				"default_print_language": "en",
				"font_size": 11,
				"margin_top": 12,
				"margin_bottom": 14,
				"margin_left": 12,
				"margin_right": 12,
			}
		).insert(ignore_permissions=True)


def attach_print_format():
	"""Attach the PDF to the order-submitted emails. Only touches Notifications that have no print format yet."""
	for name in ATTACH_PRINT_TO:
		if frappe.db.exists("Notification", name) and not frappe.db.get_value(
			"Notification", name, "print_format"
		):
			frappe.db.set_value("Notification", name, {"attach_print": 1, "print_format": PRINT_FORMAT})
