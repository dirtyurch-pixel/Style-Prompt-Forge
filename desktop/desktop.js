/* Style Prompt Forge desktop bridge: saves to files on this PC and connects the Ask Claude buttons. */
(function(){
  window.FORGE_DESKTOP = true;
  var seed = __SEED__;
  var LS = window.localStorage, setI = Storage.prototype.setItem, rmI = Storage.prototype.removeItem;
  var hasSeed = seed && typeof seed === "object" && Object.keys(seed).length > 0;
  if (hasSeed) { try { Object.keys(seed).forEach(function(k){ if (typeof seed[k] === "string") setI.call(LS, k, seed[k]); }); } catch (e) {} }
  var timer = null;
  function push(){
    timer = null; var o = {};
    for (var i = 0; i < LS.length; i++) { var k = LS.key(i); if (/^forge/.test(k)) o[k] = LS.getItem(k); }
    fetch("/api/store", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(o), keepalive:true}).catch(function(){});
  }
  function later(){ if (!timer) timer = setTimeout(push, 700); }
  Storage.prototype.setItem = function(k, v){ setI.call(this, k, v); if (this === LS && /^forge/.test(k)) later(); };
  Storage.prototype.removeItem = function(k){ rmI.call(this, k); if (this === LS && /^forge/.test(k)) later(); };
  if (!hasSeed) setTimeout(push, 1500);
  window.addEventListener("pagehide", function(){ if (timer) { clearTimeout(timer); push(); } });

  var MARK = "\x1e";
  async function sample(input, opts){
    opts = opts || {};
    var r;
    try {
      r = await fetch("/api/sample", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({prompt:input}), signal:opts.signal});
    } catch (e) { throw {code: e && e.name === "AbortError" ? "cancelled" : "unavailable", message: "Couldn't reach the Forge app. Is it still running?"}; }
    if (!r.ok) { var m = ""; try { m = (await r.json()).error; } catch (e) {} throw {code: r.status === 400 ? "no_key" : "unavailable", message: m || "Couldn't reach Claude."}; }
    var rd = r.body.getReader(), dec = new TextDecoder(), raw = "";
    try {
      for (;;) {
        var x = await rd.read(); if (x.done) break;
        raw += dec.decode(x.value, {stream:true});
        var shown = raw.split(MARK)[0];
        if (opts.onText && shown) opts.onText({text: shown, delta: ""});
      }
    } catch (e) { throw {code: e && e.name === "AbortError" ? "cancelled" : "unavailable", message: "Stopped.", text: raw.split(MARK)[0]}; }
    var parts = raw.split(MARK), text = parts[0], info = {};
    try { info = JSON.parse(parts[1] || "{}"); } catch (e) {}
    if (info.error) throw {code: "unavailable", message: info.error, text: text};
    if (info.note) text += "\n\n[" + info.note + "]";
    if (typeof info.usd === "number") window.FORGE_LAST_COST = info;
    return {text: text, truncated: false};
  }
  window.claude = { use: async function(name){ return name === "sample" ? sample : null; } };
})();
