# JobMarket AI — Phase 0 through Phase 14

AI-Powered Job Market & Skill Intelligence Platform.
This delivery covers **Phase 0 (foundation)** through **Phase 14
(UI polish, accessibility, migrations & deployment)** from the roadmap.

## What's new in this delivery (UI Polish, Accessibility & Deployment)

This phase does not add user-facing features — it hardens the application
for real-world deployment and makes it usable with a keyboard or screen
reader, not just a mouse:

- **Database migrations (Flask-Migrate / Alembic).** Every previous phase
  relied on `db.create_all()` at app startup — convenient for local dev,
  but unsafe for a production database that already holds real data and
  needs versioned, reviewable schema changes. `migrations/` now holds a
  baseline revision generated against a genuinely empty database (verified
  to create all 29 app tables plus `alembic_version`), and `flask db
  upgrade` is the documented, tested way to apply schema in production. The
  app detects `flask db ...` invocations and skips its own `create_all()`/
  seed bootstrap in that case, so Alembic's autogenerate sees a true diff.
  `db.create_all()` is still used for local dev/test convenience (and in
  the test suite), but production deployment now goes through migrations —
  see `docs/DEPLOYMENT.md`.
- **`/health` endpoint** for load balancers and uptime monitors. Returns
  `200 {"status": "ok", "checks": {"database": true}}` when the database
  is reachable, `503` with `"status": "degraded"` otherwise. No
  authentication required, by design.
- **Accessibility pass**: a "Skip to main content" link (visible on
  keyboard focus) so keyboard users can bypass the navigation bar; a
  labeled `<main id="main-content">` landmark; `aria-label="Primary"` on
  the main nav; visible `:focus-visible` outlines on every interactive
  element (links, buttons, inputs, selects, textareas) in both light and
  dark themes; and a `prefers-reduced-motion` media query that disables
  animations/transitions for users who've asked their OS for reduced
  motion.
- **Responsive tables**: every `<table>` across the app (20 tables across
  17 templates — admin panels, job/resume lists, reports, the application
  tracker, advanced insights) is now wrapped in `.table-responsive`, so
  wide tables scroll horizontally on narrow screens instead of breaking
  the layout. A regression test (`test_no_unwrapped_tables_in_templates`)
  scans the whole template tree so a future table can't be added without
  the wrapper.
- **`docs/DEPLOYMENT.md`**: environment variables (what's required vs.
  optional and why), the migration workflow, running under gunicorn
  instead of the Flask dev server, the `/health` endpoint, upload/log
  storage persistence, and a production launch checklist.
- **14 new tests** (`tests/test_phase14_deployment.py`) covering the
  health endpoint, migration files and wiring, accessibility markers in
  rendered HTML, the responsive-table audit, and presence of the
  deployment doc's key sections. Full suite: **270/270 passing**.

No existing route, model, or template behavior changes as a result of this
phase — it is purely additive (new endpoint, new docs, new tests) and
structural (migrations replacing ad-hoc schema creation for production,
markup wrapping for tables) rather than a feature change.

## A phase-numbering correction, worth being upfront about

This delivery's "Phase 8" actually built what the original roadmap
labeled **Phase 10** (Job Search, Saved Jobs & Application Tracker) — a
drift that happened while working through requests in sequence. That
means the original **Phase 8, Career Roadmap & Recommendations, was
skipped**, and Phase 9 (AI Career Assistant) matched the original
numbering correctly. This delivery — labeled "Phase 10" in our ongoing
sequence — builds that skipped content. Going forward, the phase
descriptions below refer to *what was actually built*, not necessarily
matching the original roadmap document's numbers one-to-one; treat the
section headers as a build log rather than a strict cross-reference.

## What's new in this delivery (Advanced NLP & Forecasting)

This is the roadmap's explicitly **optional / post-MVP** phase, and its
stated constraint was that these features "must be implemented modularly
and should not break the core application." A dedicated test
(`test_advanced_features_do_not_affect_core_pages`) asserts every core
page still returns 200, and all 239 pre-existing tests passed unchanged
after this phase was added.

- **Skill relationship graph** (`/advanced/skill-graph`): an interactive
  D3 force graph where an edge means those two skills genuinely appeared
  together in 2+ of the same job postings — built from Phase 5's real
  co-occurrence data, nothing inferred. Isolated nodes are dropped so the
  graph never renders a field of disconnected dots implying "no
  relationships" when a skill simply wasn't co-mentioned enough. Also
  exposed as JSON at `/advanced/skill-graph.json`.
- **Semantic job clustering** (`/advanced/clusters`): TF-IDF + KMeans
  over analyzed job text — deliberately the same classical vector-space
  approach Phase 6 already uses, rather than introducing a second,
  heavier embedding stack for one optional feature. **Cluster labels are
  not invented**: each is described by its own highest-weighted TF-IDF
  terms and the skills that actually occur most in that cluster.
- **Skill demand forecasting** (`/advanced/forecast`) — see the section
  below, because this one needed the most care.
- **Multi-resume comparison** (`/advanced/compare-resumes`): put two or
  more of your own resume versions side by side (skills, parsed
  experience/education/sections, skills unique to each version), and
  optionally score them all against a job reusing Phase 6's real
  matching engine rather than inventing a second metric.
- 17 new tests (`tests/test_advanced.py`).

### The forecasting feature is deliberately hard to trigger

Forecasting is the single feature in this whole project most capable of
producing confident-sounding nonsense, so the gating is strict on
purpose. The spec says "do not claim real-world growth percentages unless
calculated from actual collected data" — and a *forecast* is a claim
about the future, which is a stronger claim still.

So `forecast_skill_demand()` requires **3+ months of history with 3+
analyzed jobs each** before it will project anything at all. It also:

- projects only **one month ahead** (short horizons are the only honest
  ones at this data volume),
- uses plain **linear extrapolation**, and names that method in the UI so
  nobody mistakes it for something more sophisticated,
- returns a **volatility band** per skill, derived from how much that
  skill's observed demand actually moved — a noisy series is labelled as
  such rather than presented with false precision,
- only forecasts skills present in **every** month used, since a skill
  that appeared once has no series to fit,
- states in the UI that it is "an estimate based on this deployment's own
  collected data — not a market prediction, and not based on any external
  data source."

**On a fresh deployment this feature will correctly refuse to produce a
forecast, and that is the intended behaviour.** Verified live: after
analyzing 8 jobs in a single month, the skill graph and clustering both
light up with real results while the forecast still declines — because 8
jobs in one month is not three months of history. A separate test
backdates jobs across three real months to prove the projection genuinely
works once the data justifies it.

## What's new in this delivery (Admin Panel & Security Hardening)

- **Audit logging** (`ActivityLog` + `app/services/auth/audit.py`):
  registration, successful/failed logins, disabled-account login
  attempts, password changes, password resets, account deletion, and
  every admin action are recorded with actor, action, IP, and a short
  non-sensitive description. Two design decisions worth calling out:
  - The `user_email` is **denormalized onto the log row**, and the FK is
    `ON DELETE SET NULL` with no cascade — so **deleting an account
    cannot erase its audit trail**. A trail that a user can wipe by
    deleting themselves isn't a trail. Covered by a dedicated test.
  - `_redact()` is a **defensive backstop** that strips anything
    resembling a password, API key, or bearer token even if a future
    caller passes one in by mistake. Also covered by a test.
- **Admin panel**: an overview dashboard (real counts across users,
  resumes, jobs, matches, conversations, roadmaps, audit entries, plus
  recent failed logins), a searchable user list, and a filterable audit
  log viewer — alongside the taxonomy, data import, AI status, and
  learning resource pages from earlier phases.
- **User management**: enable/disable accounts and grant/revoke admin
  rights. **An admin cannot disable or de-admin their own account** —
  doing so would lock them out with no UI path back, so it's blocked
  explicitly rather than left as a footgun. Disabled users are genuinely
  blocked at login (verified end-to-end, not just at the DB level).
- **Security headers** on every response via an `after_request` hook:
  `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`,
  `Permissions-Policy`, and a `Content-Security-Policy` scoped to the
  CDNs this app actually uses. `Strict-Transport-Security` is set **only
  outside debug mode** — pinning HSTS from a plain-HTTP dev server would
  actively harm developers, so that's a deliberate conditional (tested).
- A proper **403 page** (previously Flask's raw default).
- 18 new tests (`tests/test_admin_security.py`) plus 1 CSRF-coverage test.

### An honest note on the CSP

The policy includes `'unsafe-inline'` for scripts and styles, because
several templates still use small inline `<script>`/`style` blocks.
Removing it would require moving every inline block to a static file —
genuinely worth doing, but it's a real refactor across many templates
rather than something to slip in silently here. Flagging it explicitly
rather than shipping a CSP that looks stricter than it is.

## What's new in this delivery (Reports, ATS Analysis & Resume Improvement)

- **Report export** (`/reports/`) in **PDF, CSV, and JSON** for five
  report types: resume analysis, resume-job match report, skill gap
  report, career roadmap, and a market analysis snapshot. Every exporter
  reads data that *already exists* in the database from earlier phases —
  `generator.py` computes nothing new, so an exported report can never
  disagree with what the user sees on screen.
- **ATS-style analysis** (`/reports/ats/<report_id>`): keyword coverage
  with the specific missing terms listed, required-skill coverage, job
  title alignment, section structure, and formatting problem detection
  (no email detected, no experience entries parsed, suspiciously short
  text, etc.). Every check is a real, explainable heuristic — no AI call,
  no invented score. **The spec-mandated disclaimer is rendered on the
  page and covered by a test** that asserts the exact wording is present.
- **Resume improvement** (`/reports/improve/<resume_id>`): two layers.
  The deterministic layer (always available, zero config) flags missing
  sections, weak bullet points (no action verb / no measurable outcome /
  too short), and — when analyzed against a specific job — missing
  keywords and skills. A test asserts that **every flagged bullet is real
  text that actually appears in the resume**, guarding against the
  analysis drifting into invented content.
- The **optional AI layer** follows Phase 9's graceful-degradation
  contract exactly (distinct messages for "no provider configured" vs.
  "provider call failed"), and its system prompt explicitly forbids
  inventing experience, education, certifications, or achievements — a
  test asserts that instruction is actually present in the prompt sent
  to the provider.
- 19 new tests (`tests/test_reports.py`) plus 1 new CSRF-coverage test.

## A dependency that had been missing from requirements.txt

While building this phase, the sandbox filesystem reset twice
mid-session. Recovering from the previously delivered zip surfaced a real
latent bug: **`fpdf2` (used for PDF export) had been installed ad-hoc in
an earlier phase but never added to `requirements.txt`.** A fresh clone
would have installed cleanly and then failed at runtime the moment anyone
tried a PDF export. It's now pinned in `requirements.txt` and verified by
a full fresh-clone install + test run. Worth flagging because it's
exactly the class of bug that "works on my machine" hides.

## What's new in this delivery (Career Roadmap & Recommendations)

- **Career Roadmap** (`/roadmap/`): a month-by-month skill plan built
  entirely from real data — it aggregates skill gaps across *every* one
  of the user's resume-job match reports (Phase 6), deduplicates by
  skill (keeping the more urgent classification if a skill shows up as
  both "critical" in one match and "important" in another), and paces
  them one per month, most urgent first. If a user has no match reports
  yet, the page says so plainly and links to where to create one —
  there is no generic/fallback roadmap shown when there's no real data
  to build one from.
- **Progress tracking**: mark each roadmap skill as not started /
  learning / completed. **Regenerating the roadmap preserves this
  progress** for any skill that appears in both the old and new
  roadmap — running a fresh match report shouldn't silently reset
  progress on a skill the user is already partway through.
- **Learning resources**: curated, real official-documentation links per
  skill (Python → docs.python.org, Docker → docs.docker.com, etc.) —
  **never a fabricated or guessed course link**, per the spec's explicit
  instruction. A skill with no curated resource yet honestly shows
  nothing rather than a made-up one (verified by a dedicated test).
  Admins can add more resources (courses, books, tutorials, practice
  platforms) via `/admin/learning-resources`, extending this the same
  way the skill taxonomy itself is extended.
- **Project recommendations**: deterministic template generation over
  the same real gap data — groups the most urgent missing skills into
  small clusters and describes a concrete project combining them, with
  difficulty and time estimated by how many skills are involved. This
  is intentionally *not* an AI-generated feature: it works identically
  with zero configuration, and a test explicitly verifies every
  technology named in every recommendation is drawn from real gap data,
  never invented. (A future phase could add an optional AI-enhanced
  variant behind the same graceful-degradation pattern Phase 9
  established, without touching this deterministic baseline.)
- 18 new tests (`tests/test_roadmap.py`) plus 1 new CSRF-coverage
  regression test.

## What's new in Phase 9

- **AI Career Assistant** (`/assistant/`): a chat interface backed
  entirely by Phase 7's `AIProviderManager` — this is the first
  user-facing feature to actually call it. Ask things like "what skills
  do I need for my target role?" or "what should I learn next?", with
  follow-up questions in the same conversation thread.
- **Grounding is structured retrieval, not vector-embedding RAG** — and
  that's a deliberate choice, documented in
  `app/services/assistant/context_builder.py`: each user's own data
  (profile, skills, resumes, analyzed jobs, match reports, saved jobs) is
  small and already fully structured in the database, so a direct,
  capped structured summary is the cheapest suitable method and more
  auditable than similarity search would be here. The system prompt
  explicitly instructs the model to answer *only* from that data and say
  so plainly when something isn't covered, rather than inventing
  specifics about the user's resume or scores.
- Asking about a specific job (a new "Ask the assistant about this job"
  button on the job browse page) includes that job's full structured
  details in the context for that turn — verified with a test that
  checks the system prompt actually contains the job's title and
  required skills, not just a generic mention.
- **Graceful degradation, not a fake feature**: with no AI provider
  configured (the default in this environment — see the Phase 7 honesty
  section below), starting a conversation still works and stores a clear
  explanation rather than crashing or pretending to answer. If a
  provider *is* configured but a specific call fails, a distinct, more
  generic message is shown — the assistant doesn't conflate "nothing is
  set up" with "something went wrong right now."
- 13 new tests (`tests/test_assistant.py`) plus 1 new CSRF-coverage
  regression test — all using the same mocked-HTTP-response pattern
  established in Phase 7's provider tests.

## A real bug found and fixed this phase (root cause, not a workaround)

A follow-up-question test failed with garbled conversation history: the
prompt sent to the (mocked) model showed the *new* question twice and
completely dropped the *original* first question, even though the
database itself had the correct data in the correct order the whole
time. Root cause, confirmed by direct reproduction outside the HTTP
layer: **SQLAlchemy's dynamic relationship `.order_by()` appends to the
relationship's own configured default ordering rather than replacing
it.** `AIConversation.messages` is defined with `order_by="AIMessage.id"`
(ascending) for normal display purposes; calling
`conversation.messages.order_by(AIMessage.id.desc())` inside the history
builder didn't override that — it silently became `ORDER BY id ASC, id
DESC`, which is still just ascending order since `id` is already unique.
The `.reverse()` and `[:-1]` slicing that followed then operated on the
wrong ordering, corrupting the history. Fixed by querying `AIMessage`
directly (`AIMessage.query.filter_by(...)`) instead of through the
relationship, which has no default ordering to silently interfere.
This is a general SQLAlchemy gotcha worth remembering for any future
code that needs a *different* order than a relationship's configured
default — go through the model's query, not the relationship attribute.

## What's new in Phase 8

- **Job Search** (`/jobs/search`): filterable search — title/company
  keyword, location, remote status, employment type, max experience
  required, min salary — across the **shared pool of every completed
  job in the system**, not just your own. This deliberately extends the
  precedent set in Phase 5 (job posting content isn't private data about
  whoever submitted it): a new read-only `browse_detail` view lets any
  logged-in user see any completed job's full details, distinct from the
  original ownership-gated `/jobs/<id>` page (which still requires
  ownership for edit/delete/reprocess). Verified this distinction with a
  dedicated pair of tests — public browse succeeds for a non-owner (200),
  the private analysis page still returns 403.
- **Saved Jobs** (`/saved-jobs/`): save any job from search (idempotent —
  saving twice doesn't duplicate), with private notes, application date,
  and interview date. Two users can independently save the same
  underlying job with completely separate notes/status — verified that
  neither can see the other's.
- **Application Tracker** (`/saved-jobs/tracker`): funnel counts (Saved /
  Applied / Interview / Offer / Rejected) and two conversion rates
  (applications → interview-or-better, applications → offer). One
  simplification made deliberately and documented here: the spec lists
  `SavedJob`, `JobApplication`, and `ApplicationNote` as separate models,
  but since section 24's saved-job statuses already are the full
  application funnel and section 25 calls the tracker "lightweight," this
  is built as **one `SavedJob` model with two views** over it rather than
  three overlapping tables — the tracker page is a filtered/aggregated
  read of the same data, not a separate write path.
- **Quick Match** (new `/match/quick/<job_id>` route): lets a user match
  their own resume against *any* completed job in the shared pool, not
  just ones they personally analyzed — a natural extension once job
  search exists. This was added carefully to avoid any regression to
  Phase 6: the original `/match/analyze` flow and its dropdown (scoped to
  only the user's own resumes+jobs) are completely unchanged; this is a
  new, separate endpoint used only from the "Check my fit" button on the
  public browse page. Resume ownership is still strictly enforced (only
  your own resumes ever appear in the dropdown); job ownership is not,
  by design.
- 24 new tests (`tests/test_saved_jobs.py`) plus 1 new CSRF-coverage
  regression test.

## A testing-harness lesson (not an app bug) worth being upfront about

While verifying this phase live, two `curl` commands that combined
`--data-urlencode` with an explicit `-X POST` flag returned `405 Method
Not Allowed` in a couple of multi-step bash scripts, which briefly looked
like a real routing bug. Direct reproduction ruled it out: the exact same
request via Flask's own test client returned `200`, and the exact same
`curl` invocation *without* the redundant `-X POST` (curl already sends
POST automatically once you pass `--data-urlencode`) returned the correct
`302 FOUND`. The routes (`job.save`, `saved_jobs.update`,
`matching.quick_match`) all work correctly — this was a quirk in how that
specific combination of curl flags interacted within a couple of
fragmented, multi-invocation test scripts, not a defect in the
application. Mentioning it here in the interest of being transparent
about the debugging process, not because it affected the shipped code.

## What's new in Phase 7

- **`AIProviderManager`** (`app/services/ai/manager.py`) — the single
  entry point the rest of the app is meant to use for any AI call. Routes
  and services call `manager.generate(...)` / `.generate_json(...)` /
  `.embed(...)` and never import a specific provider directly, so adding
  a 6th provider later never touches a caller
- **Five providers**, each implementing the same interface
  (`app/services/ai/base.py`): Gemini, Groq, OpenRouter, Claude, OpenAI.
  Groq and OpenRouter don't offer embeddings APIs and Claude doesn't
  either — each raises a clear, non-retryable `AIProviderError` for
  `.embed()` rather than silently returning nothing
- **Gemini multi-key rotation** (`app/services/ai/key_rotation.py`): on a
  rate-limit/quota error, the offending key is put in cooldown and the
  next available key is tried automatically — before the manager would
  ever consider falling back to a *different provider* entirely
- **Fallback ordering**: configured default provider first, then
  `AI_PROVIDER_ORDER`, skipping any provider with no API key configured;
  if every provider fails, `NoProviderAvailableError` reports exactly
  which providers were tried and why
- **Response caching** (`app/services/ai/cache.py`), DB-backed, keyed by
  `(provider, model, method, prompt, extra context)` per the spec —
  scoped per-provider-and-model so a fallback to a different provider
  never silently serves a cached answer from another one
- **Usage tracking** (`AIUsage` model): every attempt (success or
  failure) is logged with provider, model, tokens, response time, and
  cache-hit status. Visible at `/admin/ai-status`, which also shows each
  provider's configuration and (for Gemini) live key rotation status —
  **always showing only the last 4 characters of any key, never the full
  secret**, verified by a dedicated test
- 33 new tests across `test_ai_key_rotation.py`, `test_ai_providers.py`,
  `test_ai_manager.py`, and `test_ai_admin_status.py`, plus one
  deliberately real (non-mocked) network test — see below

## An honest note on what could and couldn't be tested here

This sandbox has no configured API keys for any provider, and of the five
provider domains this app talks to, only `api.anthropic.com` is reachable
through this environment's network egress rules —
`generativelanguage.googleapis.com` (Gemini), `api.groq.com`,
`openrouter.ai`, and `api.openai.com` are not. So the testing strategy
for this phase is layered, and each layer proves something different:

1. **Mocked-HTTP tests** (`test_ai_providers.py`, `test_ai_manager.py`) —
   the majority of the suite. These verify request construction and
   response parsing against payloads shaped exactly like each provider's
   real, documented API, and verify the manager's fallback/caching/usage
   logic. They don't touch the network at all.
2. **One genuinely real network test** (`test_ai_live_smoke.py`) — no
   mocking, a real HTTPS call to `api.anthropic.com` with an
   intentionally invalid key. This can't prove a *successful* generation
   works (that needs a real deployment with real credentials), but it
   does prove the request actually reaches Anthropic's live servers and
   that our error-handling code correctly classifies a real 401 response
   — not a hand-crafted mock — as non-retryable.
3. **One further live check done manually** (not a checked-in automated
   test, since it needs a fake key set via environment variable) that
   ran the *entire* pipeline — `AIProviderManager.generate()` → provider
   selection → real HTTP call to Anthropic → error classification →
   fallback exhaustion → `AIUsage` row logged with a real measured
   response time (103ms) — end to end, against the live API. This is the
   strongest evidence available in this environment that the full stack
   is wired together correctly, not just each piece in isolation.

**What is not verified here, and can't be without real credentials:** a
successful generation from any provider, real Gemini key rotation against
Google's actual rate limits, or real responses from Groq/OpenRouter/OpenAI
(their domains aren't reachable from this sandbox at all). The
architecture is provider-agnostic and ready to work the moment real API
keys are supplied — but that final confirmation needs a real deployment.

## What's new in Phase 6

- **Resume ↔ Job matching** (`/match/`): pick one of your resumes and one
  of your analyzed jobs, get a compatibility report with an overall score
  and a five-way breakdown: skills, experience, education, keyword
  coverage, and semantic similarity
- **Semantic similarity uses TF-IDF + cosine similarity** (scikit-learn),
  not a deep embedding model — deliberately, because Phase 7's AI
  provider architecture doesn't exist yet and the spec is explicit that
  NLP tasks should use the cheapest suitable method. The function's
  signature (`semantic_similarity(text_a, text_b) -> float | None`) is
  designed so it can be swapped for real embeddings later without
  touching any caller
- **Every sub-score returns `None` (not 0, not 100) when there isn't
  enough data** — a job with no detected skills, a profile with no years
  of experience set, an education level that isn't on the strict
  comparable ladder (bootcamp/self_taught/other) — and the overall score
  only weighs whichever sub-scores are actually available, renormalizing
  weights among them rather than dragging the total toward zero for
  missing data
- **Skill gap classification**, three tiers:
  - *Critical* — required by the job, missing from your skills
  - *Important* — preferred by the job, missing from your skills
  - *Optional* — not explicitly requested by this job, but frequently
    required alongside its skills **market-wide** (reusing Phase 5's
    co-occurrence data) — genuine "you might also want to learn X"
    suggestions grounded in actual collected data, empty rather than
    guessed when the market dataset is too small
- Re-running a match on the same resume+job pair updates the existing
  report in place (no duplicate history clutter)
- A clear disclaimer on every report: match scores are estimates, not a
  guarantee of employment
- 19 new tests (`tests/test_matching.py`) covering scoring accuracy
  against real parsed fixtures, gap classification correctness, weight
  renormalization, ownership/isolation, and the market co-occurrence
  optional-suggestion feature end-to-end

## A near-miss caught during testing (not a bug, but worth explaining)

A cross-user isolation test initially expected a `403` when one user
tried to match against another user's resume/job IDs, but got `200`
instead. Investigation showed **no actual security gap**: the matching
form's `resume_id`/`job_id` dropdowns are `SelectField`s whose `choices`
are re-derived from the *current* logged-in user on every request before
validation runs — so a forged ID that isn't in that user's own list is
rejected by WTForms itself (redirecting with a flash error) before the
route's own explicit ownership check is ever reached. Confirmed directly
that zero `JobAnalysis` rows were created in that scenario. The test was
updated to assert the actual (secure) outcome — no report created —
rather than a specific HTTP status code, and the route's explicit
`abort(403)` ownership check remains in place as defense-in-depth.

## Quick start

```bash
cd jobmarket-ai
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
cp .env.example .env
python3 app.py
```

Visit `http://127.0.0.1:5000`, register, verify, log in. Set your years
of experience and education level on **My Profile**, upload a resume,
analyze a job, then visit **Match Analysis** to run a compatibility
report — or use the "Match against a job/resume" button right on a
resume's or job's detail page. Then visit **Career Roadmap** to turn
those match reports into a month-by-month skill plan with real learning
resources and project ideas. Visit **AI Assistant** to try the chat
interface — without a configured API key it'll explain that clearly
rather than failing; set `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
`GROQ_API_KEY`, `OPENROUTER_API_KEY`, or `GEMINI_API_KEY_1..4` in `.env`
to get real answers grounded in your actual data.

## Running the tests

```bash
python3 -m pytest tests/ -v
```

256 tests should pass (103 from Phases 1–6, 39 from Phase 7: 6 key
rotation + 18 provider + 10 manager + 4 admin-status + 1 real network
test, 25 from Phase 8: 24 job search/saved jobs/tracker + 1 CSRF
coverage, 14 from Phase 9: 13 assistant + 1 CSRF coverage, 19 from the
roadmap delivery: 18 roadmap/recommendations + 1 CSRF coverage, 20 from
the reports delivery: 19 reports/ATS/improvement + 1 CSRF coverage,
19 from the admin delivery: 18 admin/security + 1 CSRF coverage,
17 from this delivery: advanced insights).

## What was tested (Reports, ATS Analysis & Resume Improvement)

pytest first — including tests that go beyond "did it return 200":
`test_pdf_export_produces_valid_pdf_header` asserts the bytes actually
start with `%PDF-` (not an error page), `test_json_export_contains_real_
resume_data` asserts the export contains the real parsed name, skills,
and experience count, and the two anti-fabrication tests described above.
Then live-server verification: registering, uploading a real PDF resume,
analyzing a gap job, running a match, and downloading all three formats
over real HTTP — then **parsing the downloaded PDF back with `pypdf` to
confirm it's a genuinely valid one-page document containing the real
extracted name and skills**, rather than trusting a byte count. ATS
disclaimer and real missing skills (Terraform, Rust) confirmed rendered
on the live page. All reverified on a from-scratch clone.

## What was tested (Career Roadmap & Recommendations)

Same discipline as every phase: pytest first — including a test that
specifically parses every generated recommendation's technology list and
asserts it's a subset of the real skill gaps found in that test's match
report, to catch any drift toward inventing plausible-sounding but
unfounded suggestions — then live-server verification: registering,
uploading a real resume, analyzing a job specifically chosen because the
resume doesn't have those skills (`sample_job_gap.txt`, reused from
Phase 6), running a match, and generating a roadmap via a real form
click. Confirmed live: the roadmap correctly shows the real missing
skills (Rust, Terraform) in priority order; a curated learning-resource
link renders for skills that have one; project recommendations generate
successfully with real click submissions; a skill's status updates to
"completed" via its own form's embedded token; and an admin can add a
new learning resource through the admin panel. All of this reverified on
a from-scratch clone.

## What was tested (Phase 9 — AI career assistant)

Same layered approach established in Phase 7, since this phase is the
first to actually exercise that architecture end-to-end: mocked-HTTP
tests for the majority of coverage (grounding correctness, conversation
history, ownership, graceful degradation), then real verification against
the live server. Specifically confirmed live: the assistant page honestly
reports "no AI provider configured" (the default state of this sandbox);
starting a conversation anyway still works and stores that explanation
rather than crashing, verified via a real click using the token embedded
in that exact form (not scraped from elsewhere — the Phase 4 lesson);
and, going one step further than Phase 7 did, **the entire assistant
pipeline was run against the real Anthropic API with a fake key** —
`start_conversation()` → context builder → `AIProviderManager` → real
HTTPS call to `api.anthropic.com` → a real 401 → correctly classified as
a *configured provider failing* (a distinct message from *no provider
configured at all*) → logged with a genuine measured response time
(142ms) → the correct generic failure message stored. Separately, a
mocked successful response was confirmed to flow all the way through
from a real profile's grounded data to the stored, displayed reply. All
of this reverified on a from-scratch clone.

## What was tested (Phase 8 — job search, saved jobs, tracker)

Same discipline as every phase: pytest first (167/167 passing, including
tests that specifically probe the ownership boundary between the new
public `browse_detail` view and the original private `/jobs/<id>` view),
then live-server verification with real HTTP requests — registering,
analyzing a job, searching for it, saving it via the token embedded in
that exact button's own HTML (not one scraped from elsewhere, per the
Phase 4 lesson), updating its status to "Applied" with real form
submission, confirming the tracker reflects it, and — importantly —
verifying with a second real user that saved-job notes stay private
while the underlying job content is visible to both. Also verified the
quick-match cross-feature integration end-to-end: a second user uploads
their own resume and successfully matches it against the first user's
analyzed job, with the resulting report correctly owned by the second
user. All of this reverified on a from-scratch clone of the delivered
code.

## What was tested (Phase 6 — matching)

Same discipline as every previous phase: pytest first (including direct
unit tests of each scoring function's edge cases — partial credit,
missing data, ordinal education comparison), then a live server hit with
real HTTP requests: profile setup → real PDF resume upload → real job
analysis → a match run through the actual form (not calling the engine
directly) → confirmed the rendered score, disclaimer, and skill gap
lists match what the direct-engine test produced. Also verified live:
deleting a match report via the token embedded in that exact button's
HTML (carrying forward the Phase 4 CSRF lesson), and that a second
user's market dashboard still reflects the first user's analyzed job
(aggregate data is shared) while that user cannot view the actual match
report (403, confirmed in the pytest suite). All of this reverified on a
from-scratch clone, including the skill-gap scenario fixture
(`sample_job_gap.txt`) to confirm Critical gaps render correctly, not
just the "everything matches" happy path.

## Notes for the next phase (Phase 6, still relevant)

- `app/services/matching/semantic.py`'s `semantic_similarity()` and
  `app/services/matching/keyword_coverage.py`'s `keyword_coverage()` both
  have simple, stable `(text, text) -> float | None` signatures.
  **Phase 7's `AIProviderManager.embed()` is now available** and could
  back an LLM-embedding-based alternative behind the same signature —
  still not wired in yet (matching still uses TF-IDF), since that's a
  deliberate choice for a later phase to make with real provider
  credentials in hand, not something to switch silently.
- `DEFAULT_OVERALL_WEIGHTS` in `scoring.py` (skills 40%, semantic 20%,
  keyword 15%, experience 15%, education 10%) is a reasonable starting
  point, not empirically tuned — if Phase 45's report generator or user
  feedback suggests a different balance matters, it's one dict to adjust,
  and `overall_score()`'s renormalization logic doesn't need to change.
- `JobAnalysis` is unique per `(resume_id, job_id)` by design (re-analysis
  updates in place). If a future phase wants to show *trend* in match
  score over time (e.g., after a user adds new skills), that needs a
  separate history table — don't repurpose this one into multi-row
  history, since routes/templates assume one report per pair.
- The "optional" skill gap suggestions depend entirely on Phase 5's
  market co-occurrence data existing in meaningful volume — they'll be
  empty (correctly, not a bug) until enough jobs have been analyzed
  system-wide. Worth mentioning to early users so an empty "optional"
  section doesn't read as broken.

## Notes for the next phase (from Phase 7, still relevant)

- To actually exercise a provider, set at least one of
  `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GROQ_API_KEY`,
  `OPENROUTER_API_KEY`, or `GEMINI_API_KEY_1..4` in `.env`, then check
  `/admin/ai-status` as an admin to confirm it's picked up before
  building on top of it.
- `manager.generate_json()` raises a plain `ValueError` (not
  `AIProviderError`) if the model's response isn't valid JSON after
  stripping code fences — deliberately, so a malformed-JSON response
  doesn't trigger a fallback to a *different* provider (which won't fix
  a prompt/formatting issue) but is instead surfaced to the caller to
  handle. Phase 46 (resume improvement) and similar structured-output
  features should keep that distinction in mind.
- `AICacheEntry` has no admin UI to inspect/clear it yet — if cached
  responses ever need manual invalidation (e.g. after a prompt template
  changes), that's a small addition to `/admin/ai-status`, not a new
  subsystem.
- `SavedJob.status` values (`saved/applied/interview/offer/rejected`) are
  used both for the management list and the tracker's funnel — if a
  future phase needs richer per-application history (e.g. multiple
  interview rounds with separate dates), that's a genuine new
  `ApplicationNote`-style table, not a field to bolt onto `SavedJob`.
- The "quick match" pattern (public job, private resume, ownership
  enforced only on the private side) is a template worth reusing if a
  future phase adds more actions from the search/browse pages.

## Notes for the next phase (from Phase 9, still relevant)

- **`context_builder.py`'s structured-summary approach is intentionally
  the ceiling of what this phase does, not a permanent architectural
  choice.** If a future phase needs the assistant to search across a
  much larger shared corpus (e.g. "find me jobs like the one I'm
  looking at" across thousands of market postings, not just this user's
  handful), that's exactly the point where real vector-embedding
  retrieval (via `manager.embed()`, already built in Phase 7) becomes
  the right tool — don't extend the structured-summary approach to try
  to cover that case too.
- `AIMessage` ordering bug (see above) is a good reminder for any new
  model that both (a) defines a relationship with `order_by=` for normal
  display and (b) sometimes needs a *different* order for a specific
  query: go through `Model.query.filter_by(...)`, not
  `parent.relationship_attr.order_by(...)`.
- The assistant currently has no rate limiting of its own beyond the
  app-wide Flask-Limiter setup — if AI provider costs become a concern,
  consider a per-user daily question cap, surfaced honestly in the UI
  rather than silently throttled.
- `conversation.title` is just the first question, truncated to 150
  chars — if conversations need better titles later (e.g.
  LLM-summarized), that's a `generate()` call in `start_conversation()`,
  not a new model field.

## Notes for the next phase (from this delivery)

- **`gather_gap_skills()` in `app/services/roadmap/gap_aggregator.py` is
  now the shared source of truth for "what does this user actually need
  to learn"** — both the roadmap and project recommendations call it.
  Any future feature needing the same data (e.g. a "what's missing"
  widget on the dashboard) should call this function too, not
  re-aggregate `SkillGap` rows independently.
- **`CURATED_DOCUMENTATION` in `learning_resource_seed.py` is a
  best-effort, manually-maintained list of real URLs** — it is not
  live-checked against the actual sites. If a next phase adds automated
  reporting/health-checking of external links (a legitimate ATS/reports
  feature), this table is the natural first thing to validate
  periodically, since a documentation site restructuring could make an
  entry stale over time.
- **Project recommendations are deliberately deterministic, not
  AI-generated**, even though Phase 7/9's infrastructure could support
  an AI-enhanced version. If a future phase adds that, follow the exact
  graceful-degradation pattern from Phase 9 (distinct message for "no
  provider configured" vs. "provider call failed") and keep this
  deterministic version as the always-available fallback — don't remove
  it in favor of an AI-only version that could fail with zero
  configuration.
- `CareerRoadmap` is one-per-user, consistent with `JobAnalysis`
  being one-per-(resume,job)-pair — if a future phase wants roadmap
  *history* (e.g. "show me how my roadmap changed over the last 6
  months"), that needs a separate history table, not a change to this
  one's cardinality.

## Project structure

```
jobmarket-ai/
  app.py                       # entry point
  config.py                     # environment-based config
  requirements.txt
  .env.example
  app/
    __init__.py                 # app factory, CLI commands, auto-seed, 413 handler
    extensions.py                 # db, login_manager, csrf, limiter
    forms.py                      # WTForms with validation
    models/
      user.py                     # User, EmailVerificationToken, PasswordResetToken
      skill.py                     # SkillCategory, Skill, SkillAlias
      profile.py                   # UserProfile, UserSkill, UserCertification
      resume.py                     # Resume, ResumeSection, ResumeExperience,
                                       ResumeEducation, ResumeSkill
      job.py                         # Job, JobSection, JobSkill
      matching.py                     # JobAnalysis, SkillGap
      ai.py                            # AIUsage, AICacheEntry
      saved_job.py                      # SavedJob
      assistant.py                       # AIConversation, AIMessage
      roadmap.py                          # CareerRoadmap, RoadmapSkill,
                                             LearningResource, Recommendation
    routes/
      auth.py                      # all auth endpoints
      profile.py                    # profile, skills, certifications
      admin.py                       # taxonomy admin + data import + AI status
      api.py                          # skill autocomplete
      resume.py                        # upload, detail, download, delete, primary
      job.py                             # analyze, detail, delete, reprocess,
                                            search, browse_detail, save
      market.py                           # dashboard, skill explorer, role explorer
      matching.py                          # select resume+job, view/delete report,
                                              quick_match
      saved_jobs.py                         # saved jobs list, tracker, update, delete
      assistant.py                           # conversation list, chat, ask, delete
      roadmap.py                              # roadmap, skill status, recommendations
      dashboard.py                          # protected user dashboard
      main.py                                # landing page
    services/
      auth/decorators.py                # verified_required, admin_required
      email/mailer.py                    # SMTP + dev console/file fallback
      nlp/
        section_scanner.py                # shared header-based section splitter
      skills/
        normalizer.py                     # normalize/find/suggest skills
        seed_data.py                       # taxonomy seed content
        seed.py                             # idempotent seed loader
      resume/                            # (Phase 3)
      job/                               # (Phase 4, + search.py from Phase 8)
      market/                            # (Phase 5)
      matching/
        semantic.py                        # TF-IDF cosine similarity
        keyword_coverage.py                 # ATS-style keyword overlap
        scoring.py                           # sub-score + weighted overall calculations
        skill_gap.py                          # critical/important/optional classification
        engine.py                              # orchestrator + persistence
      ai/
        base.py                                # AIProvider interface, AIResponse, AIProviderError
        key_rotation.py                          # multi-key rotation with cooldown (Gemini)
        json_utils.py                             # shared JSON-from-text parsing
        manager.py                                 # AIProviderManager: fallback, cache, usage
        cache.py                                    # DB-backed response cache
        usage.py                                     # usage logging + aggregate stats
        providers/
          base classes + gemini.py, groq.py, openrouter.py,
          claude.py, openai.py, openai_compatible.py (shared base)
      assistant/
        context_builder.py                         # structured-summary grounding (Phase 9's RAG)
        chat.py                                      # orchestrator: context + manager + persistence
      roadmap/
        gap_aggregator.py                              # dedupes/prioritizes gaps across all match reports
        roadmap_generator.py                            # deterministic month-by-month pacing
        learning_resource_seed.py                        # curated real documentation URLs
        learning_resources.py                             # lookup + idempotent seeding
        project_recommender.py                             # deterministic project idea templates
    templates/                    # Jinja2 templates (Bootstrap 5)
    static/                        # CSS + JS (theme toggle, autocomplete, etc.)
  tests/
    fixtures/                     # sample_resume.{txt,docx,pdf}, sample_job.txt,
                                     sample_job_gap.txt
    helpers.py                    # shared register/login/verify helpers
    test_auth.py                   # 15 tests — full auth lifecycle
    test_profile.py                 # 15 tests — profile, taxonomy, admin
    test_resume.py                   # 16 tests — upload, parsing, isolation, reprocess
    test_job.py                       # 14 tests — analyze, parsing, isolation
    test_market.py                     # 19 tests — analytics, import, thresholds
    test_matching.py                    # 19 tests — scoring, gaps, isolation
    test_csrf_coverage.py                # 7 tests — CSRF regression coverage
    test_ai_key_rotation.py               # 6 tests — key rotator (no network)
    test_ai_providers.py                   # 18 tests — mocked-HTTP, all 5 providers
    test_ai_manager.py                      # 10 tests — fallback, caching, usage logging
    test_ai_admin_status.py                  # 4 tests — admin AI status page, key masking
    test_ai_live_smoke.py                     # 1 test — REAL network call to api.anthropic.com
    test_saved_jobs.py                         # 24 tests — search, save, tracker, quick match
    test_assistant.py                           # 13 tests — grounding, degradation, isolation
    test_roadmap.py                              # 18 tests — roadmap, resources, recommendations
