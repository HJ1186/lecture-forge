/* lecture-forge :: the ask-box. Works on both pages:
   - lecture page: #askbox dock at the bottom right, knows which section you are reading
   - standalone ask page: big textarea + question field
   Talks to the local server (/ping, /ask); falls back to the offline bank. */
(function () {
  "use strict";
  var CFG = window.LF_CONFIG || {};
  var BANK = window.LF_BANK || [];
  var API = CFG.api || (location.protocol === "file:" ? "http://127.0.0.1:8765" : "");
  var STOP = ["为什", "什么", "怎么", "这个", "那个", "一个", "可以", "是不", "不是",
    "的话", "时候", "如果", "如何", "哪一", "哪些", "这样", "那样", "需要", "应该",
    "到底", "那么", "有没", "没有", "请问", "一下", "为什"];

  function norm(s) {
    return (s || "").toLowerCase().replace(/[\s,.;:!?"'`()\[\]{}<>，。；：！？“”‘’（）【】《》、·\-—…\/\\]/g, "");
  }
  function grams(s) {
    var t = norm(s), out = [], i;
    for (i = 0; i < t.length - 1; i++) {
      var g = t.substr(i, 2);
      if (STOP.indexOf(g) >= 0) continue;
      if (/^[a-z0-9]{2}$/.test(g)) continue;
      out.push(g);
    }
    return out;
  }
  function score(entry, q) {
    var nq = norm(q), nqs = entry.q ? norm(entry.q) : "", full = norm((entry.a || []).join("") + " " + (entry.tags || []).join(" "));
    var sc = 0;
    if (nq && nqs.indexOf(nq) >= 0) sc += 100;
    if (nq && nq.length >= 2 && full.indexOf(nq) >= 0) sc += 40;
    (entry.tags || []).forEach(function (t) {
      var nt = norm(t);
      if (!nt) return;
      if (nq.indexOf(nt) >= 0) sc += 45;
      else if (nq.length >= 2 && nt.indexOf(nq) >= 0) sc += 25;
    });
    var both = grams(q).concat(grams(entry.q || ""));
    var uniq = both.filter(function (g, i) { return both.indexOf(g) === i; });
    var hit = 0;
    uniq.forEach(function (g) { if (full.indexOf(g) >= 0 || nqs.indexOf(g) >= 0) hit++; });
    sc += Math.min(56, hit * 2);
    return sc;
  }
  function find(q) {
    var list = BANK.map(function (e) { return { e: e, s: score(e, q) }; })
      .filter(function (x) { return x.s > 0; })
      .sort(function (a, b) { return b.s - a.s; });
    if (!list.length) return [];
    var best = list[0].s, cut = Math.max(24, best * 0.62);
    return list.filter(function (x) { return x.s >= cut; }).slice(0, 3).map(function (x) { return x.e; });
  }

  function esc(s) {
    return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function cardHtml(entry, cls) {
    var h = '<div class="card ' + (cls || "") + '"><div class="q">' + esc(entry.q) + "</div>";
    if (entry.a && entry.a.length) {
      h += "<ul>" + entry.a.map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("") + "</ul>";
    }
    if (entry.pin) {
      h += '<div class="loc"><a data-jump="' + esc(entry.pin) + '">→ 跳到讲义「' + esc(entry.pin.replace(/[、，].*$/, "")) + "」这节</a></div>";
    }
    return h + "</div>";
  }
  function jump(pin) {
    var hs = document.querySelectorAll("h2"), i, target = null;
    for (i = 0; i < hs.length; i++) {
      if (hs[i].textContent.replace(/^\s+/, "").indexOf(pin) === 0) { target = hs[i]; break; }
    }
    if (!target) return;
    if (document.body.classList.contains("hidenotes")) document.body.classList.remove("hidenotes");
    var note = target.nextElementSibling;
    while (note && !/^ASIDE$/.test(note.tagName)) note = note.nextElementSibling;
    if (note && note.tagName === "ASIDE") { var d = note.querySelector("details"); if (d) d.open = true; }
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  document.addEventListener("click", function (ev) {
    var a = ev.target.closest ? ev.target.closest("[data-jump]") : null;
    if (a) { ev.preventDefault(); jump(a.getAttribute("data-jump")); }
  });

  /* ---------- which section is on screen (context for the model) ---------- */
  function grabView() {
    var hs = [].slice.call(document.querySelectorAll("h1,h2")), pick = null, i;
    var mid = window.innerHeight * 0.35;
    for (i = 0; i < hs.length; i++) {
      var r = hs[i].getBoundingClientRect();
      if (r.top <= mid) pick = hs[i];
    }
    pick = pick || hs[0];
    if (!pick) return { name: "", text: "" };
    var out = [], node = pick.nextElementSibling, tag = pick.tagName;
    while (node) {
      if (/^H[12]$/.test(node.tagName) && node.tagName <= tag) break;
      if (!/^ASIDE$/.test(node.tagName)) out.push((node.innerText || "").trim());
      if (out.join("").length > 2200) break;
      node = node.nextElementSibling;
    }
    return { name: pick.textContent.trim().replace(/\s+/g, " "), text: out.join("\n").slice(0, 2200) };
  }

  /* ---------- online / offline ---------- */
  var online = null;
  function ping() {
    return fetch(API + "/ping", { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
  }
  function askModel(q, ctx) {
    return fetch(API + "/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ q: q, ctx: ctx })
    }).then(function (r) { return r.json(); });
  }
  function renderModel(obj) {
    var h = '<div class="card"><div class="q">' + esc(obj.q || "") + "</div>";
    h += '<div class="body">' + esc(obj.a || "") + "</div>";
    if (obj.src) h += '<div class="src">' + esc(obj.src) + "</div>";
    return h + "</div>";
  }

  /* ---------- lecture-page dock ---------- */
  var dock = document.getElementById("dock");
  if (dock) {
    var qIn = document.getElementById("q"), ans = document.getElementById("ans"),
      st = document.getElementById("st"), cxt = document.getElementById("cxt"),
      mdTag = document.getElementById("md"), dockbtn = document.getElementById("dockbtn"),
      last = { q: "", ctx: "", ctxName: "" };

    var v = grabView();
    if (cxt) cxt.textContent = v.name ? ("📄 " + v.name) : "📄 （没找到当前位置）";

    function status(txt, cls) {
      if (!st) return;
      st.textContent = txt;
      if (mdTag) { mdTag.className = "tag" + (cls ? " " + cls : ""); mdTag.textContent = txt; }
    }
    ping().then(function (r) {
      online = !!(r && r.ok);
      status(online ? (r.mode === "model" ? "模型在线" : "助手在线 · 题库") : "离线题库", online ? "on" : "");
    });

    function go() {
      var q = (qIn.value || "").trim();
      ans.innerHTML = "";
      if (!q) { ans.innerHTML = '<div class="empty">输入一个关键词试试，例如：互电阻 / 为什么 b 从 8 变成 6 / 电流源在中间怎么办</div>'; return; }
      var g = grabView();
      last = { q: q, ctx: g.text, ctxName: g.name };
      if (cxt) cxt.textContent = "📄 " + (g.name || "（当前位置）");
      if (online) {
        status("问模型中...");
        askModel(q, g.text).then(function (r) {
          if (r && r.ok && r.a) { ans.innerHTML = renderModel(r); status("模型回答 · 已压缩上下文", "on"); }
          else { offlineFallback(q, r && r.error); }
        }).catch(function () { offlineFallback(q); });
      } else {
        offlineFallback(q);
      }
    }
    function offlineFallback(q, why) {
      var hits = find(q);
      if (!hits.length) {
        ans.innerHTML = '<div class="empty">题库里没有这一条，先别急：<br>1) 点右下角「问」旁边的 <b>复制问题</b>，把它发给你的 AI（内容会带上当前章节）；<br>2) 或者打开 <a href="ask.html">独立提问页</a> 粘贴这段内容来问。<br>' +
          (why ? '<span class="hint">（服务端提示：' + esc(why) + "）</span>" : "");
        status("离线题库 · 未命中", "warn");
        return;
      }
      ans.innerHTML = hits.map(function (e, i) { return cardHtml(e, i ? "small" : ""); }).join("");
      if (hits.length > 1) ans.innerHTML += '<div class="src">↑ 主答案 + ' + (hits.length - 1) + " 条相关的</div>";
      status("离线题库", "");
    }
    function copy() {
      var txt = "我在读讲义《" + (CFG.title || "") + "》的「" + (last.ctxName || grabView().name) + "」这一节，\n问：" +
        (qIn.value.trim() || "（问题）") + "\n\n这一节的内容：\n" + (last.ctx || grabView().text);
      (navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject())
        .then(function () { status("已复制，去粘贴给 AI", "on"); })
        .catch(function () { window.prompt("复制下面的内容：", txt); });
    }
    dockbtn && dockbtn.addEventListener("click", function () { dock.classList.toggle("open"); if (dock.classList.contains("open")) qIn.focus(); });
    var x = document.getElementById("x"); x && x.addEventListener("click", function () { dock.classList.remove("open"); });
    var gob = document.getElementById("go"); gob && gob.addEventListener("click", go);
    qIn && qIn.addEventListener("keydown", function (e) { if (e.key === "Enter") go(); });
    var cb = document.getElementById("copy"); cb && cb.addEventListener("click", copy);
    var gb = document.getElementById("grab"); gb && gb.addEventListener("click", function () {
      var g = grabView();
      if (cxt) cxt.textContent = "📄 " + (g.name || "（当前位置）");
      status("已读取当前章节", "on");
    });
    document.getElementById("n-open") && document.getElementById("n-open").addEventListener("click", function () {
      document.body.classList.remove("hidenotes");
      [].forEach.call(document.querySelectorAll("aside.nq details"), function (d) { d.open = true; });
    });
    document.getElementById("n-close") && document.getElementById("n-close").addEventListener("click", function () {
      [].forEach.call(document.querySelectorAll("aside.nq details"), function (d) { d.open = false; });
    });
    document.getElementById("n-hide") && document.getElementById("n-hide").addEventListener("click", function () {
      document.body.classList.toggle("hidenotes");
    });
    if (location.hash === "#ask") { dock.classList.add("open"); qIn.focus(); }
  }

  /* ---------- standalone ask page ---------- */
  var out = document.getElementById("out");
  if (out) {
    var ctxIn = document.getElementById("ctx"), q2 = document.getElementById("qq"),
      go2 = document.getElementById("go2"), paste = document.getElementById("paste"),
      clear = document.getElementById("clear"), bar = document.getElementById("bar"),
      bartxt = document.getElementById("bartxt"), dot = document.getElementById("dot");

    function setBar(txt, cls) {
      if (bartxt) bartxt.textContent = txt;
      if (dot) dot.className = "dot" + (cls ? " " + cls : "");
    }
    ping().then(function (r) {
      if (r && r.ok) { online = true; setBar("本地服务已连上 · " + (r.mode === "model" ? "模型模式" : "题库模式（" + (r.bank || 0) + " 条）"), "on"); }
      else { online = false; setBar("没连上本地服务：先运行  python -m lecture_forge serve", "warn"); }
    });

    function submit() {
      var q = (q2.value || "").trim();
      if (!q) { q2.focus(); return; }
      var ctx = (ctxIn.value || "").trim();
      out.innerHTML = "";
      out.insertAdjacentHTML("beforeend", '<div class="card ask"><div class="q">' + esc(q) + "</div>" +
        (ctx ? '<div class="src">附带了 ' + ctx.length + " 字的材料</div>" : '<div class="src">没有附带材料</div>') + "</div>");
      if (!online) {
        out.insertAdjacentHTML("beforeend", '<div class="card err">本地服务没启动，只能离线查题库。先运行 <code>python -m lecture_forge serve</code>。</div>');
        return;
      }
      go2.disabled = true;
      askModel(q, ctx).then(function (r) {
        go2.disabled = false;
        if (r && r.ok && r.a) {
          out.insertAdjacentHTML("beforeend", renderModel(r));
        } else {
          var hits = find(q);
          if (hits.length) out.insertAdjacentHTML("beforeend", hits.map(function (e) { return cardHtml(e); }).join(""));
          else out.insertAdjacentHTML("beforeend", '<div class="card err">没能回答：' + esc((r && r.error) || "模型没返回内容") + "</div>");
        }
      }).catch(function (e) {
        go2.disabled = false;
        out.insertAdjacentHTML("beforeend", '<div class="card err">请求失败：' + esc(String(e)) + "</div>");
      });
    }
    go2 && go2.addEventListener("click", submit);
    q2 && q2.addEventListener("keydown", function (e) { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submit(); });
    paste && paste.addEventListener("click", function () {
      (navigator.clipboard ? navigator.clipboard.readText() : Promise.reject())
        .then(function (t) { if (ctxIn) ctxIn.value = t; })
        .catch(function () { alert("浏览器不允许直接读剪贴板，请手动 Ctrl+V 粘贴。"); });
    });
    clear && clear.addEventListener("click", function () {
      if (ctxIn) ctxIn.value = ""; if (q2) q2.value = ""; out.innerHTML = ""; setBar("等你提问", "");
    });
  }
})();
