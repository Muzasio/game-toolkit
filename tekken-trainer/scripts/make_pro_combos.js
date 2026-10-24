// Turn input-history rows (read_input_history.py) into trainer combos that copy a player's
// exact keys and frame timing.
//
//   node scripts/make_pro_combos.js ROWS.json DUPES.json|- PREFIX "Source" VIDEO_URL OUT.js [NAMES.json]
//
// NAMES.json (optional): {"<video second>": {"name": "...", "notes": "..."}} to name runs.
"use strict";
const fs = require("node:fs");
const path = require("node:path");
globalThis.window = globalThis;
const { parse } = require(path.join(__dirname, "../js/engine.js"));

const [rowsFile, dupesFile, prefix, source, url, outFile, namesFile] = process.argv.slice(2);
if (!outFile) {
  console.error("usage: node scripts/make_pro_combos.js ROWS.json DUPES.json|- PREFIX SOURCE URL OUT.js [NAMES.json]");
  process.exit(2);
}
const rows = JSON.parse(fs.readFileSync(rowsFile, "utf8"));
const diffs = dupesFile !== "-" ? JSON.parse(fs.readFileSync(dupesFile, "utf8")).diff : null;
const names = namesFile ? JSON.parse(fs.readFileSync(namesFile, "utf8")) : {};
const SPLIT = 60;        // neutral this long (1 s) ends a combo
const FPS = 60;

// Split into runs at long neutral rows.
const runs = [];
let cur = [];
for (const r of rows) {
  if (r.dir === "n" && !r.btn.length && r.n >= SPLIT) { if (cur.length) runs.push(cur); cur = []; }
  else cur.push(r);
}
if (cur.length) runs.push(cur);

const slowRatio = (run) => {
  if (!diffs) return 0;
  const a = Math.round(run[0].t * FPS), b = a + run.reduce((s, r) => s + r.n, 0);
  let dup = 0;
  for (let i = a; i < b && i < diffs.length; i++) if (diffs[i] < 0.4) dup++;
  return dup / Math.max(1, b - a);
};

// One run -> notation tokens with the gap (frames) before each token.
function build(run) {
  const toks = [];
  let f = 0, held = new Set(), dirs = [], lastPress = null;   // dirs: {d, f} since the last press
  for (const r of run) {
    const prevDir = dirs.length ? dirs[dirs.length - 1].d : null;
    if (r.dir !== prevDir) dirs.push({ d: r.dir, f });
    const now = new Set(r.btn);
    const pressed = [...now].filter((b) => !held.has(b)).sort();
    if (pressed.length) {
      const d = r.dir;
      const seq = dirs.map((x) => x.d);
      const recent = dirs.filter((x) => x.f >= f - 20).map((x) => x.d);
      let tok;
      const tail = (arr) => recent.slice(-arr.length).join() === arr.join();
      if (tail(["d", "df", "f"])) tok = "qcf+" + pressed.join("+");
      else if (tail(["f", "n", "f"]) && d === "f") tok = "f,f,F+" + pressed.join("+");
      else tok = (d === "n" ? "" : d + "+") + pressed.join("+");
      // Movement between presses that is not part of the move: dash, crouch cancel.
      const moves = [];
      const between = dirs.filter((x) => lastPress === null || x.f > lastPress).map((x) => x.d);
      const s = between.join(",");
      if (!tok.startsWith("f,f") && /(^|,)f,n,f(,|$)/.test(s)) moves.push("dash");
      if (/(^|,)u[fb]?,n(,|$)/.test(s)) moves.push("cc");
      for (const m of moves) toks.push({ tok: m, gap: null });
      toks.push({ tok, gap: lastPress === null ? 0 : f - lastPress, held: d });
      lastPress = f;
      dirs = [{ d, f }];
      void seq;
    }
    held = now;
    f += r.n;
  }
  return toks;
}

const out = [];
runs.forEach((run) => {
  const t0 = run[0].t;
  const presses = run.filter((r, i) => r.btn.length && (i === 0 || r.btn.some((b) => !run[i - 1].btn.includes(b))));
  if (presses.length < 3) return;
  if (slowRatio(run) > 0.3) { console.log(`skip ${t0}s: slow motion`); return; }
  // An unreadable arrow is fine while no button is pressed (keep the last direction).
  if (run.some((r) => r.dir === "?" && r.btn.length)) { console.log(`skip ${t0}s: unreadable arrow on a press`); return; }
  run = run.map((r, i, all) => (r.dir === "?" ? Object.assign({}, r, { dir: i ? all[i - 1].dir : "n" }) : r));
  const toks = build(run);
  const notation = toks.map((x) => x.tok).join(" ");
  let steps;
  try { steps = parse(notation); } catch (e) { console.log(`skip ${t0}s: ${e.message}`); return; }
  // Mashed buttons: the same press 3+ times in a row.
  let mash = 0, run3 = 1;
  for (let i = 1; i < toks.length; i++) {
    run3 = toks[i].tok === toks[i - 1].tok ? run3 + 1 : 1;
    if (run3 === 3) mash++;
  }
  const sec = Math.floor(t0);
  const meta = names[String(sec)] || {};
  out.push({
    id: `${prefix}-${sec}`,
    level: "pro", group: source,
    name: meta.name || `${source} @ ${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`,
    notation,
    damage: "",
    src: `${source} (video ${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")})`,
    url: `${url}${url.includes("?") ? "&" : "?"}t=${sec}`,
    when: meta.notes || "",
    tips: (mash ? "The player presses some buttons several times in a row (mashing) to be sure a hit comes out. " : "") +
          "These are the exact keys the player pressed, read from the game's input history.",
    pro: { gaps: steps.map(() => null), source },
  });
  // Gaps per step: tokens with a gap map to their press step(s); movement tokens get null.
  const gaps = [];
  for (const x of toks) {
    const n = parse(x.tok).length;
    for (let k = 0; k < n; k++) gaps.push(k === n - 1 ? x.gap : null);
  }
  out[out.length - 1].pro.gaps = gaps;
  console.log(`${t0}s  ${notation}\n      gaps ${gaps.map((g) => (g === null ? "·" : g)).join(" ")}`);
});

fs.writeFileSync(outFile,
  `// Combos copied from ${source}: exact keys and frame gaps read from Tekken 8's input history.\n` +
  "// Generated by scripts/make_pro_combos.js. Do not edit by hand.\n" +
  `window.T8_PRO_COMBOS = (window.T8_PRO_COMBOS || []).filter((c) => !c.id.startsWith(${JSON.stringify(prefix + "-")}))` +
  `.concat(${JSON.stringify(out)});\n`);
console.log(`${out.length} combos written`);
