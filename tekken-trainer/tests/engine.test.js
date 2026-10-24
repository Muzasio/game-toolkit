// Run: node --test tests/
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");
const { parse, Matcher } = require("../js/engine.js");

// Load the browser data files (they assign to window.*).
globalThis.window = globalThis;
require(path.join(__dirname, "../js/data/combos.js"));
const timing = { justFrames: T8_TIMING.justFrames, fastWR: T8_TIMING.fastWR };

// events: [frame, "d", dir] or [frame, "p", button]
function run(notation, events, opts) {
  const m = new Matcher(parse(notation, timing), opts);
  let last = 0;
  for (const [f, kind, v] of events) {
    for (let t = last; t < f; t++) m.tick(t);
    last = f;
    if (kind === "d") m.dir(f, v); else m.press(f, v);
  }
  m.tick(last);
  return m;
}

test("every combo, drill and punisher parses", () => {
  for (const c of [...T8_COMBOS, ...T8_DRILLS, ...T8_PUNISHERS]) {
    assert.doesNotThrow(() => parse(c.notation, timing), c.notation);
  }
});

test("f,f,F+2 motion is f,n,f with f held", () => {
  const [s] = parse("f,f,F+2", timing);
  assert.deepStrictEqual(s.motion, ["f", "n", "f"]);
  assert.strictEqual(s.dir, "f");
});

test("uf,n,4 presses 4 on neutral", () => {
  const [s] = parse("uf,n,4", timing);
  assert.deepStrictEqual(s.motion, ["uf", "n"]);
  assert.strictEqual(s.dir, "n");
});

test("simple string 4,1 works", () => {
  const m = run("4,1", [[0, "p", 4], [12, "p", 1]]);
  assert.strictEqual(m.state, "done");
});

test("wrong button fails", () => {
  const m = run("4,1", [[0, "p", 4], [12, "p", 2]]);
  assert.strictEqual(m.state, "fail");
  assert.match(m.error.msg, /Wrong button/);
});

test("plain 2 with down held fails (that would be d+2)", () => {
  const m = run("2", [[0, "d", "d"], [3, "p", 2]]);
  assert.strictEqual(m.state, "fail");
  assert.match(m.error.msg, /Direction/);
});

test("1+2 must be together", () => {
  assert.strictEqual(run("1+2", [[0, "p", 1], [1, "p", 2]]).state, "done");
  const late = run("1+2", [[0, "p", 1], [3, "p", 2]]);
  assert.strictEqual(late.state, "fail");
});

test("Hail Slicer just frame: early, ok, late", () => {
  const ev = (g) => [[0, "d", "df"], [2, "p", 1], [2 + g, "p", 4]];
  assert.match(run("FC.df+1:4", ev(10)).error.msg, /EARLY/);
  assert.strictEqual(run("FC.df+1:4", ev(16)).state, "done");
  assert.match(run("FC.df+1:4", ev(22)).error.msg, /LATE/);
});

test("fast WR+2 within 8 frames", () => {
  const fast = [[0, "d", "f"], [2, "d", "n"], [3, "d", "f"], [6, "p", 2]];
  assert.strictEqual(run("f,f,F+2(fast)", fast).state, "done");
  const slow = [[0, "d", "f"], [4, "d", "n"], [7, "d", "f"], [11, "p", 2]];
  assert.match(run("f,f,F+2(fast)", slow).error.msg, /Not fast/);
  assert.strictEqual(run("f,f,F+2", slow).state, "done");
});

test("qcf+1 needs d, df, f", () => {
  const ok = [[0, "d", "d"], [2, "d", "df"], [4, "d", "f"], [5, "p", 1]];
  assert.strictEqual(run("qcf+1", ok).state, "done");
  const bad = [[0, "d", "d"], [4, "d", "f"], [5, "p", 1]];
  assert.strictEqual(run("qcf+1", bad).state, "fail");
});

test("ws4 after d+2: must release down", () => {
  const ok = [[0, "d", "d"], [1, "p", 2], [30, "d", "n"], [32, "p", 4]];
  assert.strictEqual(run("d+2 ws4", ok).state, "done");
  const held = [[0, "d", "d"], [1, "p", 2], [32, "p", 4]];
  assert.match(run("d+2 ws4", held).error.msg, /ws/);
});

test("2,1~df SNK.2 enters Sneak", () => {
  const ev = [[0, "p", 2], [10, "p", 1], [13, "d", "df"], [25, "p", 2]];
  assert.strictEqual(run("2,1~df SNK.2", ev).state, "done");
  const noDf = [[0, "p", 2], [10, "p", 1], [25, "p", 2]];
  assert.strictEqual(run("2,1~df SNK.2", noDf).state, "fail");
});

test("crouch cancel: u then n", () => {
  const ev = [[0, "p", 3], [5, "d", "df"], [20, "d", "u"], [22, "d", "n"], [30, "p", 1]];
  // f+3 needs f held at the press
  const full = [[0, "d", "f"], [1, "p", 3], [8, "d", "df"], [20, "d", "u"], [22, "d", "n"], [30, "p", 1]];
  assert.strictEqual(run("f+3~df cc 1", full).state, "done");
  assert.strictEqual(run("f+3~df cc 1", ev).state, "fail");
});

test("dropped when too slow between moves", () => {
  const m = run("df+2 4,1", [[0, "d", "df"], [1, "p", 2], [2, "d", "n"], [120, "p", 4]]);
  assert.strictEqual(m.state, "fail");
  assert.match(m.error.msg, /Dropped|slow/);
});

test("backdash b,b", () => {
  assert.strictEqual(run("b,b", [[0, "d", "b"], [3, "d", "n"], [5, "d", "b"]]).state, "done");
});

test("full beginner combo", () => {
  const ev = [
    [0, "d", "df"], [1, "p", 2], [3, "d", "n"],
    [30, "p", 4], [45, "p", 1],
    [70, "p", 4], [85, "p", 4],
    [100, "d", "df"], [110, "p", 1], [126, "p", 4], [130, "d", "n"],
    [150, "p", 2],
    [180, "d", "b"], [182, "p", 4], [183, "d", "n"], [195, "p", 3],
  ];
  const m = run("df+2 4,1 4,4 FC.df+1,4 SNK.2 T! b+4,3", ev);
  assert.strictEqual(m.state, "done", m.error && m.error.msg);
});

test("Korean backdash: b,b then db,b cycles (with or without neutral)", () => {
  const m = run("b,b db,b db,b", [[0, "d", "b"], [3, "d", "n"], [6, "d", "b"], [10, "d", "db"], [13, "d", "b"],
    [17, "d", "db"], [20, "d", "n"], [22, "d", "b"]]);
  assert.strictEqual(m.state, "done", m.error && m.error.msg);
});

test("sidestep then backdash", () => {
  const m = run("ssl b,b", [[0, "d", "u"], [3, "d", "n"], [10, "d", "b"], [13, "d", "n"], [16, "d", "b"]]);
  assert.strictEqual(m.state, "done", m.error && m.error.msg);
});

test("dash then block", () => {
  const m = run("dash b", [[0, "d", "f"], [3, "d", "n"], [6, "d", "f"], [15, "d", "n"], [18, "d", "b"]]);
  assert.strictEqual(m.state, "done", m.error && m.error.msg);
});
