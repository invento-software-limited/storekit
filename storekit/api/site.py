import frappe


@frappe.whitelist(allow_guest=True)
def submit_inquiry(name, email, company, enquiry_type, country, message):
	doc = frappe.get_doc(
		{
			"doctype": "Lead",
			"lead_name": name,
			"email_id": email,
			"company_name": company,
			"country": country,
		}
	)
	doc.insert(ignore_permissions=True)

	# Add note for enquiry type & message
	doc.add_comment("Comment", text=f"Type: {enquiry_type}\nMessage: {message}")
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


#: price_range labels shown in the filter dropdown, mapped to (price_start, price_end).
#: ProductQuery.check_filters only applies the price filter when price_end > 0, so
#: "Over £100" needs an explicit high ceiling rather than 0/unbounded.
PRICE_RANGE_MAP = {
	"under £25": (0, 25),
	"£25 - £50": (25, 50),
	"£50 - £100": (50, 100),
	"over £100": (100, 999_999_999),
}

#: stock labels shown in the filter dropdown, mapped to ProductQuery stock filter keys
STOCK_MAP = {
	"in stock": "in_stock",
	"out of stock": "on_backorder",
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

	price_start, price_end = PRICE_RANGE_MAP.get((price_range or "").lower().strip(), (0, 0))
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
				"image": item.image or "https://placehold.co/400x300",
				"description": item.description,
				"price": price,
				"price_formatted": f"£{price:,.2f}",
				"stock_code_formatted": f"Stock Code: {item.item_code}",
				"route": route,
				"custom_route": route,
			}
		)

	# Handle sort_by filter
	if sort_by:
		sort_key = sort_by.lower().strip()
		if sort_key in ["price: low to high", "price_low_high", "price_asc"]:
			products.sort(key=lambda x: x["price"])
		elif sort_key in ["price: high to low", "price_high_low", "price_desc"]:
			products.sort(key=lambda x: x["price"], reverse=True)
		elif sort_key in ["name: a to z", "name_a_z", "name_asc"]:
			products.sort(key=lambda x: (x["item_name"] or "").lower())
		elif sort_key in ["name: z to a", "name_z_a", "name_desc"]:
			products.sort(key=lambda x: (x["item_name"] or "").lower(), reverse=True)

	total_count = res.get("items_count", 0)
	total_pages = math.ceil(total_count / page_length) if total_count else 1

	return {
		"products": products,
		"total_pages": total_pages,
		"current_page": page,
		"total_products": total_count,
	}
