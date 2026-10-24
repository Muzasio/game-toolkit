// Notation parser and input matcher.
// Works on frames (60 per second). No DOM code here, so it can be tested with Node.
(function (root) {
  "use strict";

  const MARKERS = new Set(["T!", "W!", "HE!", "HB!", "CH", "CL"]);
  const DIR_RE = /^(n|[udfb]|[ud][fb])$/i;
  const BTN_RE = /^[1-4](\+[1-4])*$/;
  const MOTIONS = { qcf: ["d", "df", "f"], qcb: ["d", "db", "b"] };
  const WORDS = {                 // whole tokens that are only movement
    dash: ["f", "n", "f"], md: ["f", "n", "f"],
    cc: ["u*", "n"], ssl: ["u", "n"], ssr: ["d", "n"],
  };

  const DEFAULTS = {
    simulWindow: 1,     // max frames between buttons of a "1+2" press
    stringWindow: 30,   // max frames between hits of a string (",")
    moveWindow: 45,     // max frames between moves in a combo (" ")
    tildeWindow: 10,    // max frames for "~" (right after)
    motionWindow: 20,   // a motion (qcf, f,f) must start within this many frames
    wsWindow: 20,       // ws: crouch must be seen within this many frames
    timing: { justFrames: {}, fastWR: 8 },
  };

  class ParseError extends Error {}

  // Remove repeats but keep "f,f" as f,n,f.
  function buildSeq(dirs) {
    const out = [];
    for (const d of dirs) {
      const last = out[out.length - 1];
      if (last === d) {
        if (d !== "n") out.push("n", d);
      } else {
        out.push(d);
      }
    }
    return out;
  }

  // Normalise a direction word: lower case, and put u/d first ("fd" -> "df").
  function normDir(s) {
    s = s.toLowerCase();
    if (s.length === 2 && "fb".includes(s[0])) s = s[1] + s[0];
    return s;
  }

  function parse(notation, timing) {
    if (typeof notation !== "string" || notation.length > 300) throw new ParseError("bad notation");
    timing = timing || DEFAULTS.timing;
    const steps = [];
    let markers = [];
    const tokens = notation.trim().split(/\s+/).filter(Boolean);

    for (let ti = 0; ti < tokens.length; ti++) {
      let tok = tokens[ti];
      const link0 = steps.length ? " " : "start";

      if (MARKERS.has(tok)) { markers.push(tok); continue; }
      if (WORDS[tok]) {
        steps.push({ kind: "dirs", seq: WORDS[tok], link: link0, label: tok, markers, tok: ti });
        markers = [];
        continue;
      }

      let fast = false;
      if (tok.endsWith("(fast)")) { fast = true; tok = tok.slice(0, -6); }
      tok = tok.replace(/[()]/g, "");

      // Split "f,f,F+2" / "FC.df+1:4~df" into pieces with their separator.
      const parts = tok.split(/([,:~])/);
      let pendingDirs = [];
      let pendingLink = link0;
      let pendingText = "";
      let soFar = "";
      for (let pi = 0; pi < parts.length; pi += 2) {
        const sep = pi === 0 ? null : parts[pi - 1];
        let piece = parts[pi];
        soFar += (sep || "") + piece;
        if (!piece) throw new ParseError(`empty part in "${tok}"`);
        const link = sep === null ? link0 : sep;

        let prefix = "";
        const pm = piece.match(/^(FC|SNK|OTG|H|SS|BT|PGR|WR)\./);
        if (pm) { prefix = pm[1]; piece = piece.slice(pm[0].length); }
        let ws = false;
        if (/^ws[1-4]/.test(piece)) { ws = true; piece = piece.slice(2); }

        // Direction only piece ("f", "df", "H.F", "~D").
        if (DIR_RE.test(piece) && !ws) {
          const d = normDir(piece);
          if (sep === "~" || prefix === "H") {
            steps.push({ kind: "dirs", seq: [sep === "~" && piece === piece.toUpperCase() ? d + "*" : d],
                         link: sep === "~" ? "~" : link, label: (sep || "") + (prefix ? prefix + "." : "") + piece,
                         markers, tok: ti });
            markers = [];
          } else {
            if (!pendingDirs.length) { pendingLink = link; pendingText = ""; }
            pendingText += (pendingDirs.length ? sep : "") + piece;
            pendingDirs.push(d);
          }
          continue;
        }

        // Button piece, maybe with a direction or motion: "df+1", "qcf+3+4", "1+2".
        let dir = null, motion = null, btnText = piece;
        const m = piece.match(/^([a-zA-Z]+)\+(.+)$/);
        if (m) {
          if (MOTIONS[m[1].toLowerCase()]) motion = MOTIONS[m[1].toLowerCase()].slice();
          else if (DIR_RE.test(m[1])) dir = normDir(m[1]);
          else throw new ParseError(`unknown input "${m[1]}" in "${tok}"`);
          btnText = m[2];
        }
        if (!BTN_RE.test(btnText)) throw new ParseError(`can't read "${piece}" in "${tok}"`);
        const btns = [...new Set(btnText.split("+").map(Number))].sort();

        let stepLink = link;
        let labelHead = sep && sep !== " " ? sep : "";
        if (pendingDirs.length) {
          labelHead = pendingText + sep;
          // "f,f,F+2" or "uf,n,4": earlier directions become the motion.
          motion = buildSeq(pendingDirs);
          const lastM = motion[motion.length - 1];
          if (dir && dir !== lastM) motion.push(dir);
          if (!dir) dir = motion[motion.length - 1];
          stepLink = pendingLink;
          pendingDirs = [];
        }
        if (dir === null) {
          if (ws) dir = "ws";
          else if (prefix === "SNK" || motion) dir = "*";
          else if (sep === "," || sep === ":") dir = "*";   // string follow-ups ignore direction
          else dir = "n";
        }

        const step = {
          kind: "press", btns, dir, motion, ws, link: stepLink, markers,
          label: labelHead + (prefix ? prefix + "." : "") + (ws ? "ws" : "") + piece, tok: ti,
          stance: prefix === "SNK",
        };
        if (stepLink === ":") {
          const win = timing.justFrames[soFar];
          step.jf = win ? win.slice() : [0, 1];
        }
        if (fast && pi === parts.length - 1) step.fast = timing.fastWR || 8;
        markers = [];
        steps.push(step);
      }
      if (pendingDirs.length) {
        // Token was only directions: "b,b" (backdash) or "d".
        steps.push({ kind: "dirs", seq: pendingDirs.length === 1 ? [pendingDirs[0] + "*"] : buildSeq(pendingDirs),
                     link: pendingLink, label: tok, markers, tok: ti });
        markers = [];
      }
    }
    if (!steps.length) throw new ParseError("no inputs");
    return steps;
  }

  function dirMatches(want, have) {
    if (want === "*") return true;
    if (want.endsWith("*")) return have.includes(want[0]);
    return want === have;
  }

  // Checks a stream of inputs against parsed steps.
  // feed: dir(frame, dir), press(frame, btn), tick(frame). Read .state, .idx, .results, .error.
  class Matcher {
    constructor(steps, opts) {
      this.steps = steps;
      this.o = Object.assign({}, DEFAULTS, opts || {});
      this.reset();
    }

    reset() {
      this.idx = 0;
      this.state = "ready";        // ready -> running -> done | fail
      this.results = [];           // per step: { frame, gap }
      this.error = null;
      this.hist = [{ f: -1e9, d: "n" }];  // direction changes
      this.group = null;           // multi-button press being collected
      this.lastFrame = null;       // frame the previous step finished
    }

    get curDir() { return this.hist[this.hist.length - 1].d; }

    fail(msg, frame) {
      this.state = "fail";
      this.error = { step: this.idx, msg, frame };
    }

    advance(frame) {
      const prev = this.lastFrame;
      this.results[this.idx] = { frame, gap: prev === null ? 0 : frame - prev };
      this.lastFrame = frame;
      this.idx++;
      if (this.idx >= this.steps.length) this.state = "done";
    }

    linkLimit(step) {
      switch (step.link) {
        case ",": return this.o.stringWindow;
        case "~": return this.o.tildeWindow;
        case ":": return step.jf[1];
        case "start": return Infinity;
        default: return step.stance ? this.o.moveWindow + 20 : this.o.moveWindow;
      }
    }

    // Did the direction history since `from` contain seq in order?
    seqSeen(seq, from, contiguous) {
      const h = this.hist.filter((e, i) => e.f >= from || i === this.hist.length - 1);
      if (contiguous) {
        for (let s = 0; s + seq.length <= h.length; s++) {
          if (seq.every((w, k) => dirMatches(w, h[s + k].d))) return h[s];
        }
        return null;
      }
      let k = 0, first = null;
      for (const e of h) {
        if (k < seq.length && dirMatches(seq[k], e.d)) { if (!k) first = e; k++; }
      }
      return k === seq.length ? first : null;
    }

    start(frame) { if (this.state === "ready") this.state = "running"; }

    dir(frame, d) {
      if (this.state === "done" || this.state === "fail") return;
      if (d === this.curDir) return;
      this.hist.push({ f: frame, d });
      if (this.hist.length > 64) this.hist.shift();
      const step = this.steps[this.idx];
      if (step && step.kind === "dirs") this.tryDirs(frame);
    }

    tryDirs(frame) {
      const step = this.steps[this.idx];
      const from = this.lastFrame === null ? frame - this.o.motionWindow : this.lastFrame - this.o.motionWindow;
      const contiguous = step.seq.length > 1 && step.seq.includes("n") && step.label !== "cc";
      const hit = this.seqSeen(step.seq, Math.max(from, (this.lastFrame ?? -1e9) - 8), contiguous);
      if (!hit) return;
      this.start(frame);
      const limit = this.linkLimit(step);
      if (this.lastFrame !== null && frame - this.lastFrame > limit) {
        return this.fail(`Too slow: ${frame - this.lastFrame}f after the last input (max ${limit}f)`, frame);
      }
      this.advance(frame);
      // Several dirs steps in a row can finish on the same input.
      const next = this.steps[this.idx];
      if (this.state === "running" && next && next.kind === "dirs") this.tryDirs(frame);
    }

    press(frame, btn) {
      if (this.state === "done" || this.state === "fail") return;
      const step = this.steps[this.idx];
      this.start(frame);
      if (step.kind === "dirs") {
        return this.fail(`Pressed ${btn} before doing "${step.label}"`, frame);
      }
      if (!step.btns.includes(btn)) {
        if (this.group) return this.fail(`Pressed ${btn}: wanted ${step.btns.join("+")}`, frame);
        return this.fail(`Wrong button: pressed ${btn}, wanted ${step.btns.join("+")}`, frame);
      }
      if (!this.group) this.group = { f: frame, got: new Set(), dirAt: this.curDir };
      if (this.group.got.has(btn)) return this.fail(`Pressed ${btn} twice`, frame);
      this.group.got.add(btn);
      if (frame - this.group.f > this.o.simulWindow) {
        return this.fail(`${step.btns.join("+")} not together: ${frame - this.group.f}f apart (max ${this.o.simulWindow}f)`, frame);
      }
      if (this.group.got.size === step.btns.length) this.finishPress(this.group.f);
    }

    finishPress(frame) {
      const step = this.steps[this.idx];
      const dirAt = this.group.dirAt;
      this.group = null;
      const gap = this.lastFrame === null ? 0 : frame - this.lastFrame;

      // Timing.
      if (step.link === ":") {
        const [a, b] = step.jf;
        if (gap < a) return this.fail(`Just frame too EARLY: ${gap}f (need ${a}-${b}f)`, frame);
        if (gap > b) return this.fail(`Just frame too LATE: ${gap}f (need ${a}-${b}f)`, frame);
      } else if (this.lastFrame !== null) {
        const limit = this.linkLimit(step);
        if (gap > limit) return this.fail(`Too slow: ${gap}f after the last input (max ${limit}f)`, frame);
      }

      // Direction held when the button was pressed.
      if (step.dir === "ws") {
        if (dirAt.includes("d")) return this.fail(`ws: let go of down first (you held ${dirAt})`, frame);
        const crouched = this.hist.some((e) => e.d.includes("d") && e.f >= frame - this.o.wsWindow);
        if (!crouched && this.idx === 0) return this.fail("ws: crouch (hold down) first, then let go", frame);
      } else if (step.dir !== "*" && dirAt !== step.dir) {
        return this.fail(`Direction: held ${dirAt.toUpperCase()}, wanted ${step.dir.toUpperCase()}`, frame);
      }

      // Motion before the button (qcf, f,f, uf,n).
      if (step.motion) {
        const tailNeeded = step.dir !== "*";   // f,f,F+2 must end on f at the press
        const from = frame - this.o.motionWindow;
        const first = this.seqSeen(step.motion, from, true);
        if (!first) return this.fail(`Motion missed: wanted ${step.motion.join(",")}`, frame);
        if (tailNeeded && !dirMatches(step.motion[step.motion.length - 1], dirAt)) {
          return this.fail(`Motion missed: wanted ${step.motion.join(",")}`, frame);
        }
        if (step.fast) {
          const span = frame - first.f + 1;
          if (span > step.fast) return this.fail(`Not fast enough: ${span}f (need ${step.fast}f or less)`, frame);
        }
      }
      this.advance(frame);
    }

    tick(frame) {
      if (this.state !== "running") return;
      if (this.group && frame - this.group.f > this.o.simulWindow) {
        const step = this.steps[this.idx];
        const miss = step.btns.filter((b) => !this.group.got.has(b));
        return this.fail(`${step.btns.join("+")}: missing ${miss.join("+")} (press together)`, frame);
      }
      const step = this.steps[this.idx];
      if (this.lastFrame !== null && step && frame - this.lastFrame > this.linkLimit(step) + 1) {
        if (step.link === ":") return this.fail(`Just frame too LATE (need ${step.jf[0]}-${step.jf[1]}f)`, frame);
        this.fail(`Dropped: next input "${step.label}" too late`, frame);
      }
    }
  }

  const api = { parse, Matcher, ParseError, DEFAULTS, buildSeq };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.T8Engine = api;
})(typeof window !== "undefined" ? window : globalThis);
