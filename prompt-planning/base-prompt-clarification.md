1. SQLite schema — three tables:
   - sweep_runs: one row per sweep the user kicks off. Stores model 
     slug, fixed inputs (JSON), axes (JSON list), timestamp.
   - generations: one row per image generation. Foreign key to 
     sweep_runs. Stores the full inputs dict for this specific 
     generation, axis_position (where it goes in the grid), label 
     (human-readable: "guidance=4.5" or the expanded prompt), status 
     (pending | running | complete | failed), output_url, error, 
     generation_ms.
   - model_schemas: 24-hour cache of Replicate OpenAPI schemas. 
     Columns: slug (PK), schema_json, cached_at.
   
   Form state is ephemeral — lives in browser DOM, never persists. 
   No "session" concept. No users table. Single user, single canvas 
   of state.

2. Schema introspection — mostly right, two clarifications:
   - Don't filter inputs out. ALL inputs render in the form. Some 
     are marked non-sweepable (the Sweep toggle is hidden for them): 
     image, mask, init_image, control_image. Put these in a 
     NEVER_SWEEP_INPUT_NAMES constant in config.py.
   - The prompt is treated like any other input. Its only "special" 
     behavior is that when toggled to Sweep, the value editor 
     becomes a "pick a direction + Preview" UI that calls Claude. 
     In Fixed mode it's just a textarea like other string inputs.

3. Streaming in — yes, stream. Each cell in the grid polls 
   /cell/{generation_id} every 2 seconds via HTMX. The cell endpoint 
   returns one of two templates: cell_polling (has hx-get and 
   hx-trigger, keeps polling) for pending/running states, or 
   cell_final (NO hx-* attributes) for complete/failed. Polling 
   auto-stops when the template flips. No SSE, no WebSockets.

4. REPLICATE_API_TOKEN — yes, add to .env.example. Final shape:
   
   REPLICATE_API_TOKEN=
   ANTHROPIC_API_KEY=
   
   I have real values for both in my .env already.

5. No history/gallery view in this slice. Each sweep is 
   self-contained — the user kicks one off, watches results stream 
   in, possibly changes inputs and kicks off another. SQLite still 
   matters though: the cell polling endpoint reads status from the 
   DB, sweeps survive server restart, and schema caching lives 
   there. History view is a "what I'd build next" item.