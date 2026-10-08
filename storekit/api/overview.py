"""Data for the StoreKit Overview page: one permission-aware round trip.

Web orders are submitted Sales Orders with order_type "Shopping Cart"; revenue is base_net_total
(company currency, excl. VAT and shipping). Period metrics use transaction_date; "as-at" metrics
(awaiting dispatch, open carts, pending approvals, catalog) ignore the period.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, getdate, nowdate

from storekit.api import overview_sections as sections
from storekit.api.overview_sections import web_order_filters

MAX_PERIOD_DAYS = 731
MAX_PAGE_LENGTH = 50
ORDER_FIELDS = [
	"name",
	"transaction_date",
	"base_net_total",
	"status",
	"per_delivered",
	"per_billed",
	"docstatus",
]


@frappe.whitelist()
def get_dashboard_data(company=None, from_date=None, to_date=None, start=0, page_length=10):
	f = parse_filters(company, from_date, to_date, start, page_length)
	require_read("Sales Order")

	orders = period_orders(f, f.from_date, f.to_date)
	previous = period_orders(f, f.prev_from, f.prev_to)
	buckets = Buckets(f.from_date, f.to_date)
	prev_buckets = Buckets(f.prev_from, f.prev_to)

	return {
		"filters": f,
		"currency": frappe.get_cached_value("Company", f.company, "default_currency"),
		"bucket_labels": buckets.labels,
		"prev_bucket_labels": align(prev_buckets.labels, len(buckets.labels)),
		"sales": sales_summary(orders, previous, buckets, prev_buckets),
		"last_order": last_web_order(f),
		"pipeline": sections.pipeline(f, orders),
		"dispatch": sections.awaiting_dispatch(f),
		"carts": sections.open_carts(f),
		"customers": sections.customers(f, buckets),
		"products": sections.products(f),
		"reviews": sections.reviews(f),
		"catalog": sections.catalog(),
	}


def parse_filters(company, from_date, to_date, start, page_length):
	"""Validate and normalise the request; defaults come from the server, not the browser."""
	company = company or frappe.defaults.get_user_default("company")
	if not company or not frappe.db.exists("Company", company):
		frappe.throw(_("Select a valid Company"))
	if not frappe.has_permission("Company", "read", company):
		frappe.throw(_("Not permitted to view {0}").format(company), frappe.PermissionError)

	to_date = getdate(to_date or nowdate())
	from_date = getdate(from_date or add_days(to_date, -29))
	days = date_diff(to_date, from_date) + 1
	if days < 1:
		frappe.throw(_("From Date must be on or before To Date"))
	if days > MAX_PERIOD_DAYS:
		frappe.throw(_("Choose a period of at most {0} days").format(MAX_PERIOD_DAYS))

	return frappe._dict(
		company=company,
		from_date=from_date,
		to_date=to_date,
		prev_to=add_days(from_date, -1),
		prev_from=add_days(from_date, -days),
		days=days,
		start=max(cint(start), 0),
		page_length=min(max(cint(page_length), 1), MAX_PAGE_LENGTH),
	)


def require_read(doctype):
	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("Not permitted to read {0}").format(_(doctype)), frappe.PermissionError)


def last_web_order(f):
	rows = frappe.get_list(
		"Sales Order",
		filters=web_order_filters(f, docstatus=1),
		fields=["name", "transaction_date"],
		order_by="transaction_date desc, creation desc",
		limit_page_length=1,
	)
	return rows[0] if rows else None


def period_orders(f, from_date, to_date):
	"""Submitted and cancelled web orders placed in the range (cancelled kept for the pipeline)."""
	return frappe.get_list(
		"Sales Order",
		filters=web_order_filters(
			f, docstatus=["in", [1, 2]], transaction_date=["between", [from_date, to_date]]
		),
		fields=ORDER_FIELDS,
		limit_page_length=0,
	)


def sales_summary(orders, previous, buckets, prev_buckets):
	current = SalesSeries(orders, buckets)
	before = SalesSeries(previous, prev_buckets)
	return {
		"revenue": current.revenue,
		"orders": current.count,
		"aov": current.aov,
		"prev_revenue": before.revenue,
		"prev_orders": before.count,
		"prev_aov": before.aov,
		"revenue_series": current.revenue_series,
		"orders_series": current.count_series,
		"aov_series": current.aov_series,
		# previous period aligned bucket-by-bucket, padded/cut to the current length
		"prev_revenue_series": align(before.revenue_series, len(buckets.labels)),
	}


class SalesSeries:
	"""Revenue/order totals and per-bucket series for submitted orders."""

	def __init__(self, orders, buckets):
		submitted = [o for o in orders if o.docstatus == 1]
		n = len(buckets.labels)
		self.revenue_series = [0.0] * n
		self.count_series = [0] * n
		for order in submitted:
			i = buckets.index(order.transaction_date)
			self.revenue_series[i] += flt(order.base_net_total)
			self.count_series[i] += 1
		self.revenue = flt(sum(self.revenue_series), 2)
		self.count = len(submitted)
		self.aov = flt(self.revenue / self.count, 2) if self.count else 0
		self.aov_series = [
			flt(r / c, 2) if c else 0 for r, c in zip(self.revenue_series, self.count_series, strict=True)
		]


def align(series, length):
	return (series + [0.0] * length)[:length]


class Buckets:
	"""Day buckets up to a month, weeks up to ~6 months, months beyond."""

	def __init__(self, from_date, to_date):
		self.from_date = getdate(from_date)
		days = date_diff(to_date, from_date) + 1
		self.step = "day" if days <= 31 else "week" if days <= 184 else "month"
		self.labels = [self.label(i) for i in range(self.index(to_date) + 1)]

	def index(self, date):
		date = getdate(date)
		if self.step == "day":
			return date_diff(date, self.from_date)
		if self.step == "week":
			return date_diff(date, self.from_date) // 7
		return (date.year - self.from_date.year) * 12 + date.month - self.from_date.month

	def label(self, i):
		if self.step == "month":
			month = self.from_date.month - 1 + i
			start = self.from_date.replace(
				year=self.from_date.year + month // 12, month=month % 12 + 1, day=1
			)
			return start.strftime("%b %y")
		start = add_days(self.from_date, i * (7 if self.step == "week" else 1))
		return getdate(start).strftime("%d %b")
