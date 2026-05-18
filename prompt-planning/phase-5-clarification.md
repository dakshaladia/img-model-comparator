Plan is mostly good, requires some fixes though.

I think you should: replace fetch() with HTMX.

Your justification ("so JS can populate textareas without replacing the 
form") is wrong - HTMX can absolutely do that via hx-target pointing at 
.prompt-variations and hx-swap="innerHTML". Using fetch here breaks the 
consistency of the codebase. Every other interaction is HTMX-driven; 
this would be the one JSON endpoint with JS-side HTML construction. 
That's a wart that's hard to defend live.

The Preview button should be:

<button type="button"
        hx-post="/prompt-expand"
        hx-target="closest .prompt-variations"
        hx-swap="innerHTML"
        hx-vals='js:{base_prompt: <read from the fixed textarea>, 
                     direction: <read from select>, 
                     count: <read from select>}'>
    Preview
</button>

And routes/prompt.py should return a TemplateResponse rendering a new 
partial templates/partials/prompt_variations.html - a simple loop of N 
<textarea name="sweep__prompt"> elements with the variation text.

This shrinks static/sweep.js by ~30 lines (no fetch, no JSON parsing, no 
DOM construction) and keeps the pattern uniform.

other fixes:

1. Note in the plan that this REPLACES the Phase 4 placeholder for 
   prompt's else-branch in input_field.html - it's not extending new 
   work, it's swapping in the real implementation. Mention this in the 
   plan so the diff reads cleanly.

2. axis_position for prompt sweeps is the index in the variation list 
   (0 for first variation, 1 for second, etc.). Same shape as numeric 
   sweep. Just confirm.

3. Drop the "if sweep_name == 'prompt' then truncate" conditional. 
   Always truncate labels to a max length (60 chars) regardless of 
   which input is swept. Cleaner than special-casing prompt.

4. The system prompt for Claude needs more structure than "produce 
   variations along the axis." Include:
   - Preserve the subject. Vary only the axis dimension.
   - Span a meaningful range - extreme to subtle, not microscopic tweaks.
   - Each variation must be a complete, self-contained image prompt 
     (full sentence, not a fragment).
   - Output ONLY a JSON array of strings.
   
5. Write a set of tests to test the implementation and make sure nothing breaks. 