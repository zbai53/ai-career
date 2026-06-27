# Screenshot Capture Guide

All screenshots live in `docs/screenshots/` and are referenced from `README.md`.

---

## Setup: consistent viewport

Use Chrome DevTools to lock every screenshot to **1280 × 800** so they look uniform in the README.

1. Open Chrome and navigate to `http://localhost:3000`
2. Open DevTools — `Cmd+Option+I`
3. Click the **device toolbar** icon (phone/tablet icon at top-left of DevTools), or press `Cmd+Shift+M`
4. In the dimensions dropdown at the top of the viewport, choose **Responsive** and type `1280` × `800`
5. Press **Enter** — the browser reflows to that size

> Keep DevTools open and docked to the side (not bottom) to avoid it taking up vertical space.

---

## Option A: Chrome built-in full-page capture (recommended)

1. In DevTools, press `Cmd+Shift+P` to open the Command Palette
2. Type `screenshot` and choose **Capture full size screenshot**
3. Chrome saves a PNG to your Downloads folder automatically
4. Rename and move it to `docs/screenshots/<name>.png`

This captures the full scrollable page even if content is below the fold.

---

## Option B: Mac system screenshot

1. Press `Cmd+Shift+4` — cursor turns into a crosshair
2. Drag to select just the browser viewport (exclude the browser chrome/address bar)
3. The PNG drops to your Desktop — rename and move to `docs/screenshots/<name>.png`

Use this option for pages where the above-the-fold view is all you need.

---

## Screenshots needed

Run `docs/screenshots/demo-data-setup.sh` first to create real data in the app.
The script prints the exact URLs to visit for each screenshot.

---

### a. `dashboard.png` — Dashboard

**URL:** `http://localhost:3000/`

**What to show:**
- Stats cards with real numbers (resumes parsed, matches run, etc.)
- Recent activity list with at least 2–3 entries
- Workflow progress bar in the left sidebar showing steps completed
- If the workflow progress section shows green checkmarks, even better

**Steps:**
1. Run the demo setup script so activity data is populated
2. Navigate to `/`
3. Capture full size screenshot

---

### b. `upload.png` — Resume Upload (parsed result)

**URL:** `http://localhost:3000/upload`

**What to show:**
- The parsed result card below the upload area (after a successful upload)
- Name, headline, skills section visible
- Education count badge visible

**Steps:**
1. Upload the sample resume (or re-use the one created by the script)
2. Wait for the parse success state to appear
3. Scroll up so the result card is visible
4. Capture screenshot

---

### c. `jd-input.png` — JD Input (parsed result)

**URL:** `http://localhost:3000/jd`

**What to show:**
- Parsed result below the text area
- Job title visible (e.g. "Senior Backend Engineer")
- Required skills badges visible
- Company and location if present

**Steps:**
1. Paste the sample JD text from the demo script into the text area
2. Click Parse
3. Wait for the parsed result to appear
4. Capture screenshot

---

### d. `match.png` — Match Results

**URL:** `http://localhost:3000/match/<match_result_id>` *(script prints this URL)*

**What to show:**
- Radar chart with 6 dimensions filled in
- Overall score percentage prominent
- At least one gap / missing skill visible
- "Rewrite Resume" button visible at the bottom

**Steps:**
1. Navigate to the match result URL printed by the script
2. Scroll to make radar chart and score both visible
3. Capture screenshot

---

### e. `rewrite.png` — Rewrite Comparison

**URL:** `http://localhost:3000/rewrite/<rewrite_id>` *(script prints this URL)*

**What to show:**
- At least one before/after bullet pair side-by-side
- Fidelity badge (green "Passed" or yellow "Warning")
- Keywords injected section visible

**Steps:**
1. Navigate to the rewrite result URL printed by the script
2. Scroll so 2–3 bullet pairs are visible
3. Make sure the fidelity badge is in frame
4. Capture screenshot

---

### f. `interview.png` — Interview Chat (mid-conversation)

**URL:** `http://localhost:3000/interview/<session_id>` *(script prints this URL)*

**What to show:**
- At least 2–3 message bubbles visible (question + answer + follow-up or next question)
- Question number badge (e.g. "Question 2 / 5")
- Answer input box at the bottom

**Steps:**
1. Navigate to the interview URL printed by the script
2. If the interview was run via script, navigate to it and type one more answer manually to show activity
   - OR use the session the script started but didn't fully complete
3. Capture screenshot with chat visible

---

### g. `review.png` — Coach Review

**URL:** `http://localhost:3000/review/<session_id>` *(script prints this URL)*

**What to show:**
- Overall readiness badge (e.g. "Almost Ready" or "Ready")
- Overall score
- At least one per-question score row visible
- Strengths / Improvements section partially visible

**Steps:**
1. Navigate to the review URL printed by the script
2. Scroll so the readiness badge and first 2 question rows are visible
3. Capture screenshot

---

### h. `workflow.png` — Workflow Visualization

**URL:** `http://localhost:3000/workflow`

**What to show:**
- React Flow graph with nodes rendered
- At least some nodes in a "completed" or highlighted state
- Node labels readable (parse_resume, match, rewrite, etc.)

**Steps:**
1. Navigate to `/workflow`
2. Let the graph load fully (may take 1–2 seconds)
3. Zoom out slightly if nodes overlap: use scroll wheel or pinch
4. Capture screenshot

---

## File naming checklist

```
docs/screenshots/
  dashboard.png     ✓ / ✗
  upload.png        ✓ / ✗
  jd-input.png      ✓ / ✗
  match.png         ✓ / ✗
  rewrite.png       ✓ / ✗
  interview.png     ✓ / ✗
  review.png        ✓ / ✗
  workflow.png      ✓ / ✗
```

After adding all images, update `README.md`'s Screenshots table to replace `jd-input.png`
with the actual filename if you renamed it, then verify the images render on GitHub.
