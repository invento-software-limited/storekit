from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

from storekit.api.often_purchased import OftenPurchased, get_often_purchased_section


def make_item(code, price=10.0):
	return frappe._dict(item_code=code, item_name=code, image=None, route=f"/shop/{code}", price_list_rate=price)


def make_query(items):
	query = MagicMock(fields=["item_code"])
	query._build_filters.return_value = []
	query.get_item_details.side_effect = lambda item: item
	query.items = items
	return query


class TestOftenPurchased(IntegrationTestCase):
	def build(self, items, manual=(), history=()):
		section = OftenPurchased("MAIN", make_query(items))
		section.get_manual_picks = lambda: list(manual)
		section.get_order_history = lambda: list(history)
		section.fetch_items = lambda codes: [item for item in items if item.item_code in codes]
		return section

	def test_manual_picks_come_before_order_history_without_duplicates(self):
		section = self.build([], manual=["A", "B"], history=["B", "C"])
		self.assertEqual(section.get_candidates(), ["A", "B", "C"])

	def test_item_never_recommends_itself(self):
		section = self.build([], manual=["MAIN", "A"])
		self.assertEqual(section.get_candidates(), ["A"])

	def test_section_lists_main_item_first_and_totals_all_rows(self):
		items = [make_item("MAIN", 10), make_item("A", 2.5)]
		result = self.build(items, manual=["A"]).get_section()
		self.assertEqual([row["item_code"] for row in result["items"]], ["MAIN", "A"])
		self.assertEqual(result["items"][0]["display_name"], "This item: MAIN")
		self.assertEqual(result["total"], "£12.50")

	def test_unpriced_recommendation_is_dropped(self):
		items = [make_item("MAIN"), make_item("FREE", 0), make_item("A")]
		result = self.build(items, manual=["FREE", "A"]).get_section()
		self.assertEqual([row["item_code"] for row in result["items"]], ["MAIN", "A"])

	def test_recommendations_are_capped(self):
		codes = ["A", "B", "C", "D", "E"]
		items = [make_item("MAIN"), *[make_item(code) for code in codes]]
		result = self.build(items, manual=codes).get_section()
		self.assertEqual(len(result["items"]), 1 + OftenPurchased.MAX_OTHERS)

	def test_section_is_empty_without_recommendations(self):
		self.assertEqual(self.build([make_item("MAIN")]).get_section(), {})

	def test_section_is_empty_when_main_item_cannot_be_sold(self):
		items = [make_item("MAIN", 0), make_item("A")]
		self.assertEqual(self.build(items, manual=["A"]).get_section(), {})

	def test_failure_returns_empty_section_instead_of_raising(self):
		with patch.object(OftenPurchased, "get_section", side_effect=ValueError), patch("frappe.log_error"):
			self.assertEqual(get_often_purchased_section("MAIN", MagicMock()), {})
