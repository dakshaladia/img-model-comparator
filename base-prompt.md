I'm building Sweep — a take-home project for an engineering role at Luma 
(multimodal AI lab, makers of the Ray-3.14 video model). 8-hour budget. The 
take-home asks me to clone-and-improve an existing product. My next round 
after this is a live coding interview, so I need to own every line of code 
in this codebase.

WHAT I'M CLONING
Replicate's per-model playground at replicate.com/[model] — the auto-generated 
form-on-a-page where you fill in a model's inputs and hit Run to get one output.

WHAT I'M IMPROVING
Sweep mode. Mark any input as "swept," provide a list of values, run them all 
in parallel into a labeled comparison grid. Plus the prompt itself is sweepable: 
pick a direction like "camera angle" or "lighting" and Claude generates N stylistic variations rendered as a grid.

STACK (locked — don't suggest alternatives)
- FastAPI + Jinja2 + HTMX 2 (CDN) + Tailwind (CDN)
- SQLite via stdlib sqlite3 (NOT SQLAlchemy)
- replicate Python SDK for generations
- anthropic Python SDK (claude-sonnet-4-6) for prompt expansion only
- asyncio.gather + Semaphore for parallelism
- Deploy: Fly.io via Dockerfile
- No React, no Next.js, no build step

SUPPORTED IMAGE MODELS (locked — these exact 6, in this order)
The image generation backend uses these 6 hand-picked models from Replicate:

1. "black-forest-labs/flux-schnell"
   - Role: cheap/fast dev workhorse, ~$0.003/image
   - Use during all my development testing

2. "black-forest-labs/flux-1.1-pro"
   - Role: higher quality, ~$0.04/image
   - Use for the recorded demo video

3. "google/imagen-4-fast"
   - Role: different vendor (Google), proves cross-vendor schema parsing

4. "bytedance/seedream-4"
   - Role: different aesthetic, different vendor (ByteDance)
   - If this model's schema breaks parsing, swap for 
     "black-forest-labs/flux-1.1-pro-ultra" and tell me

5. "recraft-ai/recraft-v3"
   - Role: illustration-focused, used in demo for art-style prompt sweep

6. "stability-ai/stable-diffusion-3.5-large"
   - Role: classical diffusion params (width, height, guidance, steps, seed)
   - Best model for demoing numeric sweeps

LLM USED FOR PROMPT EXPANSION (separate from image gen)
Claude Sonnet 4.6 (claude-sonnet-4-6) via the Anthropic Python SDK.
This is used ONLY in the prompt-sweep feature: expand a base prompt into N 
stylistic variations along a named axis. Not used for anything else.

WHY THESE SIX MODELS (so you don't suggest alternatives)
- Span 5 different vendors → proves schema introspection generalizes
- Span price range from $0.003 to $0.065 per image
- Span aesthetic styles (photorealism, illustration, classical diffusion)
- Span parameter shapes (aspect_ratio vs width/height, guidance vs guidance_scale)
- These get encoded in config.py as SUPPORTED_MODELS_SLUGS later

Do NOT propose adding more models, removing any, or swapping for video models 
unless I ask. The list is closed for this slice.

The user's choice of model is part of the form — they pick from a dropdown 
of these 6 at runtime. There is no "default model" — the dropdown 
auto-loads the first one on page load via hx-trigger="change, load".

CONSTRAINTS YOU MUST ENFORCE
- No ORM. Raw sqlite3 only.
- No frontend framework beyond HTMX + small vanilla JS.
- All API keys server-side.
- Build data model and storage first, then routes, then templates.
- Get the happy path working before adding error handling.
- One axis per sweep for this slice — no 2-axis grids yet.
- Cap sweep size at 9 and parallel concurrency at 6.
- Push back if I ask for something out of scope.

PHASED PLAN (a sketch — we'll refine each phase together)
1. FastAPI skeleton + SQLite tables
2. Replicate client + schema introspection
3. Dynamic form rendering from model schema  
4. Numeric sweep: toggle, parallel generation, grid streaming
5. Prompt sweep: Claude expansion + editable previews
6. Polish + deploy

WORKING STYLE
- Use plan mode for each new chunk. Show me the plan, I approve, then you code.
- Show me file changes one file at a time, smallest files first.
- After each file, pause and let me confirm before continuing.
- If you're about to use a library or pattern I might not know, briefly 
  explain it before writing the code.

Read it carefully and confirm 
you understand the architecture. Don't write any code yet. Ask any 
clarifying questions, then I'll send the first hour's prompt.
