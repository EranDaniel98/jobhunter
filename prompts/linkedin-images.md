# LinkedIn Post Series — Image Specs

Since AI image generators produce poor results for technical/infographic content, these images should be built as **HTML/CSS** and screenshotted. See `linkedin-images.html` (to be created).

---

## Global Style Guide

### Visual Identity
- **Background:** #1A1A2E (dark charcoal)
- **Accent:** #E8712A (warm orange)
- **Secondary:** #7B8FA1 (cool blue-gray)
- **Text:** #F5F5F5 (white)
- **Muted:** #3A3A5C (subtle elements)
- **Success green:** #4ADE80
- **Error red:** #E84057
- **Dimensions:** 1200x627px (LinkedIn feed optimal)
- **Font (display):** Outfit (Google Fonts) — geometric, modern
- **Font (code/data):** JetBrains Mono (Google Fonts) — developer aesthetic

### Series Branding
- "Day X/9" badge in top-left corner, small and understated
- Consistent orange accent as the focal color in every image
- Bottom-right: subtle "JobHunter AI" text, very small

---

## Post [T] — Teaser: "9 Days. 9 Posts."

**Concept:** A vertical list of 9 numbered items with short labels, styled like a terminal/code editor. Each day is a line, with Day 9 highlighted differently ("I need your help").

**Visual:**
```
┌─────────────────────────────────────────────┐
│                                             │
│   9 DAYS. 9 POSTS.                          │
│                                             │
│   01  The story                             │
│   02  The method                            │
│   03  AI reads your resume                  │
│   04  Finding hidden companies              │
│   05  90-second company research            │
│   06  AI writes, you approve                │
│   07  Paste a job, get a battle plan        │
│   08  Where AI gets it wrong                │
│   09  I need your help               ← ?   │
│                                             │
│   Starts tomorrow.                          │
│                                             │
└─────────────────────────────────────────────┘
```

**Style notes:**
- Dark background, monospace font for the list
- Numbers in orange, labels in white
- Day 09 line has orange glow/highlight, the "← ?" in muted gray creates curiosity
- "9 DAYS. 9 POSTS." as large headline at top in Outfit bold
- "Starts tomorrow." at bottom in smaller muted text
- Clean, terminal-like feel

---

## Post [1] — Origin Story: "8 Months. Zero Interviews."

**Concept:** A stark timeline/counter showing the frustrating numbers — large "8 MONTHS" and "0 INTERVIEWS" — with a turning point marked by an orange line where the approach changed.

**Visual:**
```
┌─────────────────────────────────────────────┐
│                                             │
│        8 MONTHS                             │
│        ███████████████████████ ─────── 0    │
│        applications ·····  interviews       │
│                                             │
│   ──────────── ◆ ────────────               │
│            method changed                   │
│                                             │
│        2 WEEKS                              │
│        █████ ─────────────────── ████       │
│        targeted     more replies            │
│                                             │
└─────────────────────────────────────────────┘
```

**Style notes:**
- Top half: gray/muted bars showing 8 months of nothing. "0" in large red text
- Orange diamond marker in the middle = the turning point
- Bottom half: orange bars, shorter time period, visible results
- Minimal, data-visualization feel — like a dashboard metric
- The contrast between gray emptiness and orange results tells the story

---

## Post [2] — The Method: 4 Steps

**Concept:** A clean 4-step flow diagram, each step as a card with an icon and short label. Arrow connections between them.

**Visual:**
```
┌─────────────────────────────────────────────┐
│                                             │
│   THE 4-STEP METHOD                         │
│                                             │
│   ┌──────┐    ┌──────┐    ┌──────┐    ┌──────┐  │
│   │  🔍  │ →  │  👤  │ →  │  📋  │ →  │  ✉️  │  │
│   │ Find │    │ Find │    │  15  │    │Write │  │
│   │signal│    │person│    │ min  │    │ msg  │  │
│   └──────┘    └──────┘    └──────┘    └──────┘  │
│                                             │
│   Job boards: 4-10%    This method: 30-40%  │
│   ████                 ████████████████     │
│                                             │
└─────────────────────────────────────────────┘
```

**Style notes:**
- 4 cards in a horizontal row with arrow connections
- Icons are simple SVG (magnifying glass, person, clipboard, envelope)
- Cards have blue-gray background, orange border on hover/active
- Below: two comparison bars — gray short bar (4-10%) vs orange long bar (30-40%)
- Clean, infographic feel. Not cluttered.

---

## Post [3] — Candidate DNA

**Concept:** A stylized "DNA profile card" showing what the AI extracts — a mock-up of the actual UI output. Skills as tags, a strength/gap section, a vector visualization.

**Visual:**
```
┌─────────────────────────────────────────────┐
│  Day 3/9                                    │
│                                             │
│  ┌─ CANDIDATE DNA ─────────────────────┐    │
│  │                                     │    │
│  │  Career Stage: Senior               │    │
│  │                                     │    │
│  │  Strengths                          │    │
│  │  ● Distributed systems              │    │
│  │  ● API design                       │    │
│  │  ● Team leadership                  │    │
│  │                                     │    │
│  │  Skills  [62 extracted]             │    │
│  │  ┌─────┐ ┌────────┐ ┌──────┐       │    │
│  │  │ Python│ │FastAPI │ │Redis │ ...  │    │
│  │  └─────┘ └────────┘ └──────┘       │    │
│  │                                     │    │
│  │  Gaps                               │    │
│  │  △ Kubernetes (learnable)           │    │
│  │  △ Go (adjacent)                    │    │
│  │                                     │    │
│  │  ═══════════════════ 1536 dims      │    │
│  │  ▓▓▓▒▒▓▓▓▒▓▒▒▓▓▓▒▓  vector        │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  Not keywords. Meaning.                     │
│                                             │
└─────────────────────────────────────────────┘
```

**Style notes:**
- Looks like a product UI card on the dark background — rounded corners, subtle border
- Strengths in green-ish text, Gaps in amber/yellow
- Skills as pill/tag elements in blue-gray with orange borders
- Bottom: a visual representation of the vector — like a small heatmap or barcode pattern in orange/gray
- Tagline at bottom: "Not keywords. Meaning." in orange
- This should look like a real product screenshot (but cleaner/idealized)

---

## Post [4] — Finding Hidden Companies

**Concept:** A mock search results panel showing 3 companies with fit scores and hiring signals — like a dashboard view.

**Visual:**
```
┌─────────────────────────────────────────────┐
│  Day 4/9                                    │
│                                             │
│  DISCOVERED COMPANIES                3 new  │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │ Acme Fintech          Fit: 87%  🟠 │    │
│  │ Series B (2 months ago) · New VP Eng│    │
│  │ 4 backend roles posted              │    │
│  └─────────────────────────────────────┘    │
│  ┌─────────────────────────────────────┐    │
│  │ NovaPay                Fit: 81%  🟠 │    │
│  │ Product launch · Team growing       │    │
│  │ No public job posting yet           │    │
│  └─────────────────────────────────────┘    │
│  ┌─────────────────────────────────────┐    │
│  │ DataBridge             Fit: 74%  🟡 │    │
│  │ Series A · New CTO                  │    │
│  │ No public job posting yet           │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  None of these were on any job board.       │
│                                             │
└─────────────────────────────────────────────┘
```

**Style notes:**
- Dashboard-style card list — looks like the actual product UI
- Each company card has: name, fit score (orange percentage), signal tags
- "No public job posting yet" in orange/amber — this is the key selling point
- Fit scores as colored dots (orange = high, yellow = good)
- Bottom tagline: "None of these were on any job board." in orange
- Clean, SaaS dashboard feel

---

## Post [5] — 90-Second Company Dossier

**Concept:** A mock dossier output showing the sections the AI generates — company profile, signals, culture, contacts, personalized fit. With a timer showing "0:90".

**Visual:**
```
┌─────────────────────────────────────────────┐
│  Day 5/9                          ⏱ 0:90   │
│                                             │
│  COMPANY DOSSIER — Acme Fintech             │
│                                             │
│  ┌── Profile ──┐  ┌── Signals ────────┐     │
│  │ Fintech     │  │ Series B: $18M    │     │
│  │ 120 people  │  │ New VP Eng (Jan)  │     │
│  │ Tel Aviv    │  │ 4 open roles      │     │
│  │ Python/Go   │  │ ████████ HIGH     │     │
│  └─────────────┘  └───────────────────┘     │
│                                             │
│  ┌── Culture ──────────────────────────┐    │
│  │ Score: 7.2/10                       │    │
│  │ ⚠ 1 red flag: work-life balance    │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  ┌── Key Contacts ─────────────────────┐    │
│  │ Sarah K. — Eng Director   ✉ verified│    │
│  │ Tom R.   — Backend Lead   ✉ verified│    │
│  └─────────────────────────────────────┘    │
│                                             │
│  ┌── Why You'd Be a Good Fit ─────────┐    │
│  │ "Your distributed systems exp..."   │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  15-20 min manually → 90 seconds.           │
│                                             │
└─────────────────────────────────────────────┘
```

**Style notes:**
- This is THE money image — it shows the core product value
- Styled as a product screenshot with sections/panels
- Timer "⏱ 0:90" in top-right in orange
- Culture red flag in amber/yellow with warning icon
- Contacts with green checkmarks for "verified"
- "Why You'd Be a Good Fit" section with personalized text preview
- Bottom tagline: "15-20 min manually → 90 seconds." in orange
- Multiple small panels rather than one big wall of text

---

## Post [6] — AI Writes, You Approve

**Concept:** A split view: left shows an AI-generated outreach draft, right shows the approval queue with "Approve / Reject" buttons. The human is in control.

**Visual:**
```
┌─────────────────────────────────────────────┐
│  Day 6/9                                    │
│                                             │
│  ┌── AI Draft ─────────────────────────┐    │
│  │                                     │    │
│  │ Subject: Your Series B and backend  │    │
│  │ scaling                             │    │
│  │                                     │    │
│  │ Hi Sarah,                           │    │
│  │                                     │    │
│  │ I noticed Acme just closed a $18M   │    │
│  │ Series B and you're scaling the     │    │
│  │ backend team...                     │    │
│  │                                     │    │
│  │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │    │
│  │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │    │
│  │                                     │    │
│  └─────────────────────────────────────┘    │
│                                             │
│       ┌──────────┐    ┌──────────┐          │
│       │ ✓ Approve │    │ ✗ Reject │          │
│       └──────────┘    └──────────┘          │
│                                             │
│  Nothing sends until you click.             │
│                                             │
└─────────────────────────────────────────────┘
```

**Style notes:**
- The draft panel looks like an email composer — real text visible at top, blurred/faded at bottom (privacy + mystery)
- "Approve" button in green, "Reject" in muted gray
- The visible text should show real, specific outreach (Series B reference, name, specific detail)
- Bottom tagline: "Nothing sends until you click." in orange
- This image should feel like looking over someone's shoulder at the product

---

## Post [7] — Job Analysis in 30 Seconds

**Concept:** A mock "readiness report" showing the output when you paste a job posting — score, matching skills, gaps, and a cover letter preview.

**Visual:**
```
┌─────────────────────────────────────────────┐
│  Day 7/9                          ⏱ 0:30   │
│                                             │
│  JOB ANALYSIS — Senior Backend Engineer     │
│                                             │
│  Readiness: ████████████░░░░ 72%            │
│                                             │
│  ✓ Matching (8/11)        ✗ Missing (3)     │
│  ┌─────────────────┐     ┌────────────────┐ │
│  │ Python ✓        │     │ Kubernetes ✗   │ │
│  │ FastAPI ✓       │     │ Go ✗           │ │
│  │ PostgreSQL ✓    │     │ GraphQL ✗      │ │
│  │ Redis ✓         │     │                │ │
│  │ Docker ✓        │     │                │ │
│  │ +3 more         │     │                │ │
│  └─────────────────┘     └────────────────┘ │
│                                             │
│  ATS Keywords: 14 identified                │
│  Resume Tips: 3 high priority               │
│  Cover Letter: Generated ✓                  │
│                                             │
│  From a URL. In 30 seconds.                 │
│                                             │
└─────────────────────────────────────────────┘
```

**Style notes:**
- Readiness bar: partially filled, orange portion (72%), gray remainder
- Matching skills: green checkmarks, Missing: red/amber X marks
- ATS keywords, resume tips, cover letter as compact status lines with green checkmarks
- Timer "⏱ 0:30" in top-right
- Bottom tagline: "From a URL. In 30 seconds." in orange
- Clean report/dashboard aesthetic

---

## Post [8] — What AI Gets Wrong

**Concept:** A side-by-side comparison: left shows an AI draft with issues highlighted (too formal, generic phrase, outdated signal), right shows the human-edited version. Honest, not polished.

**Visual:**
```
┌─────────────────────────────────────────────┐
│  Day 8/9                                    │
│                                             │
│    AI Draft              After Human Edit   │
│  ┌─────────────┐      ┌─────────────┐      │
│  │              │      │              │      │
│  │ "I would be  │  →   │ "Your Series │      │
│  │  honored to  │      │  B caught my │      │
│  │  explore..." │      │  eye — I've  │      │
│  │              │      │  built..."   │      │
│  │  ⚠ too formal│      │  ✓ specific  │      │
│  │  ⚠ generic   │      │  ✓ personal  │      │
│  │  ⚠ stale ref │      │  ✓ current   │      │
│  └─────────────┘      └─────────────┘      │
│                                             │
│        80% AI research + structure          │
│        20% human judgment + voice           │
│                                             │
│  ═══════════════════════                    │
│  ████████████████████ ░░░░░                 │
│  AI handles this      You handle this       │
│                                             │
└─────────────────────────────────────────────┘
```

**Style notes:**
- Left panel: gray/muted, with amber warning icons marking issues
- Right panel: clean, green checkmarks
- Arrow between them showing the human edit step
- Bottom: an 80/20 split bar — large orange section (AI) + small blue-gray section (human)
- The imperfection is the point — shows honesty about limits
- Not over-designed — slightly rougher than the other images to match the "honest" tone

---

## Post [9] — Beta Tester Ask

**Concept:** Simple, direct, bold. Large text asking for help. Not a product launch announcement — a builder asking for feedback.

**Visual:**
```
┌─────────────────────────────────────────────┐
│                                             │
│                                             │
│                                             │
│         Looking for                         │
│         2-3 job seekers                     │
│         to break this.                      │
│                                             │
│                                             │
│    Free access. Honest feedback.            │
│    That's the deal.                         │
│                                             │
│                                             │
│              DM me.                         │
│                                             │
│                                             │
│                                             │
└─────────────────────────────────────────────┘
```

**Style notes:**
- Intentionally minimal — massive whitespace (on dark background)
- "2-3 job seekers" in large orange text
- "to break this." in white
- "Free access. Honest feedback. That's the deal." in smaller muted text
- "DM me." in orange at the bottom, slightly larger
- No product screenshots, no features, no icons. Just the ask.
- This should stand out in the feed BECAUSE it's different from the other images

---

## Implementation Notes

### Build as HTML/CSS
All images should be created as a single `linkedin-images.html` file:
- Each image is a `<div>` sized at 1200x627px
- Use Google Fonts (Outfit + JetBrains Mono) via CDN
- CSS variables for the color palette
- Screenshot each div for the final PNG

### Text rendering
HTML/CSS gives perfect text every time — no AI garbling. This is the main advantage over Midjourney/DALL-E.

### Screenshots
- Open in Chrome at 100% zoom
- Use DevTools "Capture node screenshot" on each card div
- Or use a screenshot tool that captures at exact dimensions

### File naming
```
linkedin-teaser.png
linkedin-day1-origin.png
linkedin-day2-method.png
linkedin-day3-dna.png
linkedin-day4-companies.png
linkedin-day5-dossier.png
linkedin-day6-outreach.png
linkedin-day7-analysis.png
linkedin-day8-honest.png
linkedin-day9-beta.png
```
