### StoreKit

Frappe/ERPNext ecommerce storefront built on Frappe Builder: catalog, cart, checkout, payments, order emails and Builder pages.

StoreKit merges the former `invento_webshop` (generic webshop engine) and `hopkins` (Hopkins site, order emails) apps.

### Layout

| Path | What |
|---|---|
| `storekit/storekit/doctype/` | Webshop Settings/Theme, payments (Lloyds Connect, Payment Gateway), Google Business reviews, downloads, FAQ, case studies, testimonials |
| `storekit/api/`, `storekit/webshop_functions/` | Whitelisted storefront APIs (items, cart, checkout, address, payments); `api/site.py` holds the site enquiry/newsletter/products APIs |
| `storekit/order_emails/` | Order Notifications, email templates, COD-only `place_order` and `cancel_order` overrides |
| `storekit/builder_files/`, `storekit/fixtures/` | Builder pages, components, client scripts, themes, settings |
| `storekit/setup/legacy_*.py` | One-off migration from the legacy apps (runs `after_install`) plus aliases for old `invento_webshop.*` / `hopkins.*` API paths |

### Installation

```bash
bench get-app $URL_OF_THIS_REPO --branch develop
bench --site <site> install-app storekit
```

Requires `erpnext` and `builder`.

#### Migrating a site that runs invento_webshop / hopkins

```bash
bench --site <site> backup --with-files
bench --site <site> install-app storekit          # moves DocTypes, Builder records and stored method paths to storekit
bench --site <site> remove-from-installed-apps invento_webshop
bench --site <site> remove-from-installed-apps hopkins
bench --site <site> execute storekit.setup.legacy_migration.drop_legacy_records
bench --site <site> migrate
```

Do not `uninstall-app` the legacy apps: that drops the DocType tables StoreKit now owns. Restart the web/worker processes after installing so the new package is importable.

### License

mit
