Mostly correct. Three things to fix in your mental model:

1. CRITICAL - Step 3, the parallelism. POST /sweep does NOT await all 
   generations. The flow is:
   
   a. Insert 1 sweep_run row + N generation rows (status="pending") 
    | into SQLite synchronously
   b. For each generation, fire asyncio.create_task(run_one_generation(gen)) 
      - fire-and-forget into the background
   c. Immediately return partials/grid.html with N cells, each rendered 
      as cell_polling.html showing the pending state
   d. The background tasks run inside an asyncio.Semaphore(6). They 
      update each generation's row in SQLite as they transition 
      (pending -> running -> complete | failed)
   e. The cells poll /cell/{id} every 2s and read live status from SQLite
   
   This is asyncio.create_task (fire-and-forget), NOT asyncio.gather 
   (await-all). The HTTP response returns within ~100ms, not 30+ seconds.

2. Step 2 - Route is GET /model-form?slug=X (query param), not 
   /form/{slug} (path param). The model dropdown uses 
   hx-get="/model-form" with hx-include reading the slug from the 
   <select>. Also: one partial file `partials/input_field.html` with 
   internal {% if input.type == ... %} branches, NOT separate 
   `components/input_string.html` etc. - too granular.

3. Step 5 - Route is POST /prompt-expand. The direction is picked from 
   a dropdown of preset axes (camera angle, lighting, art style, mood, 
   etc.) from PROMPT_SWEEP_DIRECTIONS in config.py - not typed freely. 
   After Preview, the N variations appear as editable textareas - user 
   can manually tweak any before hitting Run.

Otherwise the data flow is right. Confirm you've internalized these 
three corrections and let's move into Phase 1 planning.