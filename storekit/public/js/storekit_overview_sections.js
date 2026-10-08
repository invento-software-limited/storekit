// Panel and worklist renderers for the StoreKit Overview page. Each returns an HTML string.
window.storekit_overview_sections = (() => {
	const esc = (v) => frappe.utils.escape_html(String(v ?? ""));
	const date = (v) => (v ? frappe.datetime.str_to_user(String(v).slice(0, 10)) : "");
	const doc = (doctype, name, label) => `<a class="lnk" data-doctype="${esc(doctype)}" data-doc="${esc(name)}">${esc(label || name)}</a>`;
	const empty = (text) => `<div class="empty">${esc(text)}</div>`;
	const GROUP_COLORS = ["#097C52", "#17626e", "#2f5a86", "#8a5a16", "#a3552f", "#5c6672"];
	const STAR_COLORS = ["#a3302f", "#a3552f", "#8a5a16", "#17626e", "#097C52"];

	function card(label, value, caption, visual, cls = "", color = "") {
		return `<div class="mx-c ${cls}"><div class="cd-k">${esc(label)}</div>
			<div class="mx-v"${color ? ` style="color:${color}"` : ""}>${value}</div>
			<div class="mx-s">${caption}</div><div class="mx-sp">${visual}</div></div>`;
	}

	function delta(now, before) {
		if (!before) return now ? `<span class="pill" style="background:#22405e">${__("New")}</span>` : "";
		const pct = ((now - before) / Math.abs(before)) * 100;
		const up = pct >= 0;
		return `<span class="pill" style="background:${up ? "#0a5a3c" : "#8a4527"}">${up ? "▲" : "▼"} ${Math.abs(pct).toFixed(0)}%</span>`;
	}

	function head(title, sub, sub_cls = "") {
		return `<div class="hrow"><div class="h">${esc(title)}</div><div class="hs ${sub_cls}">${esc(sub)}</div></div>`;
	}

	function trend_card() {
		return `<div class="surf card">${head(__("Revenue over time"), "", "trend-sub")}<div class="trend-ch"></div>
			<div class="lgd"><span><i style="background:#097C52"></i>${__("This period")}</span><span><i style="background:#a3552f;height:2px;vertical-align:3px"></i>${__("Previous period")}</span></div></div>`;
	}

	function products_card(d, fmt) {
		const top = d.products.top;
		const max = Math.max(...top.map((p) => p.revenue), 1);
		const rows = top.map((p) => `<div data-doctype="Item" data-doc="${esc(p.item_code)}" class="rk-r-wrap">
			<div class="rk-r"><i class="rk-d" style="background:#097C52"></i><span class="rk-n" title="${esc(p.item_name)}">${esc(p.item_name)}</span>
				<span class="rk-v">${fmt.full(p.revenue)}</span><span class="rk-q">${format_number(p.qty, null, 0)} ${esc(p.uom)}</span></div>
			<div class="rk-t"><div class="rk-f" style="width:${((p.revenue / max) * 100).toFixed(1)}%;background:#097C52"></div></div></div>`);
		return `<div class="surf card">${head(__("Top products"), __("By net revenue, top {0}", [top.length]))}
			${rows.length ? `<div class="rk">${rows.join("")}</div>` : empty(__("No product sales in this period"))}</div>`;
	}

	function groups_card(d, fmt) {
		const parts = d.products.groups.map((g, i) => ({ ...g, color: GROUP_COLORS[i % GROUP_COLORS.length] }));
		const total = parts.reduce((s, p) => s + p.value, 0);
		const chart = parts.length ? storekit_charts.donut(parts, { label: __("NET SALES"), value: fmt.compact(total) }, (v) => fmt.full(v)) : empty(__("No sales in this period"));
		return `<div class="surf card">${head(__("Sales by item group"), __("Share of net revenue"))}${chart}</div>`;
	}

	function dispatch_card(d, fmt) {
		const rows = d.dispatch.rows, f = d.filters;
		const age_color = (days) => (days <= 2 ? "#097C52" : days <= 7 ? "#8a5a16" : "#a3302f");
		const body = rows.map((r) => `<tr><td class="doc">${doc("Sales Order", r.name)}</td>
			<td>${doc("Customer", r.customer, r.customer_name)}</td><td>${date(r.transaction_date)}</td>
			<td style="color:${age_color(r.age_days)};font-weight:600">${__("{0} d", [r.age_days])}</td>
			<td class="n">${format_number(r.total_qty, null, 0)}</td><td class="n">${fmt.full(r.base_net_total)}</td></tr>`);
		const first = f.start + 1, last = f.start + rows.length;
		const pager = `<div class="pg"><span>${rows.length ? __("{0}–{1} of {2}", [first, last, d.dispatch.count]) : ""}</span>
			<button data-page="-1" ${f.start ? "" : "disabled"}>${__("Previous")}</button>
			<button data-page="1" ${last < d.dispatch.count ? "" : "disabled"}>${__("Next")}</button></div>`;
		return `<div class="surf card">${head(__("Orders to dispatch"), __("Oldest first · not yet fully delivered"))}
			${rows.length ? `<div class="tw"><table class="tb"><thead><tr><th>${__("Order")}</th><th>${__("Customer")}</th><th>${__("Ordered")}</th><th>${__("Age")}</th><th class="n">${__("Qty")}</th><th class="n">${__("Net value")}</th></tr></thead><tbody>${body.join("")}</tbody></table></div>${pager}` : empty(__("Nothing waiting to be dispatched"))}</div>`;
	}

	function carts_card(d, fmt) {
		const c = d.carts;
		if (!c.allowed) return `<div class="surf card">${head(__("Abandoned carts"), "")}${empty(__("No access to Quotations"))}</div>`;
		const idle = (h) => (h >= 48 ? __("{0} d", [Math.floor(h / 24)]) : __("{0} h", [Math.floor(h)]));
		const body = c.abandoned.map((r) => `<tr><td class="doc">${doc("Quotation", r.name)}</td>
			<td>${esc(r.customer_name || r.party_name)}<div style="font-size:10.5px;color:#98a1ac">${esc(r.contact_email || "")}</div></td>
			<td>${idle(r.idle_hours)}</td><td class="n">${fmt.full(r.base_net_total)}</td></tr>`);
		return `<div class="surf card">${head(__("Abandoned carts"), __("Idle over 24h · {0} worth {1}", [c.abandoned_count, fmt.full(c.abandoned_value)]))}
			${body.length ? `<div class="tw"><table class="tb"><thead><tr><th>${__("Cart")}</th><th>${__("Customer")}</th><th>${__("Idle")}</th><th class="n">${__("Value")}</th></tr></thead><tbody>${body.join("")}</tbody></table></div>` : empty(__("No abandoned carts"))}</div>`;
	}

	function customers_card(d) {
		const c = d.customers;
		if (!c.allowed) return `<div class="surf card">${head(__("New customers without an order"), "")}${empty(__("No access to Customers"))}</div>`;
		const body = c.no_order.map((r) => `<tr><td class="doc">${doc("Customer", r.name, r.customer_name)}</td>
			<td>${esc(r.email_id || r.mobile_no || "")}</td><td>${date(r.creation)}</td></tr>`);
		return `<div class="surf card">${head(__("New customers without an order"), __("{0} of {1} signed up this period", [c.no_order_count, c.new]))}
			${body.length ? `<div class="tw"><table class="tb"><thead><tr><th>${__("Customer")}</th><th>${__("Contact")}</th><th>${__("Signed up")}</th></tr></thead><tbody>${body.join("")}</tbody></table></div>` : empty(__("Every new customer has ordered"))}</div>`;
	}

	function reviews_card(d) {
		const r = d.reviews;
		if (!r.allowed) return `<div class="surf card">${head(__("Customer reviews"), "")}${empty(__("No access to Customer Reviews"))}</div>`;
		const hist = storekit_charts.histogram(r.stars.map((v, i) => ({ label: `${i + 1}★`, value: v })), STAR_COLORS);
		const rows = r.rows.slice(0, 5).map((x) => `<tr><td><span class="stars">${"★".repeat(x.stars)}${"☆".repeat(5 - x.stars)}</span></td>
			<td>${doc("Item", x.item)}</td><td class="wrap">${esc(x.review)}</td><td>${date(x.creation)}</td></tr>`);
		return `<div class="surf card">${head(__("Customer reviews"), r.count ? __("{0} reviews · average {1} ★", [r.count, r.average]) : __("No reviews this period"))}
			${r.count ? `${hist}<table class="tb" style="margin-top:10px"><tbody>${rows.join("")}</tbody></table>` : empty(__("No reviews this period"))}</div>`;
	}

	function catalog_card(d) {
		const c = d.catalog;
		if (!c.allowed) return `<div class="surf card">${head(__("Catalog health"), "")}${empty(__("No access to Items"))}</div>`;
		const pub = { custom_publish_on_website: 1, disabled: 0 };
		const stat = (label, value, sub, filters) => `<div class="stat-c"${filters ? ` data-list="Item" data-filters='${esc(JSON.stringify(filters))}' style="cursor:pointer"` : ""}>
			<div class="cd-k">${esc(label)}</div><div class="stat-v">${value ?? "—"}</div><div class="stat-s">${esc(sub)}</div></div>`;
		const no_price_color = c.no_price ? "#a3302f" : "#097C52";
		return `<div class="surf card">${head(__("Catalog health"), __("Current state"))}<div class="stat">
			${stat(__("Published"), c.published, __("Live on the website"), pub)}
			${stat(__("No selling price"), `<span style="color:${no_price_color}">${c.no_price ?? "—"}</span>`, __("Published, no rate in {0}", [c.price_list || "—"]))}
			${stat(__("On sale"), c.on_sale, __("Published and marked on sale"), { ...pub, custom_on_sale: 1 })}
			${stat(__("On backorder"), c.on_backorder, __("Published and on backorder"), { ...pub, custom_on_backorder: 1 })}
		</div></div>`;
	}

	return { card, delta, trend_card, products_card, groups_card, dispatch_card, carts_card, customers_card, reviews_card, catalog_card };
})();
