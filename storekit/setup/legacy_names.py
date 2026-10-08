"""Rename rules for code and records inherited from the invento_webshop and hopkins apps.

Pure string rules (no frappe import) so the same table rewrites source files and DB records.
"""

import re

LEGACY_APPS = ("invento_webshop", "hopkins")
LEGACY_MODULES = ("Invento Webshop", "Hopkins")
APP = "storekit"
MODULE = "StoreKit"

# Order matters: the specific paths go before the generic app-prefix rules.
RULES = [
	(re.compile(r"\binvento_webshop\.invento_webshop\."), "storekit.storekit."),
	(re.compile(r"\bhopkins\.hopkins\."), "storekit.storekit."),
	(re.compile(r"\bhopkins\.api\."), "storekit.api.site."),
	(re.compile(r"/assets/(?:invento_webshop|hopkins)/"), "/assets/storekit/"),
	(re.compile(r"\b(?:invento_webshop|hopkins)/templates/"), "storekit/templates/"),
	(re.compile(r"\binvento_webshop\.(?=[a-z_])"), "storekit."),
	(re.compile(r"\bhopkins\.(?=(?:order_emails|templates|patches|setup)\b)"), "storekit."),
	(re.compile(r"""(["'])(?:invento_webshop|hopkins)\1"""), r"\1storekit\1"),
	(re.compile(r"""("module":\s*)"(?:Invento Webshop|Hopkins)\""""), r'\1"StoreKit"'),
]


def rewrite(text: str) -> str:
	"""Return text with every legacy app path/name pointed at storekit."""
	for pattern, replacement in RULES:
		text = pattern.sub(replacement, text)
	return text


def has_legacy_reference(text: str) -> bool:
	return bool(text) and any(app in text for app in LEGACY_APPS)
