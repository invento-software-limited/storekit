// StoreKit Overview: web-shop KPIs, order pipeline, charts and worklists from storekit.api.overview.
frappe.pages["storekit-overview"].on_page_load = (wrapper) => {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Store Overview"), single_column: true });
	frappe
		.require(["/assets/storekit/js/storekit_overview_charts.js", "/assets/storekit/js/storekit_overview_sections.js"])
		.then(() => {
			wrapper.overview = new StoreOverview(page);
			wrapper.overview.refresh();
		});
};

frappe.pages["storekit-overview"].on_page_show = (wrapper) => wrapper.overview?.refresh();

const PERIODS = {
	"Last 7 days": () => [frappe.datetime.add_days(frappe.datetime.get_today(), -6), frappe.datetime.get_today()],
	"Last 30 days": () => [frappe.datetime.add_days(frappe.datetime.get_today(), -29), frappe.datetime.get_today()],
	"Last 90 days": () => [frappe.datetime.add_days(frappe.datetime.get_today(), -89), frappe.datetime.get_today()],
	"This month": () => [frappe.datetime.month_start(), frappe.datetime.get_today()],
	"This year": () => [frappe.datetime.year_start(), frappe.datetime.get_today()],
};
const PAGE_LENGTH = 10;

class StoreOverview {
	constructor(page) {
		this.page = page;
		this.sequence = 0;
		this.start = 0;
		page.wrapper.find(".layout-main-section-wrapper").css({ width: "100%", flex: "1 0 100%" });
		page.body.css("padding", "var(--padding-xs) var(--padding-md)");
		this.$root = $(`<div class="cd sko"><div class="body"></div></div>`).appendTo(page.body);
		this.make_filters();
		this.bind_events();
	}

	make_filters() {
		const change = () => {
			this.start = 0;
			this.refresh();
		};
		this.company = this.page.add_field({
			fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company",
			default: frappe.defaults.get_user_default("company"), reqd: 1, change,
		});
		this.period = this.page.add_field({
			fieldname: "period", label: __("Period"), fieldtype: "Select", default: "Last 30 days",
			options: [...Object.keys(PERIODS), "Custom"].join("\n"),
			change: () => {
				this.toggle_custom();
				change();
			},
		});
		this.from_date = this.page.add_field({ fieldname: "from_date", label: __("From"), fieldtype: "Date", change });
		this.to_date = this.page.add_field({ fieldname: "to_date", label: __("To"), fieldtype: "Date", change });
		this.toggle_custom();
	}

	toggle_custom() {
		const custom = this.period.get_value() === "Custom";
		this.from_date.$wrapper.toggle(custom);
		this.to_date.$wrapper.toggle(custom);
	}

	args() {
		const period = this.period.get_value();
		const [from_date, to_date] =
			period === "Custom" ? [this.from_date.get_value(), this.to_date.get_value()] : PERIODS[period]();
		return { company: this.company.get_value(), from_date, to_date, start: this.start, page_length: PAGE_LENGTH };
	}

	refresh() {
		const args = this.args();
		if (!args.company || !args.from_date || !args.to_date) return;
		const sequence = ++this.sequence;
		this.$root.addClass("loading");
		frappe.call({
			method: "storekit.api.overview.get_dashboard_data",
			args,
			callback: (r) => sequence === this.sequence && r.message && this.render(r.message),
			error: () => sequence === this.sequence && this.render_state(__("Could not load the overview.")),
			always: () => sequence === this.sequence && this.$root.removeClass("loading"),
		});
	}

	render_state(message) {
		this.$root.find(".body").html(`<div class="state">${frappe.utils.escape_html(message)}</div>`);
	}

	render(d) {
		this.d = d;
		const fmt = new MoneyFormat(d.currency);
		const S = storekit_overview_sections;
		this.$root.find(".body").html(
			[
				this.header(d),
				this.cards(d, fmt),
				this.pipeline(d, fmt),
				S.trend_card(),
				`<div class="two even">${S.products_card(d, fmt)}${S.groups_card(d, fmt)}</div>`,
				S.dispatch_card(d, fmt),
				`<div class="two even">${S.carts_card(d, fmt)}${S.customers_card(d)}</div>`,
				`<div class="two even">${S.reviews_card(d)}${S.catalog_card(d)}</div>`,
			].join("")
		);
		this.draw_trend(fmt);
	}

	draw_trend(fmt) {
		const el = this.$root.find(".trend-ch")[0];
		if (!el || !this.d) return;
		const s = this.d.sales, f = this.d.filters;
		const prev_labels = (i) => __("Previous: {0}", [this.d.prev_bucket_labels[i] || ""]);
		el.innerHTML = storekit_charts.combo(this.d.bucket_labels, s.revenue_series, s.prev_revenue_series, {
			width: el.clientWidth, fmt_axis: (v) => fmt.compact(v), fmt_title: (v) => fmt.full(v), prev_label: prev_labels,
		});
		this.$root.find(".trend-sub").text(`${fmt.range(f.from_date, f.to_date)} · ${fmt.scale_label()}`);
	}

	header(d) {
		const f = d.filters, esc = frappe.utils.escape_html;
		const last = d.last_order ? frappe.datetime.str_to_user(d.last_order.transaction_date) : "—";
		const fmt = new MoneyFormat(d.currency);
		return `<div class="hd">
			<div class="hd-mono">SK</div>
			<div class="hd-id"><div class="hd-name">${__("Store overview")}</div>
				<div class="hd-meta"><b>${esc(f.company)}</b> · ${fmt.range(f.from_date, f.to_date)} · ${__("compared with")} ${fmt.range(f.prev_from, f.prev_to)}</div></div>
			<div class="hd-r">
				<div><div class="cd-k">${__("Last web order")}</div><div class="v">${esc(last)}</div></div>
				<div><div class="cd-k">${__("Open order value")}</div><div class="v">${fmt.full(d.dispatch.value)}</div></div>
			</div></div>`;
	}

	cards(d, fmt) {
		const s = d.sales, C = storekit_charts, S = storekit_overview_sections;
		const verdict = s.revenue >= s.prev_revenue ? "#097C52" : "#a3552f";
		const ages = d.dispatch.ages.map((a, i) => ({ ...a, value: a.count, color: ["#097C52", "#8a5a16", "#a3302f"][i] }));
		const idle = d.carts.idle.map((a, i) => ({ label: a.label, value: a.count, color: ["#17626e", "#8a5a16", "#a3552f"][i] }));
		const cust = d.customers.allowed
			? C.segmented([{ label: __("Ordered"), value: d.customers.ordered, color: "#097C52" }, { label: __("No order yet"), value: d.customers.no_order_count, color: "#8a5a16" }])
			: "";
		return `<div class="surf mx">
			${S.card(__("Web revenue"), fmt.value_html(s.revenue), S.delta(s.revenue, s.prev_revenue) + __("vs previous"), C.spark_line(s.revenue_series, verdict), "tint", verdict)}
			${S.card(__("Web orders"), s.orders, S.delta(s.orders, s.prev_orders) + __("vs previous"), C.spark_line(s.orders_series, "#2f5a86"))}
			${S.card(__("Average order"), fmt.value_html(s.aov), S.delta(s.aov, s.prev_aov) + __("vs previous"), C.spark_line(s.aov_series, "#17626e"))}
			${S.card(__("Awaiting dispatch"), d.dispatch.count, `${fmt.full(d.dispatch.value)} ${__("open")}`, C.spark_bars(ages, "#097C52"))}
			${S.card(__("New customers"), d.customers.new ?? "—", d.customers.allowed ? __("{0} without an order", [d.customers.no_order_count]) : __("No access"), cust)}
			${S.card(__("Open carts"), d.carts.count, `${fmt.full(d.carts.value)} · ${__("{0} abandoned", [d.carts.abandoned_count])}`, C.segmented(idle))}
		</div>`;
	}

	pipeline(d, fmt) {
		const p = d.pipeline, f = d.filters, esc = frappe.utils.escape_html;
		const so = (extra) => JSON.stringify({ company: f.company, order_type: "Shopping Cart", transaction_date: ["Between", [f.from_date, f.to_date]], ...extra });
		const open = ["in", ["To Deliver and Bill", "To Deliver"]];
		const stages = [
			["cart", __("In cart"), "#22405e", "Quotation", { docstatus: 0, base_net_total: [">", 0] }],
			["ordered", __("Ordered"), "#17505d", "Sales Order", { docstatus: 1, status: open, per_delivered: 0 }],
			["part_dispatched", __("Part dispatched"), "#145a4c", "Sales Order", { docstatus: 1, status: open, per_delivered: [">", 0] }],
			["to_bill", __("Dispatched, to bill"), "#0a5a3c", "Sales Order", { docstatus: 1, status: "To Bill" }],
			["completed", __("Completed"), "#7a4f12", "Sales Order", { docstatus: 1, status: "Completed" }],
		];
		const blocks = stages.map(([key, label, bg, dt, extra]) =>
			`<div class="fl-c" style="--bg:${bg}" data-list="${dt}" data-filters='${esc(so(extra))}' title="${esc(__("Open {0}", [__(dt)]))}">
				<div class="fl-k">${label}</div><div class="fl-v">${p[key].count}</div><div class="fl-s">${fmt.full(p[key].value)}</div></div>`
		);
		const side = [["closed", __("Closed"), { docstatus: 1, status: "Closed" }], ["on_hold", __("On hold"), { docstatus: 1, status: "On Hold" }], ["cancelled", __("Cancelled"), { docstatus: 2 }]]
			.map(([key, label, extra]) => `<a data-list="Sales Order" data-filters='${esc(so(extra))}'>${label}: <b>${p[key].count}</b></a>`);
		return `<div class="sec">${__("Orders placed in period, by current stage")}</div>
			<div class="fl">${blocks.join("")}</div><div class="fl-x">${side.join("")}</div>`;
	}

	bind_events() {
		this.$root.on("click", "[data-list]", (e) => {
			frappe.route_options = JSON.parse(e.currentTarget.dataset.filters || "{}");
			frappe.set_route("List", e.currentTarget.dataset.list);
		});
		this.$root.on("click", "[data-doc]", (e) => {
			e.preventDefault();
			frappe.set_route("Form", e.currentTarget.dataset.doctype, e.currentTarget.dataset.doc);
		});
		this.$root.on("click", "[data-page]", (e) => {
			this.start = Math.max(0, this.start + Number(e.currentTarget.dataset.page) * PAGE_LENGTH);
			this.refresh();
		});
		$(window).off("resize.sko").on("resize.sko", frappe.utils.debounce(() => this.d && this.draw_trend(new MoneyFormat(this.d.currency)), 200));
	}
}

class MoneyFormat {
	constructor(currency) {
		this.currency = currency;
		this.symbol = get_currency_symbol(currency) || currency;
	}
	full(v) {
		return format_currency(v || 0, this.currency);
	}
	split(v) {
		const a = Math.abs(v || 0);
		if (a >= 1e6) return [(v / 1e6).toFixed(2), "M"];
		if (a >= 1e4) return [(v / 1e3).toFixed(1), "K"];
		return [format_number(v || 0, null, 2), ""];
	}
	compact(v) {
		const [n, unit] = this.split(v);
		return `${this.symbol}${n}${unit}`;
	}
	value_html(v) {
		const [n, unit] = this.split(v);
		return `${this.symbol}${n}<span>${unit || this.currency}</span>`;
	}
	scale_label() {
		return __("{0}, net of VAT and shipping", [this.currency]);
	}
	range(from, to) {
		return `${frappe.datetime.str_to_user(from)} – ${frappe.datetime.str_to_user(to)}`;
	}
}
