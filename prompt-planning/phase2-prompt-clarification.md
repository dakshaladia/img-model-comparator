Plan is mostly good.Keep the awareness for the schema parser in Phase 3.

But there are two scope issues to fix before you implement:

1. Phase 2 is doing Phase 4's work. Pull these out:

   a. run_generation belongs in services/sweep_engine.py in Phase 4, NOT here. It's orchestration logic (semaphore, status transitions, timing) - not transport. services/replicate_client.py should be a pure transport layer.
   
   b. Schema parsing (raw schema dict -> list[ModelInput]) belongs in services/schema.py in Phase 3. fetch_schema in this phase should return the raw dict, not a parsed list.

2. Phase 2 becomes simpler - just two thin async wrappers around the SDK:

   - fetch_schema(slug: str) -> dict
    Returns the raw OpenAPI schema dict from Replicate. No parsing, no caching in this function. Caching is the caller's concern.
   
   - run_model(slug: str, inputs: dict) -> str
    Calls replicate.async_run(slug, input=inputs), parses the output (handle: bare string, list, FileOutput object with .url), returns the first image URL. No SQLite, no semaphore.
   
   Plus a smoke test scripts/test_replicate.py that:
   - Fetches schema for all 6 models, prints input counts, caches the raw schemas via storage.cache_schema (this is where caching gets wired in)
   - Calls run_model('black-forest-labs/flux-schnell', {'prompt': 'a red cube'}) and prints the URL

Hold off on changes to models.py. ModelInput might need new fields for 
file/format handling - but we can add them in Phase 3 when the schema parser 
gives us concrete evidence of what's needed.