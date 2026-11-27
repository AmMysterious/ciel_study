/* "Find a topic" box (27 Nov 2026). Searches pyt_index.json (written by pyt_pages.py) and links straight to the
   topic on its subject page. Without JavaScript the box stays hidden and the subject tiles still work. */
(function () {
  var w = document.querySelector(".topic-find");
  if (!w || !window.fetch) return;
  w.hidden = false;
  var q = w.querySelector("input"), out = w.querySelector("ul"), ix = null;
  var base = w.getAttribute("data-base") || "";
  function load() {
    if (ix) return Promise.resolve(ix);
    return fetch(base + "pyt_index.json").then(function (r) { return r.json(); }).then(function (d) { ix = d; return d; });
  }
  function esc(t) {
    return String(t).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }
  q.addEventListener("focus", load);
  q.addEventListener("input", function () {
    var v = q.value.trim().toLowerCase();
    if (v.length < 2) { out.innerHTML = ""; return; }
    load().then(function (d) {
      var words = v.split(/\s+/);
      var hits = d.filter(function (r) {
        var hay = (r.t + " " + r.s).toLowerCase();
        return words.every(function (x) { return hay.indexOf(x) > -1; });
      }).sort(function (a, b) { return b.n - a.n; }).slice(0, 8);
      out.innerHTML = hits.length ? hits.map(function (r) {
        return '<li><a href="' + base + r.u + '"><b>' + esc(r.t) + "</b><span>" + esc(r.s) + " · " + r.n +
          " past questions</span></a></li>";
      }).join("") : '<li class="none">No topic found. Try a shorter word.</li>';
    });
  });
})();
