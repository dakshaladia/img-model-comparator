Plan is solid - clearly grounded in the actual Phase 2 schema output, 
which is the right approach.

A few things to address before you implement:

1. Input naming convention. All form fields rendered in input_field.html should use name="input__<name>" - e.g., name="input__prompt", name="input__seed", name="input__aspect_ratio". This sets up Phase 4 to distinguish fixed inputs from sweep inputs by prefix. Don't use the bare name.

2. Boolean inputs should render as <select> with true/false options, NOT <input type="checkbox">. This keeps the form uniform and means Phase 4's sweep toggle works the same way for all input types. Specifically:
   
   <select name="input__go_fast">
     <option value="true" selected>true</option>
     <option value="false">false</option>
    </select>

3. Drop the "sweep toggle placeholder" hidden div. Phase 4 will add the toggle markup properly. If you want a structural hook for Phase 4, wrap each input field in <div data-sweep-toggle="{{ input.name }}"> so Phase 4 has a clear attachment point - but no hidden elements doing nothing.