import frappe
from frappe.utils import flt

from storekit.webshop_functions.cart import PRODUCT_IMAGE_PLACEHOLDER


def get_often_purchased_section(item_code, product_query):
	"""Upsell data for a product page. An upsell failure must never take the page down."""
	try:
		return OftenPurchased(item_code, product_query).get_section()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Often Purchased Section Error")
		return {}


class OftenPurchased:
	MAX_OTHERS = 3
	MIN_SHARED_ORDERS = 2

	def __init__(self, item_code, product_query):
		self.item_code = item_code
		self.product_query = product_query

	def get_section(self):
		main = self.get_rows([self.item_code])
		others = self.get_rows(self.get_candidates())[: self.MAX_OTHERS]
		if not main or not others:
			return {}

		main[0]["display_name"] = f"This item: {main[0]['item_name']}"
		rows = main + others
		return {"items": rows, "total": format_price(sum(row["price"] for row in rows))}

	def get_candidates(self):
		"""Hand-picked items first, then what customers really bought alongside this one."""
		codes = self.get_manual_picks() + self.get_order_history()
		return [code for code in dict.fromkeys(codes) if code != self.item_code]

	def get_manual_picks(self):
		return frappe.get_all(
			"Often Purchased Item",
			filters={"parent": self.item_code, "parenttype": "Item"},
			pluck="item",
			order_by="idx asc",
		)

	def get_order_history(self):
		# One shared order is coincidence (or a test order), so it doesn't count.
		return frappe.db.sql(
			"""
			select other.item_code
			from `tabSales Order Item` this
			join `tabSales Order Item` other on other.parent = this.parent
			where this.item_code = %(item)s and other.item_code != %(item)s and this.docstatus = 1
			group by other.item_code
			having count(distinct other.parent) >= %(min_orders)s
			order by count(distinct other.parent) desc
			limit 20
			""",
			{"item": self.item_code, "min_orders": self.MIN_SHARED_ORDERS},
			pluck=True,
		)

	def get_rows(self, codes):
		"""Only published, directly addable, priced items: a £0 upsell can't be sold."""
		if not codes:
			return []

		rows = {row.item_code: row for row in self.fetch_items(codes)}
		priced = (self.product_query.get_item_details(rows[code]) for code in codes if code in rows)
		return [to_row(item) for item in priced if flt(item.price_list_rate) > 0]

	def fetch_items(self, codes):
		return frappe.get_all(
			"Item",
			fields=self.product_query.fields,
			filters=[
				*self.product_query._build_filters({}, None),
				["name", "in", codes],
				["has_variants", "=", 0],
			],
			ignore_permissions=True,
		)


def to_row(item):
	price = flt(item.price_list_rate)
	return {
		"item_code": item.item_code,
		"item_name": item.item_name,
		"display_name": item.item_name,
		"image": item.image or PRODUCT_IMAGE_PLACEHOLDER,
		"route": item.route,
		"price": price,
		"price_formatted": format_price(price),
	}


def format_price(amount):
	return f"£{amount:,.2f}"
