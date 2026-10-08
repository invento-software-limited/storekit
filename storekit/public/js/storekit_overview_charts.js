// Inline-SVG chart builders for the StoreKit Overview page (design-system palette, no chart library).
window.storekit_charts = (() => {
	const esc = (v) => frappe.utils.escape_html(String(v ?? ""));
	const SOFT = "#98a1ac";

	function nice_step(max, ticks = 4) {
		const raw = max / ticks || 1;
		const mag = Math.pow(10, Math.floor(Math.log10(raw)));
		for (const n of [1, 2, 2.5, 5, 10]) if (raw <= n * mag) return n * mag;
		return mag * 10;
	}

	function spark_line(values, color) {
		const pts = values.length > 1 ? values : [0, ...values, 0];
		const W = 190, H = 26, top = 5, bottom = 23, n = pts.length;
		const min = Math.min(...pts), range = Math.max(...pts) - min || 1;
		const xs = pts.map((_, i) => 1 + i * ((W - 2) / (n - 1)));
		const ys = pts.map((v) => bottom - ((v - min) / range) * (bottom - top));
		const line = xs.map((x, i) => `${x.toFixed(1)} ${ys[i].toFixed(1)}`).join(" L ");
		const gid = "sko" + color.slice(1) + Math.random().toString(36).slice(2, 6);
		return `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" preserveAspectRatio="none">
			<defs><linearGradient id="${gid}" x1="0" x2="0" y1="0" y2="1">
				<stop offset="0%" stop-color="${color}" stop-opacity=".16"/><stop offset="100%" stop-color="${color}" stop-opacity="0"/>
			</linearGradient></defs>
			<path d="M ${line} L ${xs[n - 1].toFixed(1)} ${H} L ${xs[0].toFixed(1)} ${H} Z" fill="url(#${gid})"/>
			<path d="M ${line}" fill="none" stroke="${color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
			<circle cx="${xs[n - 1].toFixed(1)}" cy="${ys[n - 1].toFixed(1)}" r="2.4" fill="${color}"/>
		</svg>`;
	}

	// bars: [{label, value, color?}] — capped width so a single bar doesn't fill the slot
	function spark_bars(bars, color) {
		const W = 190, H = 26, gap = 4, n = bars.length || 1;
		const w = Math.min(28, (W - gap * (n + 1)) / n);
		const max = Math.max(...bars.map((b) => b.value), 0.0001);
		return `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" preserveAspectRatio="none">${bars
			.map((b, i) => {
				const h = Math.max((b.value / max) * (H - 2), 1);
				return `<rect x="${(gap + i * (w + gap)).toFixed(1)}" y="${(H - h).toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" rx="1" fill="${b.color || color}"><title>${esc(b.label)}: ${esc(b.value)}</title></rect>`;
			})
			.join("")}</svg>`;
	}

	// segments: [{label, value, color}] — composition with a named legend
	function segmented(segments) {
		const total = segments.reduce((s, x) => s + Math.max(0, x.value), 0);
		const bar = total
			? segments.map((x) => `<div style="flex:${(Math.max(0, x.value) / total).toFixed(4)};background:${x.color}" title="${esc(x.label)}: ${esc(x.value)}"></div>`).join("")
			: `<div style="flex:1;background:#eef1f4"></div>`;
		const legend = segments.map((x) => `<span><i style="background:${x.color}"></i>${esc(x.label)} ${esc(x.value)}</span>`).join("");
		return `<div class="sg"><div class="sg-b">${bar}</div><div class="sg-l">${legend}</div></div>`;
	}

	// bars = this period, line = previous period, same buckets
	function combo(labels, primary, comparison, opts) {
		const W = Math.max(opts.width, 320), H = 210, ML = 54, MR = 8, MT = 12, MB = 26;
		const plotW = W - ML - MR, plotH = H - MT - MB, n = labels.length;
		const step = nice_step(Math.max(...primary, ...comparison, 0));
		const top = Math.ceil(Math.max(...primary, ...comparison, 0) / step) * step || step;
		const y = (v) => MT + (top - v) * (plotH / top);
		let grid = "";
		for (let v = 0; v <= top + 1e-6; v += step)
			grid += `<line x1="${ML}" x2="${W - MR}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}" stroke="#edf0f3"/><text x="${ML - 8}" y="${(y(v) + 3.5).toFixed(1)}" font-size="9.5" fill="${SOFT}" text-anchor="end">${esc(opts.fmt_axis(v))}</text>`;
		const colW = plotW / n, barW = Math.max(3, Math.min(30, colW * 0.6));
		const every = Math.ceil(n / Math.floor(plotW / 46));
		let bars = "", labs = "", dots = "";
		const pts = [];
		labels.forEach((label, i) => {
			const cx = ML + (i + 0.5) * colW, h = (primary[i] || 0) * (plotH / top);
			bars += `<rect x="${(cx - barW / 2).toFixed(1)}" y="${(y(0) - h).toFixed(1)}" width="${barW.toFixed(1)}" height="${h.toFixed(1)}" fill="#097C52" rx="1.5"><title>${esc(label)}: ${esc(opts.fmt_title(primary[i] || 0))}</title></rect>`;
			pts.push(`${cx.toFixed(1)} ${y(comparison[i] || 0).toFixed(1)}`);
			dots += `<circle cx="${cx.toFixed(1)}" cy="${y(comparison[i] || 0).toFixed(1)}" r="2.2" fill="#fff" stroke="#a3552f" stroke-width="1.4"><title>${esc(opts.prev_label(i))}: ${esc(opts.fmt_title(comparison[i] || 0))}</title></circle>`;
			if (i % every === 0) labs += `<text x="${cx.toFixed(1)}" y="${H - 8}" font-size="9.5" fill="${SOFT}" text-anchor="middle">${esc(label)}</text>`;
		});
		const line = `<path d="M ${pts.join(" L ")}" fill="none" stroke="#a3552f" stroke-width="1.5" stroke-linejoin="round"/>`;
		return `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}">${grid}${bars}${line}${dots}${labs}</svg>`;
	}

	// parts: [{label, value, color}]
	function donut(parts, center, fmt) {
		const total = parts.reduce((s, p) => s + p.value, 0) || 1;
		const cx = 96, cy = 100, r = 74, sw = 24, C = 2 * Math.PI * r;
		let offset = 0, rings = "", rows = "";
		parts.forEach((p, i) => {
			const len = (p.value / total) * C, pct = Math.round((p.value / total) * 100);
			rings += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${p.color}" stroke-width="${sw}" stroke-dasharray="${len.toFixed(2)} ${C.toFixed(2)}" stroke-dashoffset="${(-offset).toFixed(2)}" transform="rotate(-90 ${cx} ${cy})"><title>${esc(p.label)}: ${esc(fmt(p.value))} (${pct}%)</title></circle>`;
			offset += len;
			const ty = 22 + i * 32;
			rows += `<rect x="206" y="${ty}" width="3" height="24" fill="${p.color}"/>
				<text x="217" y="${ty + 10}" font-size="11" font-weight="600" fill="${p.color}">${esc(String(p.label).slice(0, 22))}</text>
				<text x="217" y="${ty + 22}" font-size="9.5" fill="#5c6672">${pct}%</text>
				<text x="420" y="${ty + 16}" font-size="11.5" font-weight="600" fill="#0d1117" text-anchor="end">${esc(fmt(p.value))}</text>`;
		});
		const h = Math.max(200, 22 + parts.length * 32);
		return `<svg viewBox="0 0 424 ${h}" width="100%" style="display:block;max-width:424px;margin:0 auto">
			<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#eef1f4" stroke-width="${sw}"/>${rings}
			<text x="${cx}" y="${cy - 6}" font-size="9" letter-spacing="1.4" fill="#0d1117" text-anchor="middle">${esc(center.label)}</text>
			<text x="${cx}" y="${cy + 14}" font-size="18" font-weight="600" fill="#0d1117" text-anchor="middle" letter-spacing="-.6">${esc(center.value)}</text>${rows}
		</svg>`;
	}

	// buckets: [{label, value}] — histogram, colour per bucket
	function histogram(buckets, colors) {
		const W = 420, H = 150, ML = 26, MR = 4, MT = 18, MB = 22, plotW = W - ML - MR, plotH = H - MT - MB;
		const total = buckets.reduce((s, b) => s + b.value, 0) || 1;
		const step = Math.max(1, Math.ceil(nice_step(Math.max(...buckets.map((b) => b.value), 1), 3)));
		const top = Math.ceil(Math.max(...buckets.map((b) => b.value), 1) / step) * step;
		const colW = plotW / buckets.length, barW = Math.min(46, colW * 0.62);
		let out = "";
		for (let v = 0; v <= top; v += step) {
			const y = MT + plotH - v * (plotH / top);
			out += `<line x1="${ML}" x2="${W - MR}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}" stroke="#edf0f3"/><text x="${ML - 6}" y="${(y + 3.5).toFixed(1)}" font-size="9.5" fill="${SOFT}" text-anchor="end">${v}</text>`;
		}
		buckets.forEach((b, i) => {
			const cx = ML + (i + 0.5) * colW, h = b.value * (plotH / top), y = MT + plotH - h, c = colors[i];
			const pct = Math.round((b.value / total) * 100);
			out += `<rect x="${(cx - barW / 2).toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${h.toFixed(1)}" fill="${c}" rx="2"><title>${esc(b.label)}: ${b.value} (${pct}%)</title></rect>`;
			if (b.value) out += `<text x="${cx.toFixed(1)}" y="${(y - 5).toFixed(1)}" font-size="10" font-weight="600" fill="${c}" text-anchor="middle">${pct}%</text>`;
			out += `<text x="${cx.toFixed(1)}" y="${H - 6}" font-size="10" fill="${SOFT}" text-anchor="middle">${esc(b.label)}</text>`;
		});
		return `<svg viewBox="0 0 ${W} ${H}" width="100%">${out}</svg>`;
	}

	return { spark_line, spark_bars, segmented, combo, donut, histogram };
})();
