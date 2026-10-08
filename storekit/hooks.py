from storekit.setup.legacy_aliases import LEGACY_METHOD_ALIASES

app_name = "storekit"
app_title = "StoreKit"
app_publisher = "Invento Software Limited"
app_description = "Generic Frappe ecommerce storefront: catalog, cart, checkout, orders and Builder pages"
app_email = "hello@invento.com.bd"
app_license = "mit"

required_apps = ["erpnext", "builder"]

# Includes in <head>
# ------------------

doctype_js = {"Customer": "public/js/customer.js"}
doctype_list_js = {"Item": "public/js/item_list.js"}

# Jinja
# ----------

jinja = {"methods": ["storekit.order_emails.jinja_methods.order_email_context"]}

# Installation
# ------------

after_install = "storekit.setup.legacy_migration.execute"
after_migrate = ["storekit.order_emails.setup.after_migrate"]

# DocType Class
# ---------------

override_doctype_class = {
	"Item": "storekit.hook_functions.item.CustomItem",
	"Shipping Rule": "storekit.hook_functions.shipping_rule.CustomShippingRule",
	"Builder Page": "storekit.hook_functions.builder_page.CustomBuilderPage",
}

# Document Events
# ---------------

doc_events = {
	"Website Download": {
		"before_save": "storekit.api.website_download.update_file_details",
	},
	"Shipping Rule": {
		"before_save": "storekit.api.shipping.validate_default_rule",
	},
	"Sales Order": {
		"validate": "storekit.order_emails.events.fill_notification_email",
	},
	"Delivery Note": {
		"validate": "storekit.order_emails.events.fill_notification_email",
		"before_submit": "storekit.order_emails.events.remember_order_status",
		"on_submit": "storekit.order_emails.events.after_delivery_note_submit",
	},
	"Sales Invoice": {
		"before_submit": "storekit.order_emails.events.remember_order_status",
		"on_submit": "storekit.order_emails.events.after_invoice_submit",
	},
	"Email Queue": {
		"before_insert": "storekit.order_emails.events.render_print_attachments",
		"after_insert": "storekit.order_emails.events.send_queued_now",
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"storekit.google_business.google_reviews.sync_all_enabled_accounts",
	],
}

# Overriding Methods
# ------------------------------

# Checkout is Cash on Delivery only and order cancellation sends the order emails.
_ORDER_OVERRIDES = {
	"storekit.webshop_functions.cart.place_order": "storekit.order_emails.api.place_order",
	"storekit.webshop_functions.order.order.cancel_order": "storekit.order_emails.api.cancel_order",
	"invento_webshop.webshop_functions.cart.place_order": "storekit.order_emails.api.place_order",
	"invento_webshop.webshop_functions.order.order.cancel_order": "storekit.order_emails.api.cancel_order",
}

override_whitelisted_methods = {**LEGACY_METHOD_ALIASES, **_ORDER_OVERRIDES}

# Fixtures
# --------

WEBSHOP_THEMES = [
	"Midnight Black", "Charcoal Slate", "Royal Blue", "Sky Blue", "Ocean Teal",
	"Emerald", "Forest Green", "Crimson Red", "Sunset Orange", "Amber Honey",
	"Fuchsia Pink", "Deep Violet", "Pure Black", "Carbon", "Gunmetal", "Navy Amber",
]  # fmt: skip

fixtures = [
	"Builder Settings",
	"Builder Project Folder",
	"Builder Token",
	"Builder Client Script",
	"Builder Component",
	"Builder Page",
	"User Font",
	{"doctype": "Webshop Theme", "filters": [["name", "in", WEBSHOP_THEMES]]},
	"Webshop Settings",
]
