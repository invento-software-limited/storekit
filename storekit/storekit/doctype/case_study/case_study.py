# Copyright (c) 2026, Invento Software Limited and contributors
# For license information, please see license.txt

import re

import frappe
from frappe.model.document import Document


def slugify(text):
	if not text:
		return ""
	# Lowercase
	slug = text.lower()
	# Remove non-alphanumeric, spaces, dashes
	slug = re.sub(r"[^\w\s-]", "", slug)
	# Replace spaces and underscores with a single dash
	slug = re.sub(r"[\s_]+", "-", slug)
	# Replace multiple consecutive dashes with a single dash
	slug = re.sub(r"-+", "-", slug)
	# Strip leading/trailing dashes
	return slug.strip("-")


class CaseStudy(Document):
	def validate(self):
		if self.title:
			self.route = slugify(self.title)

	def make_route(self):
		if self.title:
			return slugify(self.title)
		return ""

	def get_context(self, context):
		context.metatags = {
			"title": self.meta_title or self.title,
			"description": self.meta_description or self.short_description,
			"image": self.meta_image or self.image,
		}
