// Dragunov game plan, short and in our own words.
// Based on the TekkenDocs guide by Fear Of Silence (game version 2.04.00, Aug 2025)
// and the Wavu Wiki Dragunov page. Check those pages for updates after patches.
// Words used in combo notation, explained for beginners.
window.T8_GLOSSARY = [
  ["f, b, u, d", "Forward, back, up, down. Forward is towards the opponent. df = down-forward (both keys), db = down-back, uf, ub."],
  ["F, B, D (capital)", "Hold that direction instead of tapping it."],
  ["1, 2, 3, 4", "Left punch, right punch, left kick, right kick. 1+2 = both on the same frame."],
  ["n", "Neutral: no direction held."],
  ["space between moves", "Next move in the combo (wait until the last one hits)."],
  [", (comma)", "Next hit of the same string, e.g. 4,1 = press 4 then 1."],
  ["~ (tilde)", "Right after, with no delay. 2,1~df = press df immediately after the 1."],
  [": (colon)", "Just frame: the input must land on an exact frame. Don't mash it."],
  ["FC", "Full crouch: you are crouching (holding down). FC.df+1 = while crouching, hold down-forward and press 1."],
  ["ws", "While standing: let go of down and press the button as you stand up from a crouch."],
  ["SNK", "Sneak: Dragunov's crouch-walk stance. Enter it with qcf, or with df after some moves. SNK.2 = press 2 in Sneak."],
  ["qcf", "Quarter circle forward: down › down-forward › forward, one smooth roll."],
  ["PGR / PGN", "Pigeon Roll: 3+4 (or d+3+4). PGN 2 = press 2 during the roll."],
  ["cc", "Crouch cancel: tap up and let go, to stand up out of Sneak or crouch."],
  ["dash, md", "Tap forward twice quickly (md = microdash, a short one)."],
  ["ssl, ssr, SSR", "Sidestep left (tap up) / sidestep right (tap down)."],
  ["T!", "Tornado: the opponent spins in the air. Each combo can use it once to keep going."],
  ["CH", "Counter hit: you hit them while they were attacking. Some combos only work on CH."],
  ["CL", "Clean hit: the sweet spot of a move."],
  ["W!", "Wall: the opponent is stuck on the wall."],
  ["H., Heat, H.F", "Heat mode. H.F = tap forward to Heat dash after a Heat engager."],
  ["i10, i15", "Startup: the move hits after 10 or 15 frames. Lower is faster."],
  ["-12 on block", "You are 12 frames behind after it is blocked. -10 or worse can be punished."],
  ["h, m, l", "High (duck it), mid (block standing), low (block crouching)."],
  ["frame", "1/60 of a second. The game and this trainer count everything in frames."],
  ["juggle / link", "Hitting the opponent while they are in the air after a launcher."],
];

window.T8_GUIDE = [
  { title: "Game plan", points: [
    "Rushdown: win many small exchanges with safe pokes and plus-on-block mids.",
    "Main pokes: 1 (i10, +1), df+1 (i13, -2), d+2 (low, high crush, great tracking).",
    "Plus on block: f,f,F+2 (+4), b+1+2 (+6), qcf+4 (+7), d+1 (+1).",
    "Crouch game: FC.df+1,4 (low, +7 on hit) vs ws3 / ws1 (mids) from crouch.",
    "Counter-hit checks: 1,2,1 and b+4,2,1 can be hit-confirmed.",
  ]},
  { title: "Weak points", points: [
    "Weak to sidestep RIGHT (his tracking is bad on that side).",
    "Main pressure moves are slow and can be interrupted or stepped.",
    "Most damage needs a launcher; many exchanges are only poke damage.",
  ]},
  { title: "Heat", points: [
    "Heat engagers: 1,2,1 · f+3,1+2 · b+4,3 · qcf+4 · ws1+2.",
    "Heat Smash (H.2+3): mid, i15, +6 on block.",
    "In Heat, tackles and Feint & Catch become unbreakable.",
    "In Heat, ws1+2 is an i12 launcher. Use it to punish from crouch.",
  ]},
  { title: "Frame traps", points: [
    "1 → 1,2,1",
    "f,f,F+2 → df+1",
    "b+1+2 → b+4,2,1",
    "qcf+4 → ws3",
  ]},
  { title: "Whiff punishers", points: [
    "4,1: fast, up close.",
    "df+2: fastest mid launcher.",
    "qcf+1: fast high launcher, safe (-8).",
  ]},
  { title: "Stances", points: [
    "Sneak (SNK): qcf, or press df after 2,1 / 3,1 / ws1 / f+3 / b+4,2 / FC.df+1,4. Sneak moves can be delayed by up to 20 frames.",
    "Pigeon Roll: 3+4 (background) or d+3+4 (foreground). PGR.2 mid, PGR.3 low, PGR.1+2 tackle.",
    "Crouch cancel (cc): tap up and let go during the Sneak/crouch dash to stand up.",
  ]},
];
