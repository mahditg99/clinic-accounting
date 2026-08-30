/* Azaran Teb Web — shared client helpers + interactive pieces */
(function () {
  "use strict";

  /* ================================================================ */
  /* Persian numeral helpers (item 9: Persian digits are the standard) */
  /* ================================================================ */
  var FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
  var EN_DIGITS = "0123456789";
  var AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"; /* Arabic-Indic, tolerated on input */

  /* Any digit script (English / Persian / Arabic-Indic) -> Persian digits. */
  function faDigits(s) {
    return String(s == null ? "" : s).replace(/[0-9٠-٩]/g, function (d) {
      var i = EN_DIGITS.indexOf(d);
      if (i === -1) i = AR_DIGITS.indexOf(d);
      return FA_DIGITS[i];
    });
  }
  /* Any digit script -> English (Latin) digits, the backend storage form. */
  function enDigits(s) {
    return String(s == null ? "" : s).replace(/[۰-۹٠-٩]/g, function (d) {
      var i = FA_DIGITS.indexOf(d);
      if (i === -1) i = AR_DIGITS.indexOf(d);
      return String(i);
    });
  }
  /* Parse any user-entered number (Persian or English digits, commas). */
  function parseNum(s) {
    var n = parseInt(enDigits(String(s == null ? "" : s)).replace(/[^\d-]/g, ""), 10);
    return isNaN(n) ? 0 : n;
  }
  /* Format an integer with thousands separators, in Persian digits.
     The separator is the Persian thousands mark '٬' (U+066C).
     Negative values are wrapped in Unicode LTR-isolate controls so RTL text
     renders "-۱٫۲۳۴" as a true negative number instead of a detached minus. */
  var THOUSANDS = "\u066C";
  function fmtMoney(n) {
    n = parseNum(n);
    if (n < 0) return "\u2066-" + faDigits(String(-n).replace(/\B(?=(\d{3})+(?!\d))/g, THOUSANDS)) + "\u2069";
    return faDigits(String(n).replace(/\B(?=(\d{3})+(?!\d))/g, THOUSANDS));
  }

  /* Generic client-side table filter (used by patients + doctors lists).
     Matching rules (item: search must work with either digit script and with
     full names):
       - the query is normalized to English digits, so typing "1001" finds a
         row rendered as "۱۰۰۱" and vice versa;
       - every whitespace-separated word must appear somewhere in the row,
         in any order ("مریم حسابداری" = first + last name together);
       - ZWNJ (نیم‌فاصله) is treated as a space on both sides. */
  function makeRowFilter(tableEl, noMatchEl) {
    function norm(s) {
      return enDigits(String(s == null ? "" : s))
        .replace(/\u200c/g, " ").toLowerCase();
    }
    return function (rawQ) {
      var words = norm(rawQ).split(/\s+/).filter(Boolean);
      var visible = 0;
      tableEl.querySelectorAll("tbody tr").forEach(function (tr) {
        if (noMatchEl && tr === noMatchEl) return;
        var ok = true;
        if (words.length) {
          var hay = norm(tr.textContent);
          ok = words.every(function (w) { return hay.indexOf(w) !== -1; });
        }
        tr.style.display = ok ? "" : "none";
        if (ok) visible += 1;
      });
      if (noMatchEl) {
        noMatchEl.style.display = (words.length && visible === 0) ? "" : "none";
      }
    };
  }

  /* ------------------------------------------------ flash + toasts ------ */
  const flashEl = document.getElementById("flash");
  function showFlash(t, cls) {
    if (!flashEl) return;
    flashEl.className = cls;
    flashEl.textContent = t;
    flashEl.style.display = "";
    setTimeout(() => { flashEl.style.display = "none"; }, 4000);
  }

  function toast(msg, cls) {
    cls = cls || "";
    let wrap = document.getElementById("toasts");
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.id = "toasts";
      document.body.appendChild(wrap);
    }
    const el = document.createElement("div");
    el.className = "toast " + cls;
    el.textContent = msg;
    wrap.appendChild(el);
    setTimeout(() => el.remove(), 3500);
  }

  function confirmAsk(msg) { return window.confirm(msg); }

  /* ------------------------------------------------ generic POST -------- */
  async function postJSON(url, payload) {
    const r = await fetch(url, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload), credentials: "same-origin",
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { const e = new Error((data && data.detail) || "خطا در ثبت اطلاعات"); e.status = r.status; throw e; }
    return data;
  }

  async function postForm(url, form) {
    const r = await fetch(url, { method: "POST", body: new FormData(form), credentials: "same-origin" });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { const e = new Error((data && data.detail) || "خطا در ثبت اطلاعات"); e.status = r.status; throw e; }
    return data;
  }

  window.azaran40 = {
    showFlash, toast, confirmAsk, postJSON, postForm,
    faDigits, enDigits, parseNum, fmtMoney, makeRowFilter,
  };

  /* ------------------------------------------------ sidebar toggle ------ */
  const toggle = document.getElementById("menuToggle");
  if (toggle) {
    toggle.addEventListener("click", () => {
      const sb = document.getElementById("sidebar");
      if (sb) sb.classList.toggle("open");
    });
  }

  /* ------------------------------------------------ number input: auto */
  /* Persian-aware money fields: accept Persian or English digits, display
     Persian digits with thousands separators (item 9).
     data-fanum: numeric fields (counts, qty, stock, phone/file numbers)
     rendered as text so Persian typing is possible; digits are stored/parsed
     in English by the backend but shown in Persian.
     Delegated so dynamically-added inputs (payment rows) get it too. */
  document.addEventListener("input", function (e) {
    const t = e.target;
    if (!t || !t.matches) return;
    if (t.matches("input[data-money]")) {
      const digits = enDigits(t.value).replace(/[^\d]/g, "");
      t.value = digits
        ? faDigits(parseInt(digits, 10).toLocaleString("en-US")).replace(/,/g, THOUSANDS)
        : "";
    } else if (t.matches("input[data-fanum]")) {
      /* Keep only digits (either script), always show Persian digits. */
      t.value = faDigits(enDigits(t.value).replace(/[^\d]/g, ""));
    } else if (t.matches("input[data-fadigits]")) {
      /* Free-text search boxes: show Persian digits while typing but keep
         every other character (names, spaces). The mapping is 1:1, so the
         caret index survives the rewrite. */
      var fa = faDigits(t.value);
      if (fa !== t.value) {
        var pos = (typeof t.selectionStart === "number") ? t.selectionStart : fa.length;
        t.value = fa;
        try { t.setSelectionRange(pos, pos); } catch (err) { /* unsupported */ }
      }
    }
  });

  /* ================================================================ */
  /* Patient autocomplete (item 1: results appear under the field).    */
  /* The suggestion box is appended to the input's own wrapper so it   */
  /* renders directly below the patient field.                         */
  /* ================================================================ */
  const pSearch = document.getElementById("patientSearch");
  const pHidden = document.getElementById("patientId");
  if (pSearch) {
    let box = null;
    function makeBox() {
      box = document.createElement("div");
      box.className = "suggest";
      box.style.display = "none";
      const wrap = pSearch.closest(".form-row") || pSearch.parentElement;
      wrap.style.position = "relative";
      wrap.appendChild(box);
    }
    let timer = null;
    pSearch.addEventListener("input", () => {
      clearTimeout(timer);
      const q = pSearch.value.trim();
      if (!q) { pHidden.value = ""; if (box) box.style.display = "none"; return; }
      timer = setTimeout(async () => {
        try {
          const r = await fetch("/api/patients/search?q=" + encodeURIComponent(enDigits(q)), { credentials: "same-origin" });
          const list = await r.json();
          if (!box) makeBox();
          if (!list.length) {
            box.innerHTML = '<div style="padding:10px 12px;color:var(--muted);font-size:13px;">موردی یافت نشد</div>';
          } else {
            box.innerHTML = list.slice(0, 8).map((it) =>
              '<div class="suggest-item" data-id="' + it.id + '" data-name="' + it.name + '" data-file="' + (it.file_no || '') + '">' + it.text + '</div>'
            ).join("");
            box.querySelectorAll(".suggest-item").forEach((el) => {
              el.addEventListener("click", () => {
                pSearch.value = el.dataset.name;
                pHidden.value = el.dataset.id;
                pSearch.dataset.fileNo = el.dataset.file || "";
                box.style.display = "none";
              });
            });
          }
          box.style.display = "block";
        } catch (e) { /* ignore */ }
      }, 200);
    });
    document.addEventListener("click", (e) => {
      if (box && !box.contains(e.target) && e.target !== pSearch) box.style.display = "none";
    });
  }

  /* ================================================================ */
  /* Jalali date picker (item 8: pick from a calendar, don't type).    */
  /* Attach to every input[data-jdate].                              */
  /* ================================================================ */
  const JMONTHS = ["فروردین","اردیبهشت","خرداد","تیر","مرداد","شهریور",
                   "مهر","آبان","آذر","دی","بهمن","اسفند"];
  const JWEEK = ["ش","ی","د","س","چ","پ","ج"];

  function jIsLeap(jy) { return (25 * jy + 11) % 33 < 8; }
  function jMonthLen(jy, jm) {
    if (jm <= 6) return 31;
    if (jm <= 11) return 30;
    return jIsLeap(jy) ? 30 : 29;
  }
  function parseJDate(str) {
    var s = enDigits(str || "").replace(/-/g, "/");
    var p = s.split("/");
    if (p.length < 3) return null;
    var jy = parseInt(p[0], 10), jm = parseInt(p[1], 10), jd = parseInt(p[2], 10);
    if (!jy || jm < 1 || jm > 12 || jd < 1 || jd > jMonthLen(jy, jm)) return null;
    return { jy: jy, jm: jm, jd: jd };
  }

  function attachJDatePicker(input) {
    var picker = null;
    /* Item 5: dates must be picked from the calendar, not typed. */
    input.setAttribute("readonly", "readonly");
    input.style.cursor = "pointer";
    function open() {
      if (picker) { picker.style.display = "block"; return; }
      var cur = parseJDate(input.value) ||
                parseJDate(window.AZARAN_TODAY_JALALI) ||
                { jy: 1403, jm: 1, jd: 1 };
      var viewJY = cur.jy, viewJM = cur.jm;

      picker = document.createElement("div");
      picker.className = "jdate-picker";
      picker.style.display = "block";
      input.parentElement.style.position = "relative";
      input.parentElement.appendChild(picker);

      function render() {
        var len = jMonthLen(viewJY, viewJM);
        /* weekday of the 1st of the Jalali month (0=Sunday..6=Saturday) */
        var g = jalaaliToGregorian(viewJY, viewJM, 1);
        var d1 = new Date(g[0], g[1] - 1, 1).getDay(); // 0..6
        /* Persian weeks start Saturday (index 6 in JS). Offset so column 0 = Saturday. */
        var offset = (d1 + 1) % 7; // Saturday=0, Sunday=1, ... Friday=6
        var today = parseJDate(window.AZARAN_TODAY_JALALI);
        var html = "";
        html += '<div class="jp-head">' +
                  '<button type="button" class="jp-nav" data-nav="-1">‹</button>' +
                  '<span class="jp-title">' + JMONTHS[viewJM - 1] + ' ' + faDigits(viewJY) + '</span>' +
                  '<button type="button" class="jp-nav" data-nav="1">›</button>' +
                '</div>';
        html += '<div class="jp-week">' + JWEEK.map(function (w) { return '<span>' + w + '</span>'; }).join("") + '</div>';
        html += '<div class="jp-grid">';
        for (var i = 0; i < offset; i++) html += '<span class="jp-empty"></span>';
        for (var d = 1; d <= len; d++) {
          var cls = "jp-day";
          if (today && viewJY === today.jy && viewJM === today.jm && d === today.jd) cls += " today";
          if (cur && viewJY === cur.jy && viewJM === cur.jm && d === cur.jd) cls += " sel";
          html += '<button type="button" class="' + cls + '" data-d="' + d + '">' + faDigits(d) + '</button>';
        }
        html += '</div>';
        html += '<div class="jp-foot"><button type="button" class="jp-today">امروز</button><button type="button" class="jp-clear">پاک کردن</button></div>';
        picker.innerHTML = html;

        picker.querySelectorAll("[data-nav]").forEach(function (b) {
          b.addEventListener("click", function () {
            viewJM += parseInt(b.dataset.nav, 10);
            if (viewJM < 1) { viewJM = 12; viewJY--; }
            if (viewJM > 12) { viewJM = 1; viewJY++; }
            render();
          });
        });
        picker.querySelectorAll(".jp-day").forEach(function (b) {
          b.addEventListener("click", function () {
            var d = parseInt(b.dataset.d, 10);
            var val = faDigits(viewJY) + "/" + faDigits(String(viewJM).length < 2 ? "0" + viewJM : viewJM) +
                      "/" + faDigits(String(d).length < 2 ? "0" + d : d);
            input.value = val;
            input.dispatchEvent(new Event("change"));
            picker.style.display = "none";
          });
        });
        var t = picker.querySelector(".jp-today");
        if (t) t.addEventListener("click", function () {
          if (today) {
            input.value = faDigits(today.jy) + "/" + faDigits(String(today.jm).length < 2 ? "0" + today.jm : today.jm) +
                          "/" + faDigits(String(today.jd).length < 2 ? "0" + today.jd : today.jd);
            input.dispatchEvent(new Event("change"));
            picker.style.display = "none";
          }
        });
        var clr = picker.querySelector(".jp-clear");
        if (clr) clr.addEventListener("click", function () {
          input.value = "";
          input.dispatchEvent(new Event("change"));
          picker.style.display = "none";
        });
      }
      render();
    }

    input.addEventListener("focus", open);
    input.addEventListener("click", open);
    document.addEventListener("click", function (e) {
      if (picker && !picker.contains(e.target) && e.target !== input) picker.style.display = "none";
    });
    input.addEventListener("blur", function () {
      setTimeout(function () { if (picker) picker.style.display = "none"; }, 150);
    });
  }

  document.querySelectorAll("input[data-jdate]").forEach(attachJDatePicker);

  /* ================================================================ */
  /* Generic sortable tables (item 13: click any column to sort).      */
  /* ================================================================ */
  function sortValue(text) {
    text = enDigits(String(text == null ? "" : text)).trim();
    var neg = false, s = text;
    if (s.indexOf("-") !== -1) { neg = true; s = s.replace(/-/g, ""); }
    var n = parseFloat(s.replace(/[^\d.]/g, ""));
    if (isNaN(n)) return text;
    return neg ? -n : n;
  }
  function initSortable(table) {
    const thead = table.querySelector("thead");
    if (!thead) return;
    const ths = Array.prototype.slice.call(thead.querySelectorAll("th"));
    ths.forEach(function (th, index) {
      th.classList.add("sortable");
      th.style.cursor = "pointer";
      th.addEventListener("click", function () {
        const tbody = table.querySelector("tbody");
        if (!tbody) return;
        const rows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
        if (!rows.length) return;
        const dir = th.dataset.dir === "asc" ? -1 : 1;
        ths.forEach(function (h) { h.dataset.dir = ""; });
        th.dataset.dir = dir === 1 ? "asc" : "desc";
        rows.sort(function (a, b) {
          const ac = a.children[index], bc = b.children[index];
          const av = ac ? sortValue(ac.textContent) : "";
          const bv = bc ? sortValue(bc.textContent) : "";
          if (typeof av === "number" && typeof bv === "number") return (av - bv) * dir;
          return String(av).localeCompare(String(bv), "fa") * dir;
        });
        rows.forEach(function (r) { tbody.appendChild(r); });
      });
    });
  }
  document.querySelectorAll("table.tbl").forEach(initSortable);

  /* ------------------------------------------------ Jalali date -- */
  const JALALI_MONTHS = ["فروردین","اردیبهشت","خرداد","تیر","مرداد","شهریور","مهر","آبان","آذر","دی","بهمن","اسفند"];

  /* Public-domain Jalali -> Gregorian (jalaali-js by Behrang Noruzi Niya).
     jm is 1-based. Returns [gy, gm, gd]. */
  function div(a, b) { return ~~(a / b); }
  function mod(a, b) { return a - ~~(a / b) * b; }
  function jalCal(jy) {
    var breaks = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
      1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178];
    var bl = breaks.length;
    var gy = jy + 621, leapJ = -14, jp = breaks[0], jm, jump = 0, leap = 0;
    if (jy < jp || jy >= breaks[bl - 1]) { throw new Error("Invalid Jalali year"); }
    for (var i = 1; i < bl; i += 1) {
      jm = breaks[i]; jump = jm - jp;
      if (jy < jm) break;
      leapJ = leapJ + div(jump, 33) * 8 + div(mod(jump, 33), 4);
      jp = jm;
    }
    var n = jy - jp;
    leapJ = leapJ + div(n, 33) * 8 + div(mod(n, 33) + 3, 4);
    if (mod(jump, 33) === 4 && jump - n === 4) leapJ += 1;
    var leapG = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150;
    var march = 20 + leapJ - leapG;
    if (jump - n < 6) n = n - jump + div(jump + 4, 33) * 33;
    leap = mod(mod(n + 1, 33) - 1, 4);
    if (leap === -1) leap = 4;
    return { leap: leap, gy: gy, march: march };
  }
  function jalaliToDate(jy, jm, jd) {
    var r = jalCal(jy);
    return new Date(r.gy, 2, r.march + (jm - 1) * 31 - div(jm, 7) * (jm - 7) + jd - 1);
  }
  function jalaaliToGregorian(jy, jm, jd) {
    var g = jalaliToDate(jy, jm, jd);
    return [g.getFullYear(), g.getMonth() + 1, g.getDate()];
  }
  window.azaran40.jalaaliToGregorian = jalaaliToGregorian;
  window.azaran40.JALALI_MONTHS = JALALI_MONTHS;
  window.azaran40.fmtMoney = fmtMoney;

  /* ================================================================ */
  /* Negative-value semantics: scan summary cards, stat values and     */
  /* numeric table cells; anything that begins with '-' (after bidi   */
  /* isolates) gets the .neg class so losses read as red at a glance. */
  /* Runs once on load and re-runs after recalc()-driven updates via  */
  /* a MutationObserver on those containers.                          */
  /* ================================================================ */
  function markNegatives(root) {
    (root || document).querySelectorAll(
      ".sum-card .val, .stat .value, table.tbl td.num"
    ).forEach(function (el) {
      var t = el.textContent.replace(/[\u2066-\u2069]/g, "").trim();
      if (t.indexOf("-") === 0) {
        if (!el.classList.contains("neg")) el.classList.add("neg");
      } else if (el.classList.contains("neg")) {
        el.classList.remove("neg");
      }
    });
  }
  markNegatives(document);
  var mo = new MutationObserver(function () { markNegatives(document); });
  mo.observe(document.body, { childList: true, subtree: true, characterData: true });
})();