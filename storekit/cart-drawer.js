// Populates the cart side-drawer (#cart-section / #cart-item-template / #cart-container)
// and wires its qty +/-/Remove buttons. The drawer markup already existed on every
// page but nothing ever called the cart APIs to fill it in, so it always showed the
// static "Your cart is empty" placeholder regardless of the cart_count badge.
(function () {
  if (window.cartDrawerInit) return;
  window.cartDrawerInit = true;

  function getCookie(name) {
    var m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : "";
  }

  function isGuest() {
    var user = getCookie("user_id");
    return !user || user === "Guest";
  }

  function apiGet(method, params) {
    var qs = new URLSearchParams(params || {}).toString();
    return fetch("/api/method/" + method + (qs ? "?" + qs : ""), {
      method: "GET",
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin"
    }).then(function (r) { return r.json(); });
  }

  function apiPost(method, body) {
    return fetch("/api/method/" + method, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Frappe-CSRF-Token": window.frappe ? window.frappe.csrf_token : "",
        "X-Requested-With": "XMLHttpRequest"
      },
      credentials: "same-origin",
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); });
  }

  function updateBadge(count) {
    var el = document.getElementById("cart_count");
    if (el) el.textContent = count;
  }

  function renderCartDrawer() {
    var container = document.getElementById("cart-container");
    var templateWrap = document.getElementById("cart-item-template");
    var emptyState = document.getElementById("empty-cart");
    var cartSection = document.getElementById("cart-section");
    if (!container || !templateWrap) return;

    var rowTemplate = templateWrap.querySelector(".cart-item") || templateWrap;
    var guest = isGuest();
    var cartItemsCookie = guest ? (getCookie("cart_items") || "[]") : null;
    var params = guest ? { cart_items: cartItemsCookie } : {};

    Promise.all([
      apiGet("storekit.webshop_functions.cart.get_cart_items", params),
      apiGet("storekit.webshop_functions.cart.get_order_details", params)
    ]).then(function (results) {
      var items = (results[0] && results[0].message) || [];
      var totals = (results[1] && results[1].message) || {};

      container.innerHTML = "";

      if (!items.length) {
        if (cartSection) cartSection.style.display = "none";
        if (emptyState) emptyState.style.display = "flex";
        updateBadge(0);
        return;
      }

      if (cartSection) cartSection.style.display = "";
      if (emptyState) emptyState.style.display = "none";

      var totalQty = 0;
      items.forEach(function (item) {
        totalQty += Number(item.qty) || 0;

        var row = rowTemplate.cloneNode(true);
        row.removeAttribute("id");
        row.style.display = "";
        row.dataset.itemCode = item.item_code;

        var img = row.querySelector(".item_image");
        if (img && item.image) img.src = item.image;

        var nameEl = row.querySelector(".item_name");
        if (nameEl) nameEl.textContent = item.item_name;

        var priceEl = row.querySelector(".price");
        if (priceEl) priceEl.textContent = item.rate;

        var qtyEl = row.querySelector(".item_qty");
        if (qtyEl) qtyEl.textContent = item.qty;

        container.appendChild(row);
      });

      var subEl = document.getElementById("sub_total");
      if (subEl && totals.total_price) subEl.textContent = totals.total_price;

      var grandEl = document.getElementById("grand_total");
      if (grandEl && totals.grand_total) grandEl.textContent = totals.grand_total;

      updateBadge(totalQty);
    }).catch(function (err) {
      console.error("Cart drawer render failed:", err);
    });
  }

  function handleQtyClick(e) {
    var btn = e.target.closest(".update_cart_qty");
    if (!btn) return;
    var row = btn.closest("[data-item-code]");
    if (!row) return;

    e.preventDefault();
    var action = btn.dataset.action; // "add" | "remove" | "delete"
    var body = { item_code: row.dataset.itemCode, qty: 1, action: action };
    if (isGuest()) body.cart_items = getCookie("cart_items") || "[]";

    apiPost("storekit.webshop_functions.cart.update_cart_qty", body).then(function () {
      renderCartDrawer();
    });
  }

  document.addEventListener("click", handleQtyClick);

  var openButton = document.getElementById("cart-open-button");
  if (openButton) openButton.addEventListener("click", renderCartDrawer);

  window.renderCartDrawer = renderCartDrawer;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", renderCartDrawer);
  } else {
    renderCartDrawer();
  }
})();
