# LogosDepth Roadmap: From Prototype to Launch

Drafted 22 Oct 2026. Companion docs: `memory-science.md` (evidence), `sources.md` (source registry).

**How to read this:** phases are ordered by dependency, not by calendar. Effort is in focused developer-weeks for one full-time person; if you work part-time, multiply. Everything marked **Decision** needs your call, and I give a recommendation with each. Anything I haven't verified (laws, store rules, pricing) is marked **verify**.

---

## 1. Product thesis

> **Help beginners memorize scripture word-for-word, and keep it, using methods with strong scientific support, and let them go deeper into the original Hebrew and Greek behind each verse.**

Three things set this apart from a generic flashcard app:
1. **Evidence-first mechanics.** Only levers with strong support ship (spaced retrieval, typed recall, successive relearning). We don't make claims the science doesn't back.
2. **Beginner-friendly guided learning** (read → fill → order → recall → type) before the review loop.
3. **Original-language depth** linked to each verse (83 lexicon words today).

**Decision 1: lead with which?** Today the app reads as a Hebrew/Greek word tool with a memory game bolted on. *Recommendation:* lead with **memorization** and present the lexicon as "understand the words behind your verse." That is the stronger, clearer hook.

### Principles
- **Evidence over hype.** Features need support in `memory-science.md` at the "strong" level, or ship as clearly labeled experiments.
- **Honest claims.** No health or brain-benefit promises. Say what the evidence shows.
- **Local-first, privacy-respecting.** Learners' spiritual lives are sensitive; collect little.
- **Free core.** The core memorization loop shouldn't sit behind a paywall (see Decision 5).

---

## 2. Where we are today

| Area | State |
|---|---|
| **Stack** | Flask backend, vanilla JS/CSS frontend, JSON data files; no build step |
| **Content** | 83 Hebrew/Greek lexicon entries; 27 KJV verses linked to lexicon words |
| **Learning loop** | Guided 5 steps, typed recall, daily spaced review (1/3/7/14/30/60/120 days), mastery = recall on 3 days, XP/level/streak |
| **Persistence** | Browser `localStorage` only (per device, lost if cleared) |
| **Quality** | 25 unit tests (`tests/test_recall.js`); 75-check browser test (`tests/e2e.py`); no CI |
| **Missing for launch** | Accounts/sync, backups, notifications/reminders, production hosting config, README/docs, legal pages, analytics, onboarding, more content, accessibility audit, store presence |
| **Known risks in code** | `app.run(debug=True)` in `app.py` (never ship); no rate limiting, security headers or error monitoring; Google Fonts loaded from a third party |

---

## 3. Phases at a glance

| Phase | Goal | Effort | Exit criteria |
|---|---|---|---|
| **0. Foundations** | Safe, documented, testable repo; key decisions made | 1–2 wks | CI green; README; production config; content license audit; decisions 1–6 recorded |
| **1. Product hardening (local-first MVP)** | A beginner can use it daily without losing progress | 4–6 wks | Backup/export, PWA + reminders, onboarding, 100+ verses, a11y pass |
| **2. Accounts & sync** | Same progress on every device | 3–5 wks | Sign-in, server storage, conflict-safe sync, delete-my-data |
| **3. Private beta** | Prove people stick with it and retain verses | 4–6 wks | 50–100 real users; retention + recall metrics collected; top issues fixed |
| **4. Public launch** | Open to everyone, supported, discoverable | 3–4 wks | Live domain, monitoring, legal pages, landing page, support channel |
| **5. Growth & depth** | Expand content and evidence-backed features | ongoing | Driven by beta/launch data |

**Rough total to public launch: 15–23 focused weeks (~4–6 months full-time).** Phases 1 and 2 can overlap partially; Phase 3 should not start before the Phase 1 exit criteria are met.

---

## Phase 0: Foundations (1–2 weeks)

**Engineering**
- Write a real `README.md`: what it is, run locally, run tests, data files, how to add a verse. *(S)*
- Pin dependencies; add a `requirements-dev.txt` (Playwright). Add `Procfile`/`gunicorn` config. *(S)*
- **Remove `debug=True` from the production path**; read config from environment variables (`FLASK_ENV`, secret key, etc.). *(S)*
- **CI** (GitHub Actions): run `node tests/test_recall.js` and the Playwright e2e on every push/PR. *(M)*
- Add a linter/formatter (Ruff for Python; ESLint or Prettier for JS). *(S)*
- Vendor the fonts (self-host) so the app works offline and doesn't leak visitor IPs to Google. *(S)*
- Add a data-validation test for `verses.json` and `lexicon.json` (schema, no broken Strong's IDs). *(S)*

**Content & legal**
- **Audit the source and license of `lexicon.json`** (definitions, Strong's data, transliterations). I did not check where this data came from. If any of it is copied from a copyrighted lexicon, fix it before launch. **verify** *(M)*
- Confirm the **KJV** status for your target markets. It is generally treated as public domain in the US, but the UK has separate rules for the KJV. **verify with counsel** *(S)*
- Pick additional public-domain translations (e.g., World English Bible, ASV) for the roadmap; list which modern translations would need licenses. **verify** *(S)*

**Research (cheap, high value)**
- **Competitor scan** (I haven't done one): list 8–10 scripture-memory and spaced-repetition apps, their pricing, strengths and gaps. *(M)*
- Interview 5–8 target users (new believers, small-group leaders, students) about how they memorize now and what makes them quit. *(M)*

**Decisions to record**
| # | Decision | Recommendation |
|---|---|---|
| 1 | Lead product with memorization or lexicon | Memorization first |
| 2 | Platform | **PWA first**, store apps later via a wrapper (Phase 5) if demand warrants |
| 3 | Audience | **Adults and teens**; avoid under-13 users at launch (child-privacy law adds big cost; **verify**) |
| 4 | Data model | **Local-first with optional account** for sync |
| 5 | Monetization | See "Business model" below |
| 6 | Translations at launch | KJV + one more public-domain translation (WEB or ASV) |

**Exit:** CI green, README done, production config safe, license audit complete, decisions logged.

---

## Phase 1: Product hardening, local-first MVP (4–6 weeks)

Goal: a beginner can learn, review daily, and **never lose progress**, even without an account.

### 1A. Learning features (evidence-backed first)
From the remaining items in the evidence roadmap. Build only the ones with strong support first:

| Item | Evidence | Effort |
|---|---|---|
| **Quiz after each phrase while learning** (not only at the end) | Meta-analysis, g ≈ 0.25 (see `memory-science.md` §6) | M |
| **Say-it-aloud prompt** before typing | Production effect; moderate support | S |
| **"Guess the next phrase" pretest option** | Prequestion meta-analysis: g ≈ 0.54 on the tested content | M |
| **Meaning prompt** ("say it in your own words"), optional | Self-reference/elaboration; moderate | S |
| **Keep related verses in the same review rotation** | Retrieval-induced forgetting; mechanism debated | S |
| **Beginner scaffolding that fades** (cue levels: full text → first letters → none) | Desirable-difficulty framing; learner must be able to succeed | M |

Not building (evidence too weak or poorly matched): movement/arousal features, learning-style modes, melody claims, brain-benefit claims.

### 1B. Don't-lose-your-progress
- **Export/import progress** as a JSON file (the simplest, most reliable backup before accounts). *(S)*
- Detect cleared/unavailable storage and warn users. *(S)*
- Data versioning: add a `schemaVersion` to stored data and write migrations. *(S)*

### 1C. Habit support
- **PWA**: manifest, service worker, offline use, install prompt. *(M)*
- **Review reminders** (web push where supported; fallback to email later in Phase 2). Notifications are *my hypothesis* for improving review adherence; I have not researched the evidence for reminders, so **A/B test this in beta**. *(L)*
- A simple **"daily goal"** and streak display (exists: streak). Add a freeze/grace mechanic only if beta data shows streak anxiety. *(S)*

### 1D. Onboarding & UX
- First-run walkthrough (3 screens: how it works, learn your first verse, set a reminder time). *(M)*
- Pick-a-starter-pack screen (e.g., "Gospel basics", "Psalms of comfort", "Short verses to start"). *(M)*
- Clear settings page: reminder time, translation, reset data, export. *(M)*
- Error and empty states everywhere (offline, no verses due, failed fetch). *(S)*

### 1E. Content
- Grow from **27 → 100+ verses** organized into packs (topic, book, difficulty), with **verse-level metadata** (translation, copyright line). *(L)*
- Add a second public-domain translation. *(M)*
- Expand lexicon links for verses (currently two verses have none). *(M)*
- Editorial review process for every verse's text (verify against a trusted source, with a checksum or second-person check). **I wrote the current verse texts from memory; they need a proofread against a source.** *(M)*

### 1F. Quality
- Accessibility audit: keyboard navigation, focus order, contrast, screen-reader labels, reduced motion (partly done), 200% zoom. Target **WCAG 2.2 AA** as a goal. *(M)*
- Performance budget: first load fast on mid-range phones over 4G. *(S)*
- Browser matrix: Safari iOS, Chrome Android, desktop Chrome/Firefox/Safari. *(M)*

**Exit:** progress backup works; installs as a PWA; reminders work on at least Chrome/Android; onboarding done; 100+ verses proofread; a11y pass complete; CI covers all new behavior.

---

## Phase 2: Accounts & sync (3–5 weeks)

Goal: same progress on phone and laptop, safely.

- **Backend data model:** users, verse cards (stage, due, recall days, lapses, last date), XP/streak, settings. Migrate from SQLite (dev) to **Postgres** (prod). *(L)*
- **Authentication:** email magic link or passkeys; optionally Google/Apple sign-in. Avoid building password storage yourself; use a vetted auth provider or library. *(L)*
- **Sync design:** local-first with per-card merge. The scheduling model is already per-card, so merging is straightforward: for each verse, keep the record with the later `lastDate`, and union the `days` sets. Write unit tests for conflicts (two devices, same day). *(L)*
- **Guest → account upgrade** that carries over local progress. *(M)*
- **Privacy features:** "export my data" and "delete my account and data" in the app. *(M)*
- **Email reminders** as a fallback channel (with one-click unsubscribe). *(M)*
- **Security basics:** HTTPS only, secure cookies, CSRF protection, rate limiting on auth, security headers/CSP, dependency scanning. *(M)*
- **API hardening:** versioned API; input validation; pagination. *(M)*

**Exit:** sign in on two devices and see the same schedule; conflict tests pass; delete-my-data works; security checklist complete.

---

## Phase 3: Private beta (4–6 weeks)

Goal: learn whether people *stick with it* and *retain what they memorize*, before spending on launch.

**Recruit 50–100 people** through churches, small groups, campus ministries and your network. Include complete beginners. Get **informed consent** for any measurement.

**What to measure (privacy-respecting analytics, e.g., self-hosted or privacy-first tools; no ad trackers):**

| Metric | Why |
|---|---|
| Day-1, Day-7, Day-30 return rate | Do people come back? |
| Reviews completed vs. due (adherence) | Does the schedule fit real life? |
| First-attempt recall success rate per review stage | Is it too hard or too easy? Evidence says practice should be winnable |
| Verses mastered per active user per month | Core outcome |
| Delayed typed recall at 7 and 30 days after learning | The app's own **efficacy** evidence |
| Reminder opt-in and open rates | Test the reminder hypothesis |
| Drop-off point in onboarding | Fix friction |

**Experiments worth running (randomized, with consent):**
1. Reminders on vs. off → review adherence.
2. Interval ladder A (current) vs. a gentler or tighter ladder → 30-day recall. (The literature supports spacing but not a specific pattern; this is where your own data can add something.)
3. Cue-fading scaffolding vs. fixed difficulty → completion and recall.

**Support loop:** in-app feedback button, a weekly bug triage, a public changelog, and short user interviews (5–10).

**Exit criteria (set targets before you start; examples):**
- Day-7 return ≥ 35% and Day-30 ≥ 15% *(placeholders; calibrate from the competitor scan)*
- ≥ 70% first-attempt recall success on reviews at stage ≥ 1
- No known data-loss bugs; crash-free rate ≥ 99%
- You can state, truthfully, what share of learned verses were still recalled at 30 days

---

## Phase 4: Public launch (3–4 weeks)

**Infrastructure**
- Host the Flask app (managed platform such as Render, Fly.io or Railway) with Postgres, automated backups, and a staging environment. **verify current pricing/limits** *(M)*
- Custom domain, TLS, CDN for static files. *(S)*
- Monitoring: uptime checks, error tracking (e.g., Sentry), basic dashboards, alerts. *(M)*
- Backup **restore drills** (test that you can recover). *(S)*

**Legal & trust (get counsel for these; I can't verify the rules)**
- Privacy policy and terms of service; cookie/consent handling if you use anything beyond essential storage. *(M)*
- Data-protection basics for users in the EU/UK/California. **verify** *(M)*
- Scripture copyright notices for each translation shown. *(S)*
- An "About the science" page that cites sources from `sources.md` and says plainly what is and isn't known. *(S)*

**Go-to-market**
- Landing page: one clear promise, a 30-second demo, "try a verse now" without signing up. *(M)*
- App-store listings only if you take the wrapper route (see Phase 5). *(—)*
- Launch channels (hypotheses to test): church and small-group leaders, Christian campus groups, Christian newsletters/podcasts, communities for new believers, SEO for "how to memorize scripture". *(L)*
- Press kit and a short founder story. *(S)*

**Support readiness:** FAQ, contact email, response-time goal, a public status page. *(S)*

**Exit:** production live with monitoring; legal pages published; landing page converts; you can handle support requests; rollback plan tested.

---

## Phase 5: Growth & depth (ongoing)

Prioritize using beta/launch data. Candidates:

| Candidate | Notes |
|---|---|
| **More translations** | Requires licenses for modern ones (NIV, ESV, NLT, etc.). Check each publisher's terms **verify** |
| **Audio** | Listen + repeat; supports the production effect. Licensing for recordings matters |
| **Passage and chapter memorization** | Chunk into verses; long-text memorization is a gap in the research, so measure it yourself |
| **Native iOS/Android** | Wrap the PWA (e.g., with Capacitor) once there is demand. **verify** store rules, fees and push-notification behavior on iOS PWAs |
| **Small groups & accountability** | Shared packs, group streaks, leader dashboard. Privacy-sensitive |
| **Smarter scheduling** | Replace the fixed ladder with a model fitted to real data (adaptive scheduling had a large randomized trial, Upadhyay 2021, but on factual content) |
| **Memory-palace mode** | For memorizing the *order* of many verses; evidence is promising but low-certainty |
| **Deeper lexicon** | More words, cross-references, word-study pages |
| **Localization** | Other languages and translations |
| **Teacher/leader tools** | Assign packs, track progress |
| **Widgets / lock-screen reviews** | Habit reinforcement; test first |

---

## Business model (Decision 5)

Hypotheses, not facts. Validate in beta.

| Option | Pros | Cons |
|---|---|---|
| **Free + donations/"supporter" tier** | Fits ministry ethos; low friction; builds trust | Revenue unpredictable |
| **Freemium subscription** (free core loop; paid extras like audio, extra translations, groups, advanced stats) | Predictable revenue; aligns cost with value | Risk of seeming to paywall scripture |
| **Church/organization licenses** | Larger deals; built-in distribution | Longer sales cycle; needs admin features |
| **One-time purchase** | Simple | No recurring revenue to fund hosting and licenses |

*Recommendation:* start **free** through beta; at launch use **free core + optional paid extras and a supporter tier**; explore **church licenses** after Phase 5 group features exist. Never put the evidence-backed core loop behind a paywall, and never use ads.

---

## Cross-cutting workstreams

| Workstream | Ongoing responsibilities |
|---|---|
| **Evidence & science** | Keep `memory-science.md`/`sources.md` current; verify the 10 priority papers; re-test assumptions with your own beta data |
| **Content & editorial** | Proofreading; licensing log per translation; verse metadata; consistent style |
| **Engineering quality** | CI; test coverage for scheduling and sync; dependency updates; security scans |
| **Design & accessibility** | Design system tokens; WCAG 2.2 AA; usability tests each phase |
| **Privacy & legal** | Data minimization; consent; retention policy; counsel review before launch |
| **Community & trust** | Transparent changelog; honest claims; respond to feedback |

---

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **Users stop reviewing** (the schedule only works if they show up) | Core value lost | Reminders (A/B tested), short sessions, gentle streak design, easy re-entry after missed days |
| **Content licensing problem** (lexicon or translation) | Takedown or legal exposure | Audit early (Phase 0); public-domain first; license log |
| **Verse text errors** | Loses trust fast | Source-checked proofread; user "report an error" button |
| **Data loss** (localStorage cleared) | Lost progress, churn | Export now; sync in Phase 2 |
| **Overstated science claims** | Credibility risk | Claims reviewed against `sources.md`; "About the science" page |
| **Beginners find typing hard** | Drop-off | Cue levels and scaffolding that fade; first-letter hint; success-rate monitoring |
| **Evidence gap for long verbatim text** | Unknown effectiveness | Measure recall in beta; share findings honestly |
| **Solo-developer bottleneck** | Delays | Ruthless scope; CI; phases with exit criteria |
| **Privacy sensitivity** (religious data) | Reputational harm | Minimal collection; no ad tech; clear policy; delete-my-data |
| **Competitors** | Hard to differentiate | Competitor scan; lean on evidence-first + original-language depth |

---

## Next 10 actions (this week and next)

1. Write `README.md` and add CI running the unit and e2e tests.
2. Remove `debug=True` from the production path; add environment-based config.
3. **Audit the source and license of `lexicon.json`.**
4. Proofread all 27 verses against a trusted KJV source.
5. Record Decisions 1–6.
6. Do the competitor scan (8–10 apps).
7. Interview 5 target users.
8. Build progress export/import.
9. Build "quiz after each phrase while learning" (best-supported remaining feature).
10. Self-host fonts and verify the app works offline.

---

## Launch checklist (for Phase 4)

- [ ] CI green on main; e2e passes against staging
- [ ] `debug` off; secrets in environment; HTTPS enforced
- [ ] Postgres backups automated; **restore tested**
- [ ] Error tracking and uptime monitoring live; alerts routed to you
- [ ] Privacy policy, terms, scripture copyright notices published
- [ ] "Delete my data" and "export my data" work end to end
- [ ] Accessibility pass complete; keyboard-only run-through done
- [ ] Verse texts proofread; lexicon license confirmed
- [ ] Landing page, "About the science" page, FAQ, contact email, status page
- [ ] Rollback plan written and rehearsed
- [ ] Beta exit metrics met and recorded
- [ ] Launch announcement and first 5 outreach conversations scheduled

---

## Assumptions I made (correct me)

- One developer (you), building alongside a day job or school, with me assisting.
- Web-first audience of English-speaking adults and teens; no children under 13 at launch.
- No venture funding; low-cost hosting.
- Faith-community distribution is the primary channel.
- Timelines are rough planning ranges, not commitments.
