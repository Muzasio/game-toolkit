// Keyboard input: turns key presses into Tekken directions and buttons, timed in frames.
(function (root) {
  "use strict";

  const FRAME_MS = 1000 / 60;

  const DEFAULT_KEYS = {
    up: "KeyW", down: "KeyS", left: "KeyA", right: "KeyD",
    b1: "KeyU", b2: "KeyI", b3: "KeyJ", b4: "KeyK",
    reset: "Space",
  };

  class KeyInput {
    constructor(onEvent) {
      this.onEvent = onEvent;
      this.cfg = { keys: Object.assign({}, DEFAULT_KEYS), side: "p1", socdLR: "neutral", socdUD: "up" };
      this.t0 = performance.now();
      this.held = new Set();          // logical names held: up, down, left, right, b1..b4
      this.order = {};                // when each logical key went down (for "last input wins")
      this.dir = "n";
      this.enabled = true;
      this.capture = null;            // callback for "press a key to bind"
      this.onKey = this.onKey.bind(this);
      this.release = this.release.bind(this);
    }

    attach() {
      window.addEventListener("keydown", this.onKey, true);
      window.addEventListener("keyup", this.onKey, true);
      window.addEventListener("blur", this.release);
    }

    setConfig(cfg) {
      this.cfg = Object.assign({}, this.cfg, cfg, { keys: Object.assign({}, DEFAULT_KEYS, cfg.keys || {}) });
      this.release();
    }

    frameAt(ts) { return Math.floor((ts - this.t0) / FRAME_MS); }
    now() { return this.frameAt(performance.now()); }

    logicalFor(code) {
      for (const [name, c] of Object.entries(this.cfg.keys)) if (c === code) return name;
      return null;
    }

    release() {
      const f = this.now();
      for (const name of [...this.held]) {
        if (name.startsWith("b")) this.onEvent({ type: "release", frame: f, btn: Number(name[1]) });
      }
      this.held.clear();
      this.updateDir(f);
    }

    onKey(e) {
      if (this.capture && e.type === "keydown") {
        e.preventDefault();
        const cb = this.capture;
        this.capture = null;
        cb(e.code);
        return;
      }
      const t = e.target;
      if (t && (t.tagName === "INPUT" || t.tagName === "SELECT" || t.tagName === "TEXTAREA")) return;
      const name = this.logicalFor(e.code);
      if (!name || !this.enabled) return;
      e.preventDefault();
      if (e.repeat) return;
      // e.timeStamp shares its clock with performance.now().
      const ts = e.timeStamp > 1e12 ? performance.now() : e.timeStamp;
      const f = this.frameAt(ts);
      const down = e.type === "keydown";

      if (name === "reset") { if (down) this.onEvent({ type: "reset", frame: f }); return; }
      if (down) {
        if (this.held.has(name)) return;
        this.held.add(name);
        this.order[name] = ts;
      } else {
        if (!this.held.has(name)) return;
        this.held.delete(name);
      }
      if (name.startsWith("b")) {
        this.onEvent({ type: down ? "press" : "release", frame: f, btn: Number(name[1]) });
      } else {
        this.updateDir(f);
      }
      this.onEvent({ type: "keys", frame: f, held: new Set(this.held) });
    }

    axis(a, b, rule, both) {
      const ha = this.held.has(a), hb = this.held.has(b);
      if (ha && hb) {
        if (rule === "last") return this.order[a] > this.order[b] ? a : b;
        return both;                 // "neutral" -> null, "up" -> "up"
      }
      return ha ? a : hb ? b : null;
    }

    updateDir(f) {
      const v = this.axis("up", "down", this.cfg.socdUD, this.cfg.socdUD === "up" ? "up" : null);
      const h = this.axis("left", "right", this.cfg.socdLR, null);
      const fwd = this.cfg.side === "p1" ? "right" : "left";
      let d = (v === "up" ? "u" : v === "down" ? "d" : "") + (h === null ? "" : h === fwd ? "f" : "b");
      if (!d) d = "n";
      if (d !== this.dir) {
        this.dir = d;
        this.onEvent({ type: "dir", frame: f, dir: d });
      }
    }
  }

  // Short label for a key code: "KeyW" -> "W", "Space" -> "Space".
  function keyLabel(code) {
    if (!code) return "—";
    return code.replace(/^(Key|Digit)/, "").replace(/^Arrow/, "Arrow ");
  }

  root.T8Input = { KeyInput, DEFAULT_KEYS, FRAME_MS, keyLabel };
})(window);
