// Tekken 8 Trainer UI. All page text is set with textContent (never innerHTML).
(function () {
  "use strict";

  const E = window.T8Engine;
  const I = window.T8Input;
  const TIMING = { justFrames: T8_TIMING.justFrames, fastWR: T8_TIMING.fastWR };
  const MASTER_STREAK = 10;

  // ---------- small helpers ----------
  const $ = (sel, root) => (root || document).querySelector(sel);
  function el(tag, props, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (v === undefined || v === null || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) {
      if (kid === null || kid === undefined || kid === false) continue;
      n.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return n;
  }
  const clamp = (v, a, b, d) => (Number.isFinite(+v) ? Math.min(b, Math.max(a, Math.round(+v))) : d);

  const store = {
    get(k, def) {
      try { const v = localStorage.getItem("t8t." + k); return v ? JSON.parse(v) : def; } catch { return def; }
    },
    set(k, v) { try { localStorage.setItem("t8t." + k, JSON.stringify(v)); } catch { /* storage off */ } },
  };

  // ---------- settings ----------
  const DEFAULTS = {
    keys: Object.assign({}, I.DEFAULT_KEYS), side: "p1", socdLR: "neutral", socdUD: "up",
    simulWindow: 1, stringWindow: 30, moveWindow: 45, punishWindow: 40, sound: true, cue: false,
  };
  function loadSettings() {
    const s = Object.assign({}, DEFAULTS, store.get("settings", {}));
    const keys = Object.assign({}, I.DEFAULT_KEYS);
    for (const k of Object.keys(keys)) {
      const v = s.keys && s.keys[k];
      if (typeof v === "string" && /^[A-Za-z0-9]{0,24}$/.test(v)) keys[k] = v;  // "" = unbound
    }
    return {
      keys,
      side: s.side === "p2" ? "p2" : "p1",
      socdLR: ["neutral", "last"].includes(s.socdLR) ? s.socdLR : "neutral",
      socdUD: ["up", "neutral", "last"].includes(s.socdUD) ? s.socdUD : "up",
      simulWindow: clamp(s.simulWindow, 0, 3, 1),
      stringWindow: clamp(s.stringWindow, 10, 60, 30),
      moveWindow: clamp(s.moveWindow, 20, 90, 45),
      punishWindow: clamp(s.punishWindow, 15, 90, 40),
      sound: !!s.sound, cue: !!s.cue,
    };
  }
  let settings = loadSettings();
  const saveSettings = () => { store.set("settings", settings); input.setConfig(settings); };
  const matcherOpts = () => ({
    simulWindow: settings.simulWindow, stringWindow: settings.stringWindow,
    moveWindow: settings.moveWindow, timing: TIMING,
  });

  // ---------- sound ----------
  let actx = null;
  const cueNodes = [];
  function tone(freq, dur, when, vol) {
    if (!settings.sound) return null;
    try {
      actx = actx || new AudioContext();
      const o = actx.createOscillator(), g = actx.createGain();
      o.frequency.value = freq;
      g.gain.value = vol || 0.07;
      o.connect(g).connect(actx.destination);
      const t = actx.currentTime + (when || 0);
      o.start(t);
      o.stop(t + dur);
      return o;
    } catch { return null; }
  }
  const sfx = {
    ok: () => { tone(660, 0.08); tone(990, 0.1, 0.08); },
    fail: () => tone(180, 0.2),
    step: () => tone(520, 0.03, 0, 0.03),
  };
  function stopCues() { while (cueNodes.length) { try { cueNodes.pop().stop(); } catch { /* done */ } } }

  // ---------- direction display ----------
  const ARROW = { n: "★", u: "↑", d: "↓", f: "→", b: "←", uf: "↗", ub: "↖", df: "↘", db: "↙" };

  // Tekken-style input history: one row per change, with frames held.
  class History {
    constructor(parent) {
      this.box = el("ol", { class: "history", "aria-label": "Input history" });
      parent.append(el("div", { class: "history-wrap" }, el("h3", { text: "Input display" }), this.box));
      this.rows = [];
    }
    add(frame, dir, btns) {
      const top = this.rows[0];
      if (top && top.f === frame && btns && top.dir === dir) {
        btns.forEach((b) => top.btns.add(b));
      } else {
        this.rows.unshift({ f: frame, dir, btns: new Set(btns || []) });
        if (this.rows.length > 16) this.rows.pop();
      }
      this.dirty = true;
    }
    clear() { this.rows = []; this.dirty = true; }
    render(now) {
      if (!this.dirty && !this.rows.length) return;
      if (this.dirty) {
        this.box.replaceChildren(...this.rows.map(() =>
          el("li", {}, el("span", { class: "fr" }), el("span", { class: "dir" }), el("span", { class: "btns" }))));
        this.dirty = false;
      }
      this.rows.forEach((r, i) => {
        const li = this.box.children[i];
        if (!li) return;
        const end = i === 0 ? now : this.rows[i - 1].f;
        li.children[0].textContent = String(Math.max(0, end - r.f) || 1).padStart(3, " ");
        li.children[1].textContent = ARROW[r.dir] || r.dir;
        li.children[2].textContent = [...r.btns].sort().join("+");
      });
    }
  }

  // ---------- stats ----------
  function stat(id) {
    const s = store.get("stat." + id, null) || {};
    return { a: s.a | 0, s: s.s | 0, streak: s.streak | 0, best: s.best | 0,
             drops: s.drops && typeof s.drops === "object" ? s.drops : {},
             ref: Array.isArray(s.ref) ? s.ref : null };
  }
  const saveStat = (id, s) => store.set("stat." + id, s);
  const pct = (s) => (s.a ? Math.round((100 * s.s) / s.a) + "%" : "—");

  // ---------- practice panel (combos, drills, single moves) ----------
  class Practice {
    constructor(root, onStats) {
      this.root = root;
      this.onStats = onStats || (() => {});
      this.item = null;
      this.m = null;
      this.dirLog = [{ f: -1e9, d: "n" }];
      this.waitUntil = 0;
      this.build();
    }

    build() {
      this.title = el("h2");
      this.meta = el("div", { class: "meta" });
      this.chips = el("div", { class: "chips", "aria-live": "polite" });
      this.status = el("p", { class: "status", "aria-live": "polite" });
      this.result = el("div", { class: "result" });
      this.statLine = el("p", { class: "statline" });
      this.cueBox = el("input", { type: "checkbox", id: this.root.id + "-cue",
        onchange: () => { settings.cue = this.cueBox.checked; saveSettings(); } });
      this.controls = el("div", { class: "controls" },
        el("button", { text: "Reset (Space)", onclick: () => this.reset() }),
        el("button", { text: "Save last run as my timing", onclick: () => this.saveRef() }),
        el("button", { text: "Clear my timing", onclick: () => this.clearRef() }),
        el("label", { class: "check" }, this.cueBox, " Beep my timing (rhythm)"),
        el("button", { class: "ghost", text: "Reset stats", onclick: () => this.resetStats() }));
      const left = el("div", { class: "practice-main" }, this.title, this.meta, this.chips, this.status,
        this.result, this.statLine, this.controls);
      this.root.append(left);
      this.history = new History(this.root);
      this.root.append(el("p", { class: "empty", text: "Pick something from the list." }));
      left.hidden = true;
      this.left = left;
    }

    load(item) {
      this.item = item;
      this.root.querySelector(".empty")?.remove();
      this.left.hidden = false;
      this.title.textContent = item.name;
      const meta = [];
      if (item.level) meta.push(el("span", { class: "tag lv-" + item.level, text: item.level }));
      if (item.damage) meta.push(el("span", { class: "tag", text: "Damage " + item.damage }));
      if (item.src) meta.push(el("span", { class: "tag src", text: "Source: " + item.src }));
      this.meta.replaceChildren(el("div", { class: "tags" }, meta),
        item.when ? el("p", {}, el("b", { text: "When: " }), item.when) : null,
        item.tips ? el("p", {}, el("b", { text: "Tips: " }), item.tips) : null,
        el("p", { class: "notation" }, el("b", { text: "Notation: " }), el("code", { text: item.notation })));
      try {
        this.steps = E.parse(item.notation, TIMING);
      } catch (err) {
        this.steps = null;
        this.status.textContent = "This input can't be practised here yet: " + err.message;
        this.chips.replaceChildren();
        return;
      }
      this.cueBox.checked = settings.cue;
      this.reset();
    }

    reset() {
      stopCues();
      if (!this.steps) return;
      this.m = new E.Matcher(this.steps, matcherOpts());
      const now = input.now();
      this.m.hist = this.dirLog.filter((e) => e.f >= now - 30 || e === this.dirLog[this.dirLog.length - 1])
        .map((e) => ({ f: e.f, d: e.d }));
      this.shownState = null;
      this.cued = false;
      this.status.textContent = "Ready. Start the combo whenever you want.";
      this.status.className = "status";
      this.renderChips();
      this.renderStats();
    }

    renderChips() {
      const m = this.m;
      const groups = [];
      this.steps.forEach((s, i) => {
        let cls = "chip";
        if (i < m.idx) cls += " done";
        else if (i === m.idx && m.state === "fail") cls += " bad";
        else if (i === m.idx && m.state !== "done") cls += " now";
        if (s.link === ":" || s.fast) cls += " jf";
        const mk = s.markers && s.markers.length ? el("span", { class: "mk", text: s.markers.join(" ") }) : null;
        const chip = el("span", { class: cls, title: chipHelp(s) }, mk, s.label.replace(/^,/, ""));
        const last = groups[groups.length - 1];
        if (last && last.tok === s.tok) last.node.append(chip);
        else groups.push({ tok: s.tok, node: el("span", { class: "tok" }, chip) });
      });
      this.chips.replaceChildren(...groups.map((g) => g.node));
    }

    renderStats() {
      if (!this.item) return;
      const s = stat(this.item.id);
      const mastered = s.best >= MASTER_STREAK;
      this.statLine.textContent =
        `Success ${pct(s)} (${s.s}/${s.a}) · streak ${s.streak} · best streak ${s.best}` +
        (mastered ? " · ★ mastered" : ` · ${MASTER_STREAK} in a row to master`) +
        (s.ref ? " · my timing saved" : "");
    }

    handle(ev) {
      if (!this.m) return;
      if (ev.type === "reset") return this.reset();
      if (ev.type === "dir") {
        this.dirLog.push({ f: ev.frame, d: ev.dir });
        if (this.dirLog.length > 32) this.dirLog.shift();
        this.history.add(ev.frame, ev.dir, null);
      }
      if (ev.type === "press") this.history.add(ev.frame, input.dir, [ev.btn]);
      if (ev.type !== "dir" && ev.type !== "press") return;

      if (this.m.state === "done" || this.m.state === "fail") {
        if (performance.now() < this.waitUntil) return;
        if (ev.type === "press") this.reset(); else return;
        // reset() already copied the direction log, so only feed the press.
      }
      const before = this.m.idx;
      if (ev.type === "dir") this.m.dir(ev.frame, ev.dir);
      else this.m.press(ev.frame, ev.btn);
      if (this.m.state === "running" && !this.cued) this.startCue();
      this.after(before);
    }

    tick(frame) {
      if (!this.m) return;
      const before = this.m.idx;
      this.m.tick(frame);
      this.after(before);
      this.history.render(frame);
    }

    after(before) {
      const m = this.m;
      if (m.idx !== before || m.state !== this.shownState) {
        if (m.idx > before && m.state === "running") sfx.step();
        this.renderChips();
      }
      if (m.state === this.shownState) return;
      this.shownState = m.state;
      if (m.state === "running") {
        this.status.textContent = "Go…";
        this.status.className = "status";
      } else if (m.state === "done") {
        this.finish(true);
      } else if (m.state === "fail") {
        this.finish(false);
      }
    }

    gaps() { return this.m.results.map((r) => r.gap); }

    finish(ok) {
      stopCues();
      const s = stat(this.item.id);
      s.a++;
      if (ok) { s.s++; s.streak++; s.best = Math.max(s.best, s.streak); sfx.ok(); }
      else { s.streak = 0; s.drops[this.m.idx] = (s.drops[this.m.idx] | 0) + 1; sfx.fail(); }
      saveStat(this.item.id, s);
      this.lastGaps = ok ? this.gaps() : null;
      this.waitUntil = performance.now() + 350;

      const step = this.steps[this.m.idx];
      this.status.className = "status " + (ok ? "good" : "bad");
      this.status.textContent = ok
        ? (s.streak >= MASTER_STREAK && s.streak === s.best ? `Clean! ${s.streak} in a row. ★` : `Clean! Streak ${s.streak}.`)
        : `Dropped at "${step ? step.label : "?"}": ${this.m.error.msg}`;
      this.renderResult(ok, s);
      this.renderStats();
      this.onStats();
    }

    renderResult(ok, s) {
      const ref = s.ref && s.ref.length === this.steps.length ? s.ref : null;
      const rows = this.m.results.map((r, i) => {
        const st = this.steps[i];
        const d = ref && i > 0 ? r.gap - ref[i] : null;
        return el("tr", {},
          el("td", { text: st.label }),
          el("td", { text: i === 0 ? "start" : r.gap + "f" }),
          el("td", { text: ref && i > 0 ? ref[i] + "f" : "" }),
          el("td", { class: d === null ? "" : Math.abs(d) <= 2 ? "good" : "warn",
                     text: d === null ? "" : (d > 0 ? "+" : "") + d + "f" + (d > 0 ? " late" : d < 0 ? " early" : "") }));
      });
      const worst = Object.entries(s.drops).sort((a, b) => b[1] - a[1])[0];
      this.result.replaceChildren(
        el("table", { class: "gaps" },
          el("thead", {}, el("tr", {}, el("th", { text: "Step" }), el("th", { text: "Gap" }),
            el("th", { text: ref ? "My timing" : "" }), el("th", { text: ref ? "Diff" : "" }))),
          el("tbody", {}, rows)),
        ...[worst && el("p", { class: "hint", text:
          `You drop most at step ${+worst[0] + 1} ("${this.steps[worst[0]]?.label ?? "?"}"): ${worst[1]} times.` })].filter(Boolean));
    }

    saveRef() {
      if (!this.lastGaps) { this.status.textContent = "Do a clean run first, then save it."; return; }
      const s = stat(this.item.id);
      s.ref = this.lastGaps;
      saveStat(this.item.id, s);
      this.status.textContent = "Saved. Only save a timing that worked in the real game.";
      this.renderStats();
    }

    clearRef() {
      const s = stat(this.item.id);
      s.ref = null;
      saveStat(this.item.id, s);
      this.renderStats();
    }

    resetStats() {
      if (!this.item || !confirm(`Reset stats for "${this.item.name}"?`)) return;
      store.set("stat." + this.item.id, null);
      this.renderStats();
      this.onStats();
    }

    // Beep the saved rhythm, starting from the first input.
    startCue() {
      this.cued = true;
      if (!settings.cue) return;
      const s = stat(this.item.id);
      if (!s.ref || s.ref.length !== this.steps.length) return;
      let t = 0;
      for (let i = 1; i < s.ref.length; i++) {
        t += s.ref[i] * I.FRAME_MS / 1000;
        const o = tone(880, 0.04, t, 0.05);
        if (o) cueNodes.push(o);
      }
    }
  }

  function chipHelp(s) {
    const parts = [];
    if (s.kind === "dirs") parts.push("Direction only: " + s.seq.join(", ").replace(/\*/g, " (any)"));
    else {
      parts.push("Buttons " + s.btns.join("+"));
      if (s.dir === "n") parts.push("no direction held");
      else if (s.dir === "ws") parts.push("while standing up from crouch");
      else if (s.dir !== "*") parts.push("hold " + s.dir);
      if (s.motion) parts.push("motion " + s.motion.join(","));
      if (s.jf) parts.push(`just frame: ${s.jf[0]}-${s.jf[1]} frames after the last press`);
      if (s.fast) parts.push(`whole motion within ${s.fast} frames`);
    }
    return parts.join(" · ");
  }

  // ---------- lists (combos, drills) ----------
  function renderList(listEl, items, practice, filter) {
    const shown = filter ? filter(items) : items;
    if (!shown.length) {
      listEl.replaceChildren(el("li", { class: "hint", text: "Nothing here yet. Practise a few combos first (3+ tries each)." }));
      return;
    }
    listEl.replaceChildren(...shown.map((it) => {
      const s = stat(it.id);
      const li = el("li", { class: practice.item && practice.item.id === it.id ? "sel" : "" },
        el("button", { onclick: () => { practice.load(it); renderList(listEl, items, practice, filter); } },
          it.level ? el("span", { class: "tag lv-" + it.level, text: it.level[0].toUpperCase() }) : null,
          el("span", { class: "nm", text: it.name }),
          el("span", { class: "pc", text: (s.best >= MASTER_STREAK ? "★ " : "") + pct(s) })));
      return li;
    }));
  }

  // ---------- punish trainer ----------
  const NICE = { "jack-8": "Jack-8", "devil-jin": "Devil Jin", "armor-king": "Armor King", "miary-zo": "Miary Zo" };
  const charName = (c) => NICE[c] || c.charAt(0).toUpperCase() + c.slice(1);
  const levelWord = { h: "high", m: "mid", l: "low", s: "special mid" };
  const isLowEnd = (lv) => lv.split(",").pop().trim().toLowerCase().startsWith("l");

  class Punish {
    constructor(root) {
      this.root = root;
      this.state = "idle";
      this.score = store.get("punish", { a: 0, s: 0, streak: 0, best: 0 });
      this.build();
    }

    build() {
      const chars = [...new Set(T8_PUNISH.map((m) => m.c))].sort();
      this.charSel = el("select", { "aria-label": "Opponent" },
        el("option", { value: "", text: "All characters" }),
        chars.map((c) => el("option", { value: c, text: charName(c) })));
      this.safeBox = el("input", { type: "checkbox", checked: true });
      this.card = el("div", { class: "pcard" });
      this.msg = el("p", { class: "status", "aria-live": "polite" });
      this.answer = el("div", { class: "answer" });
      this.scoreLine = el("p", { class: "statline" });
      this.root.append(
        el("div", { class: "punish-top" },
          el("p", { class: "hint", text:
            "An opponent move gets blocked. Punish it with Dragunov as fast as you can. " +
            "If the move is safe (-9 or better), don't press anything: keep blocking. " +
            "Lows are blocked crouching, so hold down before the block and use a ws punisher." }),
          el("div", { class: "controls" }, this.charSel,
            el("label", { class: "check" }, this.safeBox, " Include safe moves"),
            el("button", { text: "Next (Space)", onclick: () => this.next() }))),
        this.card, this.msg, this.answer, this.scoreLine,
        el("p", { class: "hint", text:
          "Note: pushback and range are not simulated. Some punishers can whiff in the real game." }));
      this.history = new History(this.root);
      this.renderScore();
      this.card.append(el("p", { class: "empty", text: "Press Space or Next to start." }));
    }

    pool() {
      const c = this.charSel.value;
      return T8_PUNISH.filter((m) => (!c || m.c === c) && (this.safeBox.checked || m.b <= -10));
    }

    options(t) {
      const stance = isLowEnd(t.lv) ? "crouch" : "stand";
      return T8_PUNISHERS.filter((p) => p.stance === stance && p.i <= -t.b);
    }

    next() {
      const pool = this.pool();
      if (!pool.length) return;
      this.t = pool[Math.floor(Math.random() * pool.length)];
      this.opts = this.options(this.t);
      const now = input.now();
      this.blockAt = now + 40 + Math.floor(Math.random() * 50);
      this.matchers = this.opts.map((p) => {
        const m = new E.Matcher(E.parse(p.notation, TIMING), Object.assign(matcherOpts(), { moveWindow: settings.punishWindow }));
        m.hist = [{ f: input.dirSince, d: input.dir }];
        return { p, m };
      });
      this.state = "incoming";
      this.pressed = false;
      this.history.clear();
      const lv = this.t.lv.split(",").map((x) => levelWord[x.trim().toLowerCase()[0]] || x).join(", ");
      this.card.replaceChildren(
        el("div", { class: "who", text: charName(this.t.c) }),
        el("div", { class: "cmd", text: this.t.cmd }),
        el("div", { class: "nm", text: this.t.n || "" }),
        el("div", { class: "fd" },
          el("span", { text: "i" + this.t.i }), el("span", { text: lv }),
          el("span", { class: "blk", text: (this.t.b > 0 ? "+" : "") + this.t.b + " on block" })),
        el("div", { class: "phase", text: "Incoming…" }));
      this.msg.textContent = isLowEnd(this.t.lv) ? "It ends with a low: hold down to block it." : "Block it…";
      this.msg.className = "status";
      this.answer.replaceChildren();
    }

    handle(ev) {
      if (ev.type === "reset") return this.state === "incoming" || this.state === "window" ? null : this.next();
      if (ev.type === "dir") this.history.add(ev.frame, ev.dir, null);
      if (ev.type === "press") this.history.add(ev.frame, input.dir, [ev.btn]);
      if (this.state !== "incoming" && this.state !== "window") return;
      if (ev.type === "press") {
        if (ev.frame < this.blockAt - T8_TIMING.inputBuffer) {
          return this.end(false, "Too early: you pressed during their attack (more than 8 frames before it ended).");
        }
        this.pressed = true;
        if (!this.opts.length) {
          return this.end(false, `That move is only ${this.t.b} on block: it's safe. Pressing there gets you counter-hit.`);
        }
      }
      for (const { m } of this.matchers) {
        if (ev.type === "dir") m.dir(ev.frame, ev.dir);
        else if (ev.type === "press") m.press(ev.frame, ev.btn);
      }
      this.check(ev.frame);
    }

    tick(frame) {
      this.history.render(frame);
      if (this.state === "incoming" && frame >= this.blockAt) {
        this.state = "window";
        const low = isLowEnd(this.t.lv);
        const crouching = input.dir.includes("d");
        const first = this.t.lv.split(",")[0].trim().toLowerCase()[0];
        if (low && !crouching) return this.end(false, "The low hit you: hold down to block lows.");
        if (!low && crouching && first === "m") return this.end(false, "The mid hit you: don't crouch against mids.");
        $(".phase", this.card).textContent = "BLOCKED! Punish!";
        this.card.classList.add("flash");
      }
      if (this.state !== "window") return;
      for (const { m } of this.matchers) m.tick(frame);
      this.check(frame);
      if (this.state === "window" && frame > this.blockAt + settings.punishWindow) {
        if (!this.opts.length && !this.pressed) this.end(true, `Right: ${this.t.b} on block is safe. You kept blocking.`);
        else if (!this.pressed) this.end(false, `Too slow: no punish within ${settings.punishWindow} frames.`);
      }
    }

    check(frame) {
      if (this.state !== "window" && this.state !== "incoming") return;
      const won = this.matchers.find(({ m }) => m.state === "done");
      if (won) {
        const start = won.m.results[0].frame;
        const late = start - this.blockAt;
        if (late > settings.punishWindow) return this.end(false, `Right move (${won.p.notation}), but too late: ${late}f.`);
        const best = Math.max(...this.opts.map((o) => o.i));
        return this.end(true, won.p.i === best
          ? `Best punish: ${won.p.notation} (i${won.p.i}).`
          : `Punished with ${won.p.notation} (i${won.p.i}). A stronger one fits here, see below.`);
      }
      if (this.pressed && this.matchers.every(({ m }) => m.state === "fail")) {
        const err = this.matchers[0].m.error;
        this.end(false, "Not a punisher here. " + (err ? "(" + err.msg + ")" : ""));
      }
    }

    end(ok, text) {
      this.state = "result";
      this.card.classList.remove("flash");
      const ph = $(".phase", this.card);
      if (ph) ph.textContent = ok ? "✔" : "✘";
      this.msg.textContent = text;
      this.msg.className = "status " + (ok ? "good" : "bad");
      ok ? sfx.ok() : sfx.fail();
      const sc = this.score;
      sc.a++;
      if (ok) { sc.s++; sc.streak++; sc.best = Math.max(sc.best, sc.streak); } else sc.streak = 0;
      store.set("punish", sc);
      this.renderScore();
      const best = this.opts.length ? Math.max(...this.opts.map((o) => o.i)) : null;
      this.answer.replaceChildren(this.opts.length
        ? el("div", {},
            el("p", { text: `Punishers for ${this.t.b} (${isLowEnd(this.t.lv) ? "crouching" : "standing"}):` }),
            el("ul", {}, this.opts.slice().sort((a, b) => b.i - a.i).map((o) =>
              el("li", { class: o.i === best ? "best" : "" },
                el("code", { text: o.notation }), ` i${o.i} · ${o.note}${o.i === best ? " (best)" : ""}`))))
        : el("p", { text: "No punish: Dragunov's fastest punisher is i10, so -9 or better is safe." }));
    }

    renderScore() {
      const s = this.score;
      this.scoreLine.textContent = `Score ${pct(s)} (${s.s}/${s.a}) · streak ${s.streak} · best ${s.best}`;
    }
  }

  // ---------- moves tab ----------
  function renderGuide() {
    $("#guide").replaceChildren(...T8_GUIDE.map((g) =>
      el("div", { class: "gcard" }, el("h3", { text: g.title }), el("ul", {}, g.points.map((p) => el("li", { text: p }))))));
  }

  function renderMoves() {
    const q = $("#move-search").value.trim().toLowerCase();
    const lv = $("#move-level").value;
    const sort = $("#move-sort").value;
    const num = (s) => { const m = String(s).match(/[+-]?\d+/); return m ? +m[0] : null; };
    let rows = T8_MOVES.filter((m) => {
      if (lv && !m.hitLevel.trim().toLowerCase().startsWith(lv)) return false;
      if (!q) return true;
      return [m.command, m.name, m.notes, m.startup].some((x) => x.toLowerCase().includes(q));
    });
    if (sort === "startup") rows = rows.slice().sort((a, b) => (num(a.startup) ?? 999) - (num(b.startup) ?? 999));
    if (sort === "block") rows = rows.slice().sort((a, b) => (num(b.block) ?? -999) - (num(a.block) ?? -999));
    const body = $("#moves-table tbody");
    body.replaceChildren(...rows.map((m) => {
      let ok = true;
      try { E.parse(m.command, TIMING); } catch { ok = false; }
      const tr = el("tr", {},
        el("td", {}, el("code", { text: m.command })), el("td", { text: m.name }),
        el("td", { text: m.hitLevel }), el("td", { text: m.startup }), el("td", { text: m.block }),
        el("td", { text: m.hit }), el("td", { text: m.counterHit }), el("td", { text: m.damage }),
        el("td", {}, ok ? el("button", { class: "small", text: "Drill", onclick: () => drillMove(m) }) : null));
      const notes = m.notes ? el("tr", { class: "notes" }, el("td", { colspan: 9, text: m.notes.replace(/\n/g, "  ") })) : null;
      return notes ? [tr, notes] : [tr];
    }).flat());
  }

  function drillMove(m) {
    showTab("drills");
    drillPractice.load({ id: "move:" + m.command, name: m.command + (m.name ? " · " + m.name : ""),
      notation: m.command, tips: m.notes ? m.notes.split("\n").slice(0, 3).join(" ") : "",
      src: "TekkenDocs frame data" });
  }

  // ---------- setup tab ----------
  const KEY_NAMES = { up: "Up", down: "Down", left: "Left", right: "Right",
    b1: "1 (left punch)", b2: "2 (right punch)", b3: "3 (left kick)", b4: "4 (right kick)", reset: "Reset / next" };

  function renderSetup() {
    const root = $("#setup");
    const lights = {};
    const tester = el("div", { class: "tester" },
      ...["up", "down", "left", "right", "b1", "b2", "b3", "b4"].map((k) => {
        lights[k] = el("span", { class: "light", text: KEY_NAMES[k].split(" ")[0] });
        return lights[k];
      }));
    const maxLine = el("p", { class: "statline", text: "Most keys held at once: 0" });
    const dirLine = el("p", { class: "bigdir", text: "★" });
    setupState = { lights, maxLine, dirLine, max: 0 };

    const keyRows = Object.keys(KEY_NAMES).map((k) => {
      const b = el("button", { text: I.keyLabel(settings.keys[k]) });
      b.addEventListener("click", () => {
        b.textContent = "Press a key…";
        input.capture = (code) => {
          if (code !== "Escape" && /^[A-Za-z0-9]{1,24}$/.test(code)) {
            for (const [other, c] of Object.entries(settings.keys)) if (c === code && other !== k) settings.keys[other] = "";
            settings.keys[k] = code;
            saveSettings();
          }
          renderSetup();
        };
      });
      return el("tr", {}, el("td", { text: KEY_NAMES[k] }), el("td", {}, b));
    });

    const sel = (name, opts, label) => el("label", { class: "row" }, label + " ",
      el("select", { onchange: (e) => { settings[name] = e.target.value; saveSettings(); } },
        opts.map(([v, t]) => el("option", { value: v, text: t, selected: settings[name] === v }))));
    const numIn = (name, min, max, label) => el("label", { class: "row" }, label + " ",
      el("input", { type: "number", min, max, value: settings[name],
        onchange: (e) => { settings[name] = clamp(e.target.value, min, max, DEFAULTS[name]); e.target.value = settings[name]; saveSettings(); } }));

    root.replaceChildren(
      el("div", { class: "setup-grid" },
        el("div", {},
          el("h2", { text: "Key test" }),
          el("p", { class: "hint", text: "Hold your keys here. Check that 3–4 keys at once all light up (anti-ghosting). Example: S + D + U + I." }),
          tester, dirLine, maxLine,
          el("button", { text: "Reset counter", onclick: () => { setupState.max = 0; maxLine.textContent = "Most keys held at once: 0"; } })),
        el("div", {},
          el("h2", { text: "Keys" }),
          el("p", { class: "hint", text: "Use the same keys as in Tekken 8 so the muscle memory carries over." }),
          el("table", { class: "keys" }, el("tbody", {}, keyRows)),
          el("button", { class: "ghost", text: "Default keys (WASD + UIJK)", onclick: () => {
            settings.keys = Object.assign({}, I.DEFAULT_KEYS); saveSettings(); renderSetup(); } })),
        el("div", {},
          el("h2", { text: "Rules" }),
          sel("side", [["p1", "Left side (right key = forward)"], ["p2", "Right side (left key = forward)"]], "Side:"),
          sel("socdLR", [["neutral", "Neutral"], ["last", "Last pressed wins"]], "Left + Right together:"),
          sel("socdUD", [["up", "Up"], ["neutral", "Neutral"], ["last", "Last pressed wins"]], "Up + Down together:"),
          el("p", { class: "hint", text: "Set these to match your Tekken 8 settings. The game's own keyboard rule was not confirmed in the sources." }),
          numIn("simulWindow", 0, 3, "1+2 window (frames apart allowed):"),
          numIn("stringWindow", 10, 60, "Max gap inside a string (frames):"),
          numIn("moveWindow", 20, 90, "Max gap between moves (frames):"),
          numIn("punishWindow", 15, 90, "Punish time limit (frames):"),
          el("label", { class: "row check" },
            el("input", { type: "checkbox", checked: settings.sound,
              onchange: (e) => { settings.sound = e.target.checked; saveSettings(); } }), " Sounds"))));
  }
  let setupState = null;

  function setupHandle(ev) {
    if (!setupState) return;
    if (ev.type === "keys") {
      for (const [k, n] of Object.entries(setupState.lights)) n.classList.toggle("on", ev.held.has(k));
      setupState.max = Math.max(setupState.max, ev.held.size);
      setupState.maxLine.textContent = "Most keys held at once: " + setupState.max;
    }
    if (ev.type === "dir") setupState.dirLine.textContent = ARROW[ev.dir] || ev.dir;
  }

  // ---------- tabs & wiring ----------
  let tab = "combos";
  function showTab(name) {
    tab = name;
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
    document.querySelectorAll(".tab").forEach((s) => s.classList.toggle("active", s.id === "tab-" + name));
    store.set("tab", name);
    if (name === "setup") renderSetup();
  }

  const input = new I.KeyInput((ev) => {
    if (ev.type === "dir") input.dirSince = ev.frame;
    if (tab === "combos") comboPractice.handle(ev);
    else if (tab === "drills") drillPractice.handle(ev);
    else if (tab === "punish") punish.handle(ev);
    else if (tab === "setup") setupHandle(ev);
  });
  input.dirSince = 0;
  input.setConfig(settings);

  // Combos
  const LEVELS = ["all", "easy", "medium", "hard", "extreme", "weak"];
  let comboFilter = store.get("comboFilter", "all");
  if (!LEVELS.includes(comboFilter)) comboFilter = "all";
  const filterFn = () => (items) => {
    if (comboFilter === "all") return items;
    if (comboFilter === "weak") {
      return items.map((c) => [c, stat(c.id)]).filter(([, s]) => s.a >= 3)
        .sort((a, b) => a[1].s / a[1].a - b[1].s / b[1].a).slice(0, 8).map(([c]) => c);
    }
    return items.filter((c) => c.level === comboFilter);
  };
  const comboListEl = $("#combo-list");
  const drillListEl = $("#drill-list");
  const refreshLists = () => {
    renderList(comboListEl, T8_COMBOS, comboPractice, filterFn());
    renderList(drillListEl, T8_DRILLS, drillPractice, null);
  };
  const comboPractice = new Practice($("#combo-practice"), () => refreshLists());
  const drillPractice = new Practice($("#drill-practice"), () => refreshLists());
  const punish = new Punish($("#punish"));

  function renderFilters() {
    $("#combo-filters").replaceChildren(...LEVELS.map((lv) =>
      el("button", { class: lv === comboFilter ? "active" : "", text: lv === "weak" ? "Weak spots" : lv[0].toUpperCase() + lv.slice(1),
        onclick: () => { comboFilter = lv; store.set("comboFilter", lv); renderFilters(); refreshLists(); } })));
  }

  document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
  $("#move-search").addEventListener("input", renderMoves);
  $("#move-level").addEventListener("change", renderMoves);
  $("#move-sort").addEventListener("change", renderMoves);

  renderFilters();
  refreshLists();
  renderGuide();
  renderMoves();
  input.attach();
  const savedTab = store.get("tab", "combos");
  showTab(["combos", "drills", "punish", "moves", "setup", "about"].includes(savedTab) ? savedTab : "combos");

  (function loop() {
    const f = input.now();
    if (tab === "combos") comboPractice.tick(f);
    else if (tab === "drills") drillPractice.tick(f);
    else if (tab === "punish") punish.tick(f);
    requestAnimationFrame(loop);
  })();
})();
