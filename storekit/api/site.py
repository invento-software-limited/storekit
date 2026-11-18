import frappe
from frappe.utils import fmt_money

from storekit.webshop_functions.cart import PRODUCT_IMAGE_PLACEHOLDER


@frappe.whitelist(allow_guest=True)
def submit_inquiry(name, email, company, enquiry_type, country, message):
	doc = frappe.get_doc(
		{
			"doctype": "Lead",
			"lead_name": name,
			"email_id": email,
			"company_name": company,
			# Lead.country links to Country; free text from the form may not match one
			"country": country if frappe.db.exists("Country", country) else None,
		}
	)
	doc.insert(ignore_permissions=True)

	# Add note for enquiry type & message
	doc.add_comment("Comment", text=f"Type: {enquiry_type}\nCountry: {country}\nMessage: {message}")
	return {"status": "success"}


@frappe.whitelist(allow_guest=True)
def subscribe_newsletter(email, first_name=None):
	email_group_name = "Newsletter"

	# 1. Create the Email Group if it doesn't exist yet
	if not frappe.db.exists("Email Group", email_group_name):
		group_doc = frappe.get_doc({"doctype": "Email Group", "title": email_group_name})
		group_doc.insert(ignore_permissions=True)

	# 2. Check if already subscribed
	if frappe.db.exists("Email Group Member", {"email_group": email_group_name, "email": email}):
		return {"status": "already_subscribed", "message": "You are already subscribed!"}

	# 3. Insert the new subscriber
	member_doc = frappe.get_doc(
		{"doctype": "Email Group Member", "email_group": email_group_name, "email": email, "unsubscribed": 0}
	)
	member_doc.insert(ignore_permissions=True)

	return {"status": "success", "message": "Thank you for subscribing!"}


#: Price filter bands (price_start, price_end) in the site currency. None marks the open top band.
PRICE_BANDS = [(0, 5_000), (5_000, 20_000), (20_000, 50_000), (50_000, None)]

#: ProductQuery.check_filters only applies the price filter when price_end > 0, so
#: the open top band needs an explicit high ceiling rather than 0/unbounded.
OPEN_PRICE_CEILING = 999_999_999


def get_price_ranges():
	"""Price filter options labelled in the site currency, e.g. "Under ৳ 5,000", mapped to their bounds."""
	currency = frappe.db.get_single_value("Global Defaults", "default_currency")

	def money(amount):
		return fmt_money(amount, currency=currency, precision=0)

	ranges = {}
	for start, end in PRICE_BANDS:
		if not start:
			label = f"Under {money(end)}"
		elif end is None:
			label = f"Over {money(start)}"
		else:
			label = f"{money(start)} - {money(end)}"
		ranges[label] = (start, end or OPEN_PRICE_CEILING)
	return ranges


#: stock labels shown in the filter dropdown, mapped to ProductQuery stock filter keys
STOCK_MAP = {
	"in stock": "in_stock",
	"out of stock": "on_backorder",
	"on sale": "on_sale",
}
SORT_MAP = {
	"price: low to high": "price_asc",
	"price_low_high": "price_asc",
	"price_asc": "price_asc",
	"price: high to low": "price_desc",
	"price_high_low": "price_desc",
	"price_desc": "price_desc",
	"name: a to z": "name_asc",
	"name_a_z": "name_asc",
	"name_asc": "name_asc",
	"name: z to a": "name_desc",
	"name_z_a": "name_desc",
	"name_desc": "name_desc",
}


@frappe.whitelist(allow_guest=True)
def get_products(
	page: int = 1,
	page_length: int = 20,
	search: str | None = None,
	category: str | None = None,
	sort_by: str | None = None,
	price_range: str | None = None,
	stock: str | None = None,
):
	import math

	from storekit.webshop_functions.items import ProductQuery

	try:
		page = int(page)
		page_length = int(page_length)
	except ValueError:
		page = 1
		page_length = 20

	start = (page - 1) * page_length

	price_ranges = get_price_ranges()
	price_range_map = {label.lower(): bounds for label, bounds in price_ranges.items()}
	price_start, price_end = price_range_map.get((price_range or "").lower().strip(), (0, 0))
	currency = frappe.db.get_single_value("Global Defaults", "default_currency")
	stock_filters = []
	stock_key = STOCK_MAP.get((stock or "").lower().strip())
	if stock_key:
		stock_filters.append(stock_key)

	pq = ProductQuery()
	try:
		res = pq.query(
			filters={
				"page_length": page_length,
				"price_start": price_start,
				"price_end": price_end,
				"stock": stock_filters,
				# sorted before paging, so page 2 continues the order of page 1
				"sort": SORT_MAP.get((sort_by or "").lower().strip()),
			},
			search_term=search,
			start=start,
			item_group=category,
		)
	except Exception as e:
		frappe.log_error(message=f"ProductQuery failed: {e}", title="get_products")
		return {"error": True, "message": "Failed to fetch products. Please try again."}

	items = res.get("items", [])

	products = []
	for item in items:
		price = item.get("price_list_rate") or 0.0
		route = item.get("custom_route") or (f"/shop/{item.item_code}" if item.item_code else "#")
		products.append(
			{
				"item_code": item.item_code,
				"item_name": item.item_name,
				"image": item.image or PRODUCT_IMAGE_PLACEHOLDER,
				"description": item.description,
				"price": price,
				"price_formatted": fmt_money(price, currency=currency),
				"stock_code_formatted": f"Stock Code: {item.item_code}",
				"route": route,
				"custom_route": route,
				# product cards link templates to the variant picker instead of adding them
				"has_variants": item.get("has_variants"),
				"no_variants": not item.get("has_variants"),
			}
		)

	total_count = res.get("items_count", 0)
	total_pages = math.ceil(total_count / page_length) if total_count else 1

	return {
		"products": products,
		"total_pages": total_pages,
		"current_page": page,
		"total_products": total_count,
		# Labels the products page can show in its price filter dropdown.
		"price_ranges": [{"label": label} for label in price_ranges],
	}
