import frappe
from frappe.utils import flt, fmt_money

#: Rule label markers. A COLLECTION rule (customer collects) is offered for any cart. A DIGITAL
#: rule (nothing to ship) is the only rule offered for a cart with no physical item in it.
COLLECTION_MARK = "COLLECTION"
DIGITAL_MARK = "DIGITAL"


@frappe.whitelist(allow_guest=True)
def get_shipping_methods(postcode=None):
	if not postcode:
		return []

	return get_methods_for_cart(get_cart_values(), postcode)


def get_methods_for_cart(cart, postcode=None):
	"""
	Shipping methods for a cart, the cart's default first.

	Args:
	    cart (dict): net_total, total_weight and is_physical (see get_items_values()).
	    postcode (str | None): Delivery postcode. Without one, postcode-specific rules are skipped.

	Returns:
	    list[dict]: name, label, cost and cost_display of each method.
	"""
	postcode = (postcode or "").upper().replace(" ", "")

	all_rules = frappe.get_all(
		"Shipping Rule",
		filters={"disabled": 0, "shipping_rule_type": "Selling", "custom_publish_to_website": 1},
		fields=[
			"name",
			"label",
			"shipping_amount",
			"custom_is_postcode_specific",
			"custom_postcode_prefixes",
			"custom_is_weight_stepped",
			"custom_is_default",
		],
	)

	net_total = cart.get("net_total", 0)
	total_weight = cart.get("total_weight", 0)
	currency = frappe.db.get_single_value("Global Defaults", "default_currency")

	matched_specific_rules = []
	standard_rules = []
	collection_rule = None
	digital_rule = None

	for rule in all_rules:
		label = rule.label.upper()
		if DIGITAL_MARK in label:
			digital_rule = digital_rule or rule
			continue

		if COLLECTION_MARK in label:
			collection_rule = rule
			continue

		if rule.custom_is_postcode_specific:
			prefixes = [p.strip() for p in (rule.custom_postcode_prefixes or "").split(",") if p.strip()]
			if postcode and any(postcode.startswith(p) for p in prefixes):
				matched_specific_rules.append(rule)
		else:
			standard_rules.append(rule)

	available_rules = []
	if digital_rule and not cart.get("is_physical"):
		# Nothing to deliver: no delivery charge.
		available_rules = [frappe.get_doc("Shipping Rule", digital_rule.name)]
	else:
		if matched_specific_rules:
			available_rules = [frappe.get_doc("Shipping Rule", r.name) for r in matched_specific_rules]
		else:
			# Standard rules already have custom_is_default from get_all
			# Sort to bring default rule to the top
			standard_rules.sort(key=lambda x: 0 if x.custom_is_default else 1)
			available_rules = [frappe.get_doc("Shipping Rule", r.name) for r in standard_rules]

		if collection_rule:
			available_rules.append(frappe.get_doc("Shipping Rule", collection_rule.name))

	methods = []
	for rule in available_rules:
		cost = calculate_cost(rule, net_total, total_weight)
		methods.append(
			{
				"name": rule.name,
				"label": rule.label,
				"cost": cost,
				"cost_display": fmt_money(cost, currency=currency),
			}
		)

	return methods


def validate_default_rule(doc, method):
	if doc.custom_is_default:
		# Uncheck other default rules
		frappe.db.sql(
			"""
            update `tabShipping Rule`
            set custom_is_default = 0
            where name != %s and custom_is_default = 1
        """,
			(doc.name,),
		)


def calculate_cost(rule, net_total, total_weight):
	if rule.calculate_based_on == "Fixed":
		return flt(rule.shipping_amount)

	value_to_check = flt(net_total) if rule.calculate_based_on == "Net Total" else flt(total_weight)

	applied_cost = 0
	found = False
	last_valid_amount = 0
	last_max_value = 0

	conditions = sorted(rule.get("conditions") or [], key=lambda x: flt(x.from_value))

	for condition in conditions:
		from_val = flt(condition.from_value)
		to_val = flt(condition.to_value)
		amount = flt(condition.shipping_amount)

		if from_val <= value_to_check and (value_to_check <= to_val or to_val == 0):
			applied_cost = amount
			found = True
			break

		if to_val > last_max_value:
			last_max_value = to_val
			last_valid_amount = amount

	if not found:
		if (
			rule.calculate_based_on == "Net Weight"
			and rule.custom_is_weight_stepped
			and value_to_check > last_max_value
		):
			excess_weight = value_to_check - last_max_value
			applied_cost = last_valid_amount + (excess_weight * flt(rule.custom_excess_weight_rate))
		else:
			applied_cost = last_valid_amount

	return applied_cost


def get_cart_values(quotation=None):
	"""Net total, total weight and is_physical of a cart Quotation (default: the session's cart)."""
	if not quotation:
		from storekit.webshop_functions.cart import _get_cart_quotation

		quotation = _get_cart_quotation()

	values = get_items_values([(item.item_code, item.qty) for item in quotation.items])
	values["net_total"] = flt(quotation.total)
	return values


def get_items_values(items):
	"""
	Total weight of (item_code, qty) pairs, and whether any of them is physical.

	An item is physical when it is a stock item or has a weight. A cart of only
	licences, services and hosting has nothing to deliver.
	"""
	total_weight = 0
	is_physical = False
	for item_code, qty in items:
		weight, is_stock_item = frappe.db.get_value(
			"Item", item_code, ["weight_per_unit", "is_stock_item"]
		) or (0, 0)
		total_weight += flt(weight) * flt(qty)
		is_physical = is_physical or bool(is_stock_item) or flt(weight) > 0

	return {"total_weight": total_weight, "is_physical": is_physical}


@frappe.whitelist(allow_guest=True)
def update_order_with_shipping(shipping_rule):
	from frappe.utils import flt, fmt_money

	from storekit.webshop_functions.cart import _get_cart_quotation, calculate_taxes_and_totals

	quotation = _get_cart_quotation()
	quotation.shipping_rule = shipping_rule

	# --- Clear existing shipping rows first ---
	shipping_rule_label = frappe.db.get_value("Shipping Rule", shipping_rule, "label")
	new_taxes = []
	for tax in quotation.get("taxes", []):
		# Keep only non-shipping taxes
		if tax.description not in [shipping_rule_label, f"VAT on {shipping_rule_label}"]:
			new_taxes.append(tax)
	quotation.set("taxes", new_taxes)

	# Trigger unified tax/shipping refresh
	calculate_taxes_and_totals(quotation=quotation)

	# Calculate actual shipping amount (Cost + VAT on Cost) from the taxes table
	shipping_amount = 0
	for tax in quotation.get("taxes", []):
		if tax.description in [shipping_rule_label, f"VAT on {shipping_rule_label}"]:
			shipping_amount += flt(tax.tax_amount)

	currency = frappe.db.get_single_value("Global Defaults", "default_currency")
	return {
		"shipping_amount": fmt_money(shipping_amount, currency=currency),
		"grand_total": fmt_money(quotation.grand_total, currency=currency),
	}
