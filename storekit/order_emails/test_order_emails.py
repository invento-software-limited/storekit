import frappe
from frappe.tests import IntegrationTestCase

from storekit.order_emails.setup import NOTIFICATIONS


class TestOrderEmails(IntegrationTestCase):
	def test_every_notification_exists_on_sales_order(self):
		for spec in NOTIFICATIONS:
			doc = frappe.get_doc("Notification", spec[0])
			self.assertEqual(doc.document_type, "Sales Order")
			self.assertEqual(doc.event, spec[2])

	def test_shipped_and_delivered_use_method_events(self):
		self.assertEqual(
			frappe.db.get_value("Notification", "Order Shipped (Customer)", "method"), "order_shipped"
		)
		self.assertEqual(
			frappe.db.get_value("Notification", "Order Delivered (Customer)", "method"), "order_completed"
		)

	def test_no_custom_stage_field(self):
		self.assertFalse(frappe.get_meta("Sales Order").has_field("custom_order_stage"))

	def test_layout_renders_with_context(self):
		ctx = {
			"o": frappe._dict(
				company_name="Acme",
				lines=[],
				support_email="",
				support_phone="",
				company_address="",
				brand_color="#000",
			),
			"heading": "Hello",
		}
		html = frappe.render_template("storekit/templates/emails/order_layout.html", ctx)
		self.assertIn("Hello", html)
		self.assertIn("viewport", html)
