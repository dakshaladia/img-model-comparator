Plan is good. 

Some additions to polish the work:

1. Cost preview. Add a small line below the Run button: "Estimated cost: 
   ~$X.XX (N cells × Model Name)". Update dynamically as user changes 
   model or toggles sweep values. ~15 lines of JS in sweep.js. Reads from 
   COST_PER_IMAGE_USD in config.py.

2. Empty state for #results-target. Default content "Run a sweep to see 
   results here" with subtle gray styling. Gets swapped out when the 
   first sweep response arrives.

3. Generation timing visible on completed cells. cell_final.html should 
   show "{{ '%.1f' | format(gen.generation_ms / 1000) }}s" as a small 
   badge on each completed cell. Phase 4's data is there; just surface it.

4. Header/branding on the page. Top bar with "Sweep" title and a 
   one-line tagline ("Parameter exploration for generative image models"). 
   Anchors the page, signals this is a product, not a prototype.

On the SQLite-resets-on-deploy decision:

Don't accept the reset. Add a Fly.io volume:

   [[mounts]]
     source = "sweep_data"  
     destination = "/app/data"

Plus: fly volumes create sweep_data --size 1 (before first deploy).

Reasoning: if a reviewer is mid-sweep when I deploy (or even just 
re-running my own demo and hitting any edge case), the cell polling 
returns 404s because the generation rows vanished. Low probability, bad 
cost. A 1GB volume eliminates the problem at near-zero ops cost.

CLARIFICATION on error state:

Drop the "retry hint" language. Build the visual treatment only: red 
border, error icon, error text. A working retry button is real feature 
work and out of scope for the slice. Just don't make the failed cells 
look like loading cells.

Dont build the APPROACH.md just yet. I will write it first on my own and then we can refine it together. 

