## What I built

Sweep is a parameter exploration tool for image generation models. It's a clone of Replicate's per-model playground - that auto-generated form-on-a-page you get at `replicate.com/[model]` - improved in two specific ways.

**First, sweep mode.** Any input in the form can be toggled from a single value to a range of values. Submitting fires those variations in parallel and streams the results into a labeled comparison grid. Numeric sweeps (guidance, seed, steps) get a comma-separated input. Enum sweeps (aspect ratios, output formats) get a checkbox group. Hit Run and watch the grid populate as each generation completes.

**Second, prompt-as-axis sweep.** The prompt is treated as a sweepable input too. Toggle it to Sweep, pick a stylistic direction from a dropdown - camera angle, lighting, art style, mood, composition, time of day, weather, color palette - and Claude Sonnet 4.6 generates N variations of your prompt along that axis. The variations appear as editable textareas you can tweak before hitting Run. The grid then renders the same scene rendered along the chosen creative dimension.

**Third, two-axis sweeps.** Sweep two parameters simultaneously to produce a rows x columns ablation grid. Toggle sweep on `cfg` (columns) and `seed` (rows) and the grid renders every combination. The first axis toggled becomes columns, the second becomes rows. Combined with the `num_outputs` multiplier — which repeats each cell N times for random-seed variation — this enables serious parameter exploration.

**Fourth, per-cell captions and download.** Every completed cell shows the full prompt, all input parameters, generation time, and a download button that actually downloads the image file (proxied through the server to work cross-origin).

The product supports 6 image models from 5 different vendors. Each model's form is generated dynamically from its OpenAPI schema - adding a 7th model is one line in config, making the codebase very scalable.

The codebase has been built keeping in mind decisions like: modularity, scalability, understandability, tests, and debugging. 

**Live URL:** https://sweep-playground.fly.dev/

## Why this for Luma specifically

The take-home gave me three problem types. I picked clone-and-improve because it forces sharpness - you can't ship a generic "AI tool"; you have to point at something specific and explain what you'd do differently.

I picked Replicate's playground as the clone target because it's a tool I'd actually want to extend. Replicate's form-from-schema pattern is elegant. The thing it doesn't do is let you *compare* - every interaction is one prompt, one output. But the actual workflow of working with generative models is "what happens if I bump guidance by 1, or change the seed, or rephrase the prompt slightly." That workflow today means filling in the form, running it, screenshotting, refilling, running again, screenshotting, manually tracking which inputs produced which outputs. That's friction Sweep eliminates.

The prompt-as-axis sweep is the part I'm most happy with. It started as "prompts should be sweepable too, why not." The deeper observation: when an artist uses an image model, the prompt isn't a fixed input - it's the *primary* dimension of exploration. Most users iterate the prompt 10x for every numeric parameter they touch. Treating the prompt as an axis (with semantic structure: "vary this along the lighting dimension") respects how the tool is actually used.

This kind of tool is genuinely useful for Luma. Their researchers run parameter ablations constantly when evaluating model checkpoints. Their users prompt video models the same way I prompt image models - by varying language, not knobs. The same primitive applied to video would be the natural extension, which I touch on in "what I'd build next."

## Stack choices

I'm being explicit about each choice because every reviewer will ask "why this, not that," and the answers matter as much as the choices.

**FastAPI + Jinja2 + HTMX + Tailwind (CDN) + plain JS, no build step.**

FastAPI + HTMX produces a server-rendered web app with no build pipeline, no client-side state machine. It is simple to debug, navigate and good for MVP without complicating things. As the next step, a better approach would be to use React and NextJs.

HTMX specifically is the right fit because Sweep is fundamentally server-driven grid mutations: click a button, server does something, HTML fragment swaps into the page. That's HTMX's exact sweet spot. React would also have been a state-sync problem on top of the actual work.

**SQLite via stdlib sqlite3, no ORM.**

SQLite because Sweep has one user, write throughput is single-digit rows per second, reads are point lookups by ID. It's the smallest database that fits the workload. It's in Python's standard library so adds zero dependencies. The whole database is one file at `data/sweep.db`. Reviewer clones the repo, runs `docker build && docker run`, the database is just there.

No ORM because every query in this codebase is a point lookup or a `WHERE sweep_run_id = ?`. SQLAlchemy would be 500K lines of abstraction over queries I'd write the same way by hand. It would also make the live interview harder - "what query runs when you fetch a cell?" is a question I want to answer by pointing at the line, not by explaining session.query semantics.

**I'd switch to Postgres the moment this becomes multi-user**, because then concurrent writers are real and connection pooling matters. For one user, SQLite works fine for an MVP.

**Replicate API for image generation, Anthropic API for prompt expansion.**

Two LLM providers, two different jobs. Replicate hosts the image models (we're cloning Replicate's playground, so it's the natural choice - and lets the project show breadth across 5 vendors). Claude Sonnet 4.6 handles prompt expansion because that task is structured-output text reasoning, something which it is good at, and also keeps our architecture from using the same family of models for different variety of tasks, showing diversity. Using OpenAI image gen would have been simpler but would have meant defending a single-vendor choice.

The Anthropic call uses prompt caching on the system prompt (`cache_control: ephemeral`). The expansion system prompt is roughly 1200 tokens; with caching it costs ~$0.005 per Preview click instead of $0.05. This can save costs when iterating on the system prompt.

**asyncio for concurrency, no job queue.**

Fire-and-forget with `asyncio.create_task` bounded by `asyncio.Semaphore(6)`. The HTTP request for `POST /sweep` returns within ~100ms with the grid skeleton; generations complete in the background; each cell polls `/cell/{id}` every 2 seconds reading status from SQLite. No Redis, no Celery, no RQ.

This makes sense for the slice because every task is independent, failures are isolated to individual cells, and we don't need cross-process orchestration. Adding a job queue would have meant infrastructure complexity for zero behavioral benefit. The semaphore enforces the only thing that matters: don't exceed 6 concurrent Replicate calls.

**Fly.io for deploy, with a 1GB persistent volume for `data/`.**

Fly because the deploy story is one Dockerfile and one command. The volume specifically because without it, an in-flight sweep loses its cells if I deploy a fix mid-demo. Cost: ~$0 at this scale. Benefit: zero ops surface for the demo.

## Key architectural decisions

**Schema introspection over hardcoded forms.**

The supported model list is 6 strings in `config.py`. Forms aren't hardcoded - when the user picks a model, the server fetches that model's OpenAPI schema from Replicate (cached in SQLite for 24 hours), parses it into a list of typed `ModelInput` objects, and renders the form from those. The parser handles type mapping (string/integer/number/boolean), $ref-style enum resolution (used by Imagen, Seedream, Recraft), inline enums (used by Flux), `format: "uri"` detection for non-sweepable image inputs, and `x-order` sorting for display order.

Adding a 7th model: one line added to `SUPPORTED_MODEL_SLUGS`. The form renders correctly the first time it's selected.

This is the central technical decision in the project. Without it, supporting 6 models would have meant 6 hand-coded forms and 6 places to update when something changed.

**Fire-and-forget orchestration with DB-mediated polling.**

Instead of awaiting all generations before returning the grid which would have made the HTTP request block for 30-60 seconds, defeated the streaming demo, and risked timeouts, our current `POST /sweep` does three things synchronously - insert one `sweep_runs` row, insert N `generations` rows with status="pending", fire N `asyncio.create_task` calls - then immediately returns the grid skeleton. The HTTP response is fast (~100ms). The background tasks acquire the semaphore, update their row to "running," call Replicate, update to "complete" or "failed." Each cell on the client polls `/cell/{id}` every 2 seconds, reading the live status from SQLite. The polling endpoint returns one of two templates: `cell_polling.html` (still has the polling triggers) or `cell_final.html` (zero HTMX attributes). When status flips to complete or failed, the next poll returns the final template, which replaces the polling cell, and polling auto-stops because there are no triggers in the new HTML.

Also, what is interesting is that polling auto-stops as a consequence of the template difference, not via an explicit "stop polling" message. The state of the cell is the state of the row is the template returned. One source of truth.

**Form-data naming convention as the sweep marker.**

Every form field has its name prefixed: `input__prompt` for fixed inputs, `sweep__prompt` for swept inputs. The toggle JS swaps the prefix when the user activates sweep mode (and disables the inactive control so it doesn't submit). The sweep route looks for exactly one `sweep__*` key to identify the axis. If there are zero, it's a single generation. If there are multiple, the first wins (with a constraint enforced client-side via the one-axis-at-a-time toggle JS).

This is a small thing but it means the sweep route is straightforward dict parsing instead of a parser-with-state-machine. The naming convention does the work.

**Prompt expansion as a separate HTMX swap, not a JSON fetch.**

The Preview button hits `POST /prompt-expand` via HTMX, with `hx-target` pointing at the variations container and `hx-swap="innerHTML"`. The server calls Claude, parses the response, renders a template of N `<textarea name="sweep__prompt">` elements, returns it. HTMX swaps them in. The user edits any textarea inline; clicking Run submits all of them as a multi-value sweep through the existing flow.

Claude Code's first plan for this used `fetch()` and client-side DOM construction. I pushed back: HTMX everywhere keeps the codebase pattern uniform, keeps JS minimal, and makes the prompt-expansion endpoint render HTML instead of JSON (which means it composes with the rest of the templating).

**Two-axis sweeps as cartesian product.**

The route parses up to 2 `sweep__*` keys from the form. With one axis, it's a flat grid (existing behavior). With two, it computes the cartesian product: every combination of axis 1 values x axis 2 values. The grid renders as an HTML table with column headers (first axis) and row headers (second axis). The JS tracks activation order via `data-sweep-order` — first toggled = columns, second = rows. Toggling a third axis replaces the oldest. This keeps the UX predictable: you build up from one axis to two, and the grid structure follows your intent.

**num_outputs as a multiplier, not a Replicate parameter.**

`num_outputs` controls how many times each cell configuration is repeated, not how many images Replicate generates per call. Setting `num_outputs=3` with a 2-value sweep produces 6 cells (3 repetitions x 2 values), each making an independent API call with `num_outputs=1`. This avoids waste (Replicate generating N images but only displaying 1) and gives the user random-seed variation across repetitions. `num_outputs` and `max_images` are excluded from the sweep toggle — they're batch controls, not creative parameters.

**Download proxy for cross-origin images.**

Replicate hosts images on `replicate.delivery`. The HTML `download` attribute on `<a>` tags only works for same-origin URLs — cross-origin downloads silently open a new tab instead. The fix: `GET /download/{gen_id}` streams the image through our server with `Content-Disposition: attachment`, making the browser trigger a real file download. The view-in-new-tab link still goes directly to Replicate for speed.

**Aspect ratio sweeps as CSS reframing, not regeneration.**

When `aspect_ratio` is the swept axis, the system makes one API call instead of N. The image is generated once, and each grid cell displays the same image with a different CSS `aspect-ratio` + `object-fit: cover` — the browser handles the cropping. This is the correct behavior: aspect ratio is a framing decision, not a content decision. Sweeping 5 aspect ratios costs one generation instead of five. The implementation uses `run_shared_generation()` in the sweep engine, which runs one Replicate call and copies the output URL to all generation rows.

**Three-layer input validation.**

Prompt is required for every model. Validation enforces this at three levels: (1) HTML `required` attribute on the prompt textarea blocks empty submissions in fixed mode. (2) Client-side JS intercepts the HTMX request before it fires — checks for prompt in fixed mode or expanded variations in sweep mode, and shows an inline error banner if missing. This also catches the case where sweep is toggled on prompt but the user clicks Run without clicking Expand first. (3) Server-side route validation confirms prompt exists in `fixed_inputs` or as a sweep axis before creating any generation rows.

## How I directed the AI tools

The prompt direction in this codebase wasn't ambient - every major architectural choice was a specific pushback I made to Claude Code, and the session logs show them. The ones worth highlighting:

- **Phase 2 architecture.** Claude Code's first plan put `run_generation` (semaphore acquisition, status transitions, Replicate call) inside `services/replicate_client.py`. I pushed back: that's orchestration, not transport. Replicate client should be two thin async functions (`fetch_schema`, `run_model`). The orchestration belongs in `services/sweep_engine.py` in Phase 4. Clean separation: transport doesn't know about SQLite or semaphores.

- **Phase 3 form-field naming.** First plan rendered form fields with bare names (`prompt`, `seed`, etc.). I pushed back: needs the `input__` prefix from day one so Phase 4's sweep handler can distinguish fixed from swept inputs by prefix without refactoring every input field later.

- **Phase 3 boolean rendering.** First plan rendered booleans as `<input type="checkbox">`. I pushed back: should be `<select>` with true/false options. Reasoning: checkboxes break the sweep UI symmetry (a checkbox can't represent "sweep this with values [true, false]" the way a select can). Uniform select pattern means the sweep toggle works the same way for all input types.

- **Phase 4 grid layout.** First plan used `1/2/3 columns based on N`. I pushed back: produces orphan cells (N=3 in 2 cols leaves one cell on a row alone). Should be tuned for clean rows - N=3,5,6,7,8,9 all use 3 cols, N=2 or 4 uses 2 cols, N=1 uses 1 col.

- **Phase 4 cap enforcement.** First plan didn't actually enforce `MAX_SWEEP_SIZE=9` anywhere. Without it, a user could enter 50 values and run 50 generations. Pushed back: truncate the parsed sweep values to MAX_SWEEP_SIZE in the route before creating generation rows.

- **Phase 5 fetch vs HTMX.** First plan used `fetch()` for the prompt expansion endpoint with client-side textarea construction. I pushed back: HTMX is the consistent pattern, can target the variations container directly, eliminates ~30 lines of JS. The endpoint should render HTML, not JSON.

- **Phase 5 label truncation logic.** First plan special-cased prompt labels for truncation ("if sweep_name == prompt then truncate"). Pushed back: just truncate every label to a max length. Long values are bad labels regardless of input type. Universal rule beats type-specific exception.

- **Phase 6 SQLite persistence.** First plan accepted that SQLite resets on deploy. I pushed back: add a Fly volume so in-flight sweeps survive a deploy. Five minutes of work to eliminate a real edge case.

- **The prompt-expansion system prompt itself.** This is the single most important piece of text in the codebase. I iterated it 4 times against a 9-case test matrix (3 base prompts × 3 axes). First version: too generic, variations drifted from the subject. Second version: added explicit subject-preservation rules and per-axis reference ranges (cinematography terms for "camera angle," lighting setups for "lighting," art mediums for "art style"). Third: added a worked example with a real base prompt and 4 high-quality variations to anchor the model's pattern. Fourth: hardened the JSON output instruction ("Your entire response must be parseable by json.loads()"). Final prompt is ~60 lines; subject preservation is reliable; variations are visibly distinct across the matrix.

The pattern across all of these: Claude Code's plans were never wrong, exactly - they were just close-but-not-right on architectural details that mattered. Most of these pushbacks took two or three sentences. The cumulative effect is a codebase where I made every important decision.

## Design 
Initially started with a very basic design, after integrating all the features, used Claude Code Design to upgrade the design - saw some ideas that looked elegant and tasteful, asked Claude to write a prompt to recreate that UX and used it in Claude code and refined it. It is present in the codebase as replicate-sweep.zip

## What I intentionally left out

Cuts I made deliberately:

- **AI-as-judge ranking of grid results.** After a sweep completes, score and rank cells by a user-supplied criterion ("most cinematic," "best prompt adherence") via a Claude vision call. I scoped this out because it's a strong feature but separable - it's a single new endpoint that composes with the existing grid. Roughly 90 minutes.

- **Causal-diff explanation between two cells.** Click two cells, get Claude's explanation of what about the parameter difference caused the visual difference. Pairs well with the AI judge. Another ~90 minutes.

- **Cross-model sweeps.** Same prompt across N models in one grid. Real value for "which model should I use for this kind of work," but spreads the product across two different axes of comparison (parameters vs models). Cleaner to ship one direction first.

- **History view / past sweeps gallery.** Single-session by design. SQLite persists everything but there's no UI to navigate past sweeps. Adding it is a sidebar plus a few routes.

- **Authentication, accounts, sharing.** Single-user product. Adding accounts is a Postgres-and-auth path that's correct for production but out of scope for a slice.

- **Inpainting / region-select editing.** Different interaction model entirely. Not a sweep feature.

- **Streaming generation progress.** Replicate's API isn't streaming-friendly for image gen - you wait for the full image either way. Cell polling is the right pattern; streaming partial progress would be theater.

- **Cost ceilings per session.** The 9-cell cap is a soft ceiling. A real product would have configurable spend limits.

These cuts are real, not aspirational. Each one was a deliberate scope decision in service of shipping a tight, polished slice in 8 hours rather than 4 features at 60%.

## What breaks first under pressure

Honest about the failure modes:

- **Schema parser breaks on novel input shapes.** I tested against 6 specific models. A model with deeply nested allOf/oneOf, polymorphic inputs, or array-of-objects inputs would crash the parser. Mitigation today: hand-pick supported models. Real fix: defensive parsing with per-input try/except, logging unsupported shapes and skipping rather than crashing.

- **Replicate rate limits at sweep size 9.** Each user runs at most 6 concurrent generations; one user is fine. Multiple concurrent users on the same Fly machine sharing a Replicate token would hit 429s. Mitigation: per-user rate limiting and a queue.

- **SQLite write contention under multi-user load.** Single-writer model is fine for one user. With concurrent writers from multiple sessions you'd see "database is locked" errors. WAL mode is already enabled, which helps; Postgres would solve it at real scale.

- **Long-running generations and HTTP timeouts.** Fly's default request timeout is 60 seconds. A slow Replicate response (cold model, large image) approaching that limit would fail the polling request, not the generation. The cell would show as stuck in "running" because the next poll might fail intermittently. Mitigation: increase Fly timeout, or move to SSE/WebSockets for cell updates at scale.

- **The Claude prompt-expansion under unusual axes.** "Camera angle" and "lighting" produce great variations because they're in the system prompt's reference table. A custom axis like "wardrobe formality" produces variations that are good but less reliable. Iteration on the prompt or per-axis few-shot examples would tighten this.

- **The Replicate FileOutput return type changes.** The SDK's `run()` method has returned different shapes (string, list of strings, FileOutput with `.url`) across versions. I handle three known shapes defensively. A future SDK version returning something else would break Phase 2's parser.

- **Schema cache staleness.** 24-hour TTL on schemas. If Replicate ships a model schema change in that window, the form renders with stale fields until the cache invalidates. Mitigation: lower the TTL, or invalidate on parse failure.

## What I'd build next

In rough order of leverage:

1. **AI-as-judge ranking + causal diff.** After a sweep, score the grid by a user-criterion and explain inter-cell differences. Turns Sweep from "generate variations" into "generate, evaluate, and understand variations" - a complete exploration loop.

2. **Cross-model sweeps.** Same prompt across N models in one grid. The right tool for "which model fits this kind of work."

3. **Sweep over video model parameters.** This is the actual pitch to Luma. Same primitive - pick a model, mark inputs as swept, run in parallel, compare - applied to video generation. Cell renders a short clip thumbnail with hover-to-play. Internally useful for evaluating Ray-3.14 against checkpoints; externally useful as the missing tool for video prompt engineering.

4. **Saved sweep templates with shareable URLs.** "Run my noir-lighting prompt sweep against this prompt" as a one-click action.

5. **Per-cell rating and export.** Mark cells thumbs-up/down, export the rated grid as an eval dataset. Closes the loop between "generate" and "fine-tune."

6. **Real persistence with accounts.** Postgres + simple auth, multi-user product surface.

7. A tree which versions all these changes, is visually available to the user, to click on any node/edge, and perform different kinds of sweeps. This would be the absoulte ultimate way to give a user the freedom to experiment.

## Scope summary

- **Phase 1 (foundation)**: FastAPI + SQLite + Pydantic types.
- **Phase 2 (Replicate integration)**:Async SDK wrappers + smoke test verifying all 6 models.
- **Phase 3 (schema introspection + dynamic forms)**: The trickiest piece architecturally; reused by every subsequent phase.
- **Phase 4 (sweep engine + UI):** Numeric/enum sweeps fully working end-to-end.
- **Phase 5 (prompt sweep):** 4 iterations on the system prompt.
- **Phase 6 (polish + deploy):** Cost preview, loading states, display names, error styling, Fly.io with persistent volume.
- **APPROACH.md + video:** Documentation and demo recording.


