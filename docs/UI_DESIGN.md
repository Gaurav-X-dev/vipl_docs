# VIPL interface design specification

The brief, written before the work, so the result can be checked against it
rather than judged by taste alone.

---

## 1. What this interface is for

Eight to ten people run an investigation agency's whole day through it. They
are not visiting; they are *working* — an investigator on a phone outside a
house, an office processor with twelve tabs open, an owner scanning for what is
overdue. The measure of the design is not how it photographs. It is:

- can someone find today's work in under three seconds,
- can they read a table of forty cases without leaning in,
- does the screen tell them what needs attention before they ask.

That makes this an **information tool**, not a marketing page. Craft goes into
density, hierarchy and legibility — not decoration.

### Non-goals

Gradients, illustrations, hero sections, animated flourishes, rounded-everything.
Anything that costs a row of data its place on screen has to earn it.

---

## 2. Where the current build falls short

Observed on the running app, in order of damage:

1. **Filters are laid out by three different rules.** Some pages pass bare
   `<select>` elements, some wrap each control in `<Field>`. One flex rule
   serves both, so the Reports filter bar renders as tall empty boxes with the
   date inputs stranded at the bottom. This is a genuine layout bug, not a
   preference.
2. **No vertical rhythm.** Padding values in use: 9, 10, 11, 13, 14, 16, 17,
   18, 20, 21, 22, 28, 30. Nothing lines up because nothing shares a scale.
3. **Two palettes half-applied.** A navy identity sits on top of an older teal
   one; both show.
4. **Cards are undifferentiated.** A filter bar, a chart and a data table are
   all the same white box with the same border, so the eye has no route
   through the page.
5. **Charts are bare.** The status distribution is a stack of flat bars with no
   baseline, no axis, no grouping.
6. **Empty and loading states are afterthoughts.** A centred grey line where
   the page should be explaining itself.
7. **Sidebar clipping.** The form list overflows its container at the top.

---

## 3. The system

### 3.1 Space

One scale. Every padding, gap and margin comes from it:

```
--s-1: 4px    --s-2: 8px    --s-3: 12px   --s-4: 16px
--s-5: 20px   --s-6: 24px   --s-7: 32px   --s-8: 40px
```

Rules: card padding `--s-6`. Gap between cards `--s-5`. Gap inside a control
group `--s-3`. Label to input `--s-1`. Page padding `--s-7`.

### 3.2 Type

Inter throughout, one scale, no exceptions:

| Role | Size / weight | Tracking |
|---|---|---|
| Page title | 26 / 700 | -0.025em |
| Card title | 16 / 700 | -0.015em |
| Body, table cell | 13.5 / 400 | -0.005em |
| Table cell emphasis | 14 / 600 | -0.01em |
| Meta, helper | 12.5 / 400 | 0 |
| Column header, eyebrow | 11 / 700 uppercase | 0.06em |
| Metric | 32 / 700 | -0.03em, tabular |

Nothing below 11px. The 9px badges were the single worst thing in the build.

### 3.3 Colour

Brand navy, matched to the KYC platform so the two products read as one suite.

```
brand   950 #0a203d   800 #194984   700 #1b559f   500 #3988e8   50 #eff7ff
ink        #0f1e2e    ink-2 #46596d    ink-3 #78899b
line       #e3e9f1    line-soft #eef2f7
surface    #ffffff    surface-2 #f7f9fc    paper #f4f7fb
```

Neutrals carry a navy bias — a pure grey next to this blue reads as unfinished.

Semantic colour is **separate from the accent** and means one thing each:

```
ok    #0f7b57 on #e7f6ef   warn  #9a6410 on #fdf3e3
alert #b03b34 on #fceceb   info  #4c3f9c on #eeecfb
```

Every semantic surface carries a matching border, so a badge holds its shape on
white and on `surface-2`.

### 3.4 Elevation and shape

Three levels, no more:

- **Flat** — filter bars, table headers: `surface-2`, no shadow.
- **Raised** — cards: `surface`, 1px `line`, `0 1px 2px / 0 10px 34px` at 4–6%.
- **Floating** — modals, popovers: `0 24px 70px` at 24%.

Radii: `8` controls, `10` buttons, `14` tiles, `18` cards, `999` pills.

---

## 4. Components

### 4.1 The filter bar — the piece to get right

One structure, used by every page, tolerant of both markup shapes:

```
┌──────────────────────────────────────────────────────────┐
│ [search, full width                          ] [Clear ✕] │
│ [select] [select] [select] [date] [date] [toggle]        │
└──────────────────────────────────────────────────────────┘
```

- CSS **grid**, `repeat(auto-fit, minmax(180px, 1fr))`, `align-items: end`.
  Grid is what makes it survive both a bare `<select>` and a `<Field>` wrapper —
  the bug in the current build is a flex row trying to do this job.
- Search spans the full row (`grid-column: 1 / -1`).
- Every control is 38px tall on its own baseline; labels sit above at 11px.
- **An active filter is visibly active**: brand-tinted background and border.
  Scanning the bar should say what is applied without reading each value.
- The bar is `surface-2` inside the card and bleeds to its edges, so it reads
  as a control strip attached to the data, not a second card.

### 4.2 Data table

The main object on most screens.

- Sticky header, `surface-2`, 11px uppercase, stays put while scrolling.
- Rows 48px; cell padding `--s-4`.
- Hairline `line-soft` between rows, none after the last.
- Hover tints the row `surface-2`.
- First cell is the identity: 14/600 ink, with a 12px meta line under it.
- Numeric and date columns `tabular-nums` so they line up.
- The scroll container owns `overflow-x`; the page never scrolls sideways.

### 4.3 Status badge

12px, 600, pill, semantic background **and** border, capitalised. Optional
6px dot for online/offline where colour alone would be the only signal.

### 4.4 Metric tile

Label 12.5 above, number 32/700 tabular below, optional delta. Border, no
shadow, 1px lift on hover. Semantic colour on the number only when the number
itself is the warning.

### 4.5 Distribution bar (Reports)

Currently a flat bar. It becomes a small chart:

- Label left (fixed width), track, value right with its percentage under it.
- Track is `line-soft` at full width; fill is the bar's semantic colour.
- Bars share one scale so lengths are comparable.
- Rounded ends, 8px high, 200ms ease on width so a filter change animates.

### 4.6 Empty, loading, error

Each states what happened and what to do:

- **Empty** — icon, 16/600 line, one 13.5 sentence of guidance, and the action
  that fixes it where one exists.
- **Loading** — skeleton rows matching the table's shape, not a spinner. A
  spinner says "wait"; a skeleton says "here is what is coming".
- **Error** — what failed, in plain words, and a Retry.

### 4.7 Sidebar

Already rebuilt: `brand-950`, 276px, flat list of forms with the client's own
file names, chevron trailing. Remaining fix: the scroll container must not clip
its first row.

---

## 5. Accessibility and behaviour

- One focus ring everywhere: `0 0 0 3px rgba(57,136,232,.16)` plus a
  brand-500 border. Never `outline: none` with nothing in its place.
- Contrast: body text ≥ 7:1 on white, meta ≥ 4.5:1, semantic pills ≥ 4.5:1.
- Colour is never the only signal — status carries a word, presence carries a
  label beside the dot.
- `prefers-reduced-motion` disables every transition.
- Tables scroll inside their own container; the body never scrolls sideways.

---

## 6. How this gets checked

1. No font-size below 11px anywhere in the stylesheets.
2. No **repeated** hex colour outside the token block. Two exceptions, both
   deliberate: white-alpha overlays on the dark sidebar (`#ffffff12` and
   friends) read better as literals than as a dozen near-identical tokens, and
   a genuinely single-use tint is not a system value.
3. Space-scale variables used for all new and reworked rules. The older screens
   still carry ad-hoc padding; they move onto the scale as each is touched,
   rather than in one sweep that would change every screen untested.
4. Filter bars render identically on Cases, Reports, Staff, Imports, Audit and
   Activity — the pages that mix both markup shapes.
5. `npm run build`, `tsc`, `eslint` clean; backend suite green.
