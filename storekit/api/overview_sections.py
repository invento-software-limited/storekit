"""Section builders for storekit.api.overview. Every query goes through frappe.get_list."""

import frappe
from frappe.utils import add_to_date, date_diff, flt, getdate, now_datetime, nowdate

WEB_ORDER = {"order_type": "Shopping Cart"}
OPEN_ORDER_STATUSES = ["To Deliver and Bill", "To Deliver"]
ABANDONED_AFTER_HOURS = 24
WORKLIST_LIMIT = 10
TOP_PRODUCTS = 10
TOP_GROUPS = 5


def web_order_filters(f, **extra):
	return {"company": f.company, **WEB_ORDER, **extra}


def can_read(doctype):
	return bool(frappe.has_permission(doctype, "read"))


# ---------------- order pipeline (orders placed in the period, by current stage) ----------------

STAGES = ["cart", "ordered", "part_dispatched", "to_bill", "completed"]


def pipeline(f, orders):
	stages = {key: {"count": 0, "value": 0.0} for key in [*STAGES, "closed", "on_hold", "cancelled"]}
	for order in orders:
		_add(stages[order_stage(order)], order.base_net_total)
	for cart in cart_rows(f, created_between=(f.from_date, f.to_date)):
		_add(stages["cart"], cart.base_net_total)
	return stages


def order_stage(order):
	"""One stage per order, from docstatus, status and delivered %."""
	if order.docstatus == 2:
		return "cancelled"
	if order.status in ("Closed", "On Hold", "Completed"):
		return {"Closed": "closed", "On Hold": "on_hold", "Completed": "completed"}[order.status]
	if order.status == "To Bill":
		return "to_bill"
	return "part_dispatched" if flt(order.per_delivered) > 0 else "ordered"


def _add(bucket, value):
	bucket["count"] += 1
	bucket["value"] = flt(bucket["value"] + flt(value), 2)


# ---------------- awaiting dispatch (as-at today) ----------------

DISPATCH_AGES = [("0–2 days", 0, 2), ("3–7 days", 3, 7), ("8+ days", 8, None)]


def awaiting_dispatch(f):
	filters = web_order_filters(f, docstatus=1, status=["in", OPEN_ORDER_STATUSES], per_delivered=["<", 100])
	rows = frappe.get_list(
		"Sales Order", filters=filters, fields=["transaction_date", "base_net_total"], limit_page_length=0
	)
	today = getdate(nowdate())
	ages = [{"label": label, "count": 0} for label, _, _ in DISPATCH_AGES]
	for row in rows:
		ages[_age_bucket(date_diff(today, row.transaction_date))]["count"] += 1
	return {
		"count": len(rows),
		"value": flt(sum(flt(r.base_net_total) for r in rows), 2),
		"ages": ages,
		"rows": dispatch_rows(filters, f),
	}


def _age_bucket(days):
	for i, (_, low, high) in enumerate(DISPATCH_AGES):
		if days >= low and (high is None or days <= high):
			return i
	return 0


def dispatch_rows(filters, f):
	rows = frappe.get_list(
		"Sales Order",
		filters=filters,
		fields=["name", "customer", "customer_name", "transaction_date", "base_net_total", "total_qty", "per_delivered"],
		order_by="transaction_date asc, creation asc",
		limit_start=f.start,
		limit_page_length=f.page_length,
	)
	today = getdate(nowdate())
	for row in rows:
		row.age_days = date_diff(today, row.transaction_date)
	return rows


# ---------------- carts (draft Shopping Cart quotations with items) ----------------

CART_IDLE = [("Under 24h", 0, 24), ("1–7 days", 24, 168), ("7+ days", 168, None)]


def cart_rows(f, created_between=None):
	if not can_read("Quotation"):
		return []
	filters = {"company": f.company, **WEB_ORDER, "docstatus": 0, "base_net_total": [">", 0]}
	if created_between:
		filters["transaction_date"] = ["between", list(created_between)]
	return frappe.get_list(
		"Quotation",
		filters=filters,
		fields=["name", "party_name", "customer_name", "contact_email", "base_net_total", "total_qty", "modified"],
		order_by="base_net_total desc",
		limit_page_length=0,
	)


def open_carts(f):
	carts = cart_rows(f)
	now = now_datetime()
	idle = [{"label": label, "count": 0, "value": 0.0} for label, _, _ in CART_IDLE]
	abandoned = []
	for cart in carts:
		cart.idle_hours = (now - cart.modified).total_seconds() / 3600
		_add(idle[_idle_bucket(cart.idle_hours)], cart.base_net_total)
		if cart.idle_hours >= ABANDONED_AFTER_HOURS:
			abandoned.append(cart)
	return {
		"allowed": can_read("Quotation"),
		"count": len(carts),
		"value": flt(sum(flt(c.base_net_total) for c in carts), 2),
		"idle": idle,
		"abandoned_count": len(abandoned),
		"abandoned_value": flt(sum(flt(c.base_net_total) for c in abandoned), 2),
		"abandoned": abandoned[:WORKLIST_LIMIT],
	}


def _idle_bucket(hours):
	for i, (_, low, high) in enumerate(CART_IDLE):
		if hours >= low and (high is None or hours < high):
			return i
	return 0


# ---------------- customers ----------------


def customers(f, buckets):
	"""Customers created in the period, split by whether they have placed a web order yet."""
	if not can_read("Customer"):
		return {"allowed": False}
	new = frappe.get_list(
		"Customer",
		filters={"creation": ["between", [f.from_date, add_to_date(f.to_date, days=1)]], "disabled": 0},
		fields=["name", "customer_name", "email_id", "mobile_no", "creation"],
		order_by="creation desc",
		limit_page_length=0,
	)
	series = [0] * len(buckets.labels)
	for row in new:
		series[min(buckets.index(row.creation), len(series) - 1)] += 1
	ordered = customers_with_orders(f, [c.name for c in new])
	waiting = [c for c in new if c.name not in ordered]
	return {
		"allowed": True,
		"new": len(new),
		"ordered": len(new) - len(waiting),
		"series": series,
		"no_order_count": len(waiting),
		"no_order": waiting[:WORKLIST_LIMIT],
	}


def customers_with_orders(f, names):
	if not names:
		return set()
	return set(
		frappe.get_list(
			"Sales Order",
			filters=web_order_filters(f, docstatus=1, customer=["in", names]),
			pluck="customer",
			limit_page_length=0,
		)
	)


# ---------------- products and item groups (period orders) ----------------


def products(f):
	lines = frappe.get_list(
		"Sales Order",
		filters=web_order_filters(f, docstatus=1, transaction_date=["between", [f.from_date, f.to_date]]),
		fields=["items.item_code", "items.item_name", "items.item_group", "items.base_net_amount", "items.stock_qty", "items.stock_uom"],
		limit_page_length=0,
	)
	items, groups = {}, {}
	for line in lines:
		item = items.setdefault(line.item_code, {"item_code": line.item_code, "item_name": line.item_name, "uom": line.stock_uom, "qty": 0.0, "revenue": 0.0})
		item["qty"] += flt(line.stock_qty)
		item["revenue"] += flt(line.base_net_amount)
		group = line.item_group or "Uncategorised"
		groups[group] = groups.get(group, 0.0) + flt(line.base_net_amount)
	ranked = sorted((i for i in items.values() if i["revenue"] > 0), key=lambda i: i["revenue"], reverse=True)
	return {"top": ranked[:TOP_PRODUCTS], "groups": top_groups(groups)}


def top_groups(groups):
	ranked = sorted(((name, value) for name, value in groups.items() if value > 0), key=lambda g: g[1], reverse=True)
	parts = [{"label": name, "value": flt(value, 2)} for name, value in ranked[:TOP_GROUPS]]
	other = sum(value for _, value in ranked[TOP_GROUPS:])
	if other:
		parts.append({"label": "Other", "value": flt(other, 2)})
	return parts


# ---------------- reviews (period) ----------------


def reviews(f):
	if not can_read("Customer Review"):
		return {"allowed": False}
	rows = frappe.get_list(
		"Customer Review",
		filters={"creation": ["between", [f.from_date, add_to_date(f.to_date, days=1)]]},
		fields=["name", "user", "item", "rating", "review", "creation"],
		order_by="rating asc, creation desc",
		limit_page_length=0,
	)
	stars = [0] * 5
	for row in rows:
		row.stars = min(max(round(flt(row.rating) * 5), 1), 5)
		stars[row.stars - 1] += 1
	average = flt(sum(r.stars for r in rows) / len(rows), 1) if rows else 0
	return {"allowed": True, "count": len(rows), "average": average, "stars": stars, "rows": rows[:WORKLIST_LIMIT]}


# ---------------- catalog health (as-at) ----------------


def catalog():
	if not can_read("Item"):
		return {"allowed": False}
	published = frappe.get_list(
		"Item",
		filters={"custom_publish_on_website": 1, "disabled": 0},
		fields=["name", "custom_on_sale", "custom_on_backorder"],
		limit_page_length=0,
	)
	priced = priced_items()
	return {
		"allowed": True,
		"published": len(published),
		"on_sale": sum(1 for i in published if i.custom_on_sale),
		"on_backorder": sum(1 for i in published if i.custom_on_backorder),
		"no_price": sum(1 for i in published if i.name not in priced) if priced is not None else None,
		"price_list": frappe.db.get_single_value("Selling Settings", "selling_price_list"),
	}


def priced_items():
	"""Items with a rate in the default selling price list (what the storefront shows)."""
	price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")
	if not price_list or not can_read("Item Price"):
		return None
	return set(
		frappe.get_list("Item Price", filters={"price_list": price_list, "selling": 1}, pluck="item_code", limit_page_length=0)
	)
