# tekken-trainer

Practise Tekken 8 inputs on your keyboard **without opening the game**. Made for Dragunov.
It checks every press frame by frame (60 per second), like the game, and tells you exactly what went wrong.

- **Combos:** 25 Dragunov combos from Easy to Extreme (Wavu Wiki and the TekkenDocs guide), each with when to use it and tips.
- **Drills:** one technique at a time: fast f,f,F+2 (within 8 frames), just-frame Hail Slicer (FC.df+1:4, frames 16–19), qcf moves, ws moves, crouch cancel, dashes.
- **Punish trainer:** a random blocked move from any of 41 characters. Punish it with the right Dragunov move, or keep blocking if it's safe.
- **Moves:** all 141 Dragunov moves with frame data, a short game plan, and a **Drill** button on each move.
- **Feedback:** "wrong button", "held DF, wanted N", "1+2 were 2 frames apart", "just frame too early: 12f", a Tekken-style input display, success rate, streaks and weak spots.
- **My timing:** save a run that worked in the real game, then see how many frames early or late each step is, with an optional rhythm beep.

## Run

Open `index.html` in Firefox or Chrome. No install, no internet needed.

```fish
xdg-open index.html
```

Default keys are Tekken 8's keyboard defaults: **WASD** to move, **U I J K** = 1 2 3 4, **Space** = reset / next.
Change them in **Keys & setup**. That tab also has a key test, so you can check your keyboard registers 4 keys at once.

## How the checking works

| Notation | Means | Checked |
|---|---|---|
| `4,1` | string | next hit within 30 frames (can be changed) |
| `df+2 4,1` | next move | within 45 frames (can be changed) |
| `1+2` | together | same frame (allow up to 3 in setup) |
| `2` | plain button | **no direction held** (holding one makes it a different move) |
| `FC.df+1:4` | just frame | 4 on 15–18 frames after the 1 (TekkenDocs: frames 16–19) |
| `f,f,F+2(fast)` | blue spark | f, n, f+2 within 8 frames |
| `2,1~df` | right after | df within 10 frames |
| `ws4` | while standing | let go of down, then press |
| `cc` | crouch cancel | up, then neutral |

Exact gaps between moves inside a combo depend on the game, so the trainer only checks you aren't too slow.
For exact rhythm, use **Save last run as my timing** after a run that worked in practice mode.

## Limits

- No hitboxes, range, walls or pushback. It trains your hands. Confirm combos and punishers in the game's practice mode.
- Data is from TekkenDocs (game version shown on their site) and can be out of date after a patch.

## Update the data

```fish
mkdir -p ~/tmp/t8chars
for c in dragunov kazuya # ...any characters
    curl -A "Mozilla/5.0" -o ~/tmp/t8chars/$c.json https://tekkendocs.com/api/t8/$c/framedata; sleep 1
end
python3 -I scripts/build_data.py ~/tmp/t8chars js/data
```

## Tests

```fish
node --test tests/
```

## Credits

- Frame data: [TekkenDocs](https://tekkendocs.com) (please keep this credit wherever the data is shown).
- Combos: [Wavu Wiki](https://wavu.wiki/t/Dragunov_combos) (CC0) and the [TekkenDocs Dragunov guide](https://tekkendocs.com/t8/dragunov/guide) by Fear Of Silence.
- TEKKEN is a trademark of Bandai Namco Entertainment Inc. This is a fan-made practice tool, not linked to Bandai Namco.
