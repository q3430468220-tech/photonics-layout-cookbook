# Contributing

Contributions of every size are welcome: typo fixes, clearer explanations, bug reports from your
Lumerical version, new devices and new open processes.

## Set-up

```bash
git clone https://github.com/q3430468220-tech/photonics-layout-cookbook.git
cd photonics-layout-cookbook
uv sync                    # runtime and development dependencies
uv run pre-commit install  # optional: lint and format on every commit
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Tests, lint and layout need no Lumerical. CI runs them on Linux and Windows.

## The one rule about data

**Only public data.** Every layer name, layer number, thickness, doping level and design rule must
come from a document anyone can download. Give the source next to the number, with the tags the
repository already uses (`[YAML]`, `[DG]`, ...). Mark a value you had to assume as `[assumed]`.
Never commit a PDK, a design manual or numbers you received under an NDA, also not "anonymised".

## Adding a device

A device follows the structure of the ring modulator.

1. **A builder** `<device>_builder.py` in the repository root. It takes its cross-sections,
   layers and rules from the technology file and defines none of its own. Running it writes the
   GDS with `write_gds_for_lumerical`, runs the DRC and renders the preview images.
2. **Tests** in `tests/`: the builder passes the DRC for its default and for a few other
   parameter sets, it rejects parameters that would break a rule, and its key dimensions are what
   the arguments say.
3. **Simulation steps** in `lumerical_simulations/<device>/scripts/`, one script per solver run.
   Each script draws a small GDS with the PDK, loads it with the process file through
   `common.add_layer_builder`, and writes a `.txt` summary. No thickness, material or doping in a
   script.
4. **Plots** in `lumerical_simulations/<device>/plots/<step>/`, readable without Lumerical.
5. **A README** in `lumerical_simulations/<device>/`: what each step answers, how to run it, the
   results, the settings that matter, and the limits of the model.

State which runs you actually executed, with the Lumerical version. Do not report numbers from a
run you did not make.

## Adding a process

1. A technology file `<foundry>_technology.py`, modelled on `cornerstone_technology.py`. Keep the
   foundry's own layer names.
2. A DRC, modelled on `cornerstone_drc.py`.
3. A folder `<foundry>_process_file_py/` with the CSV tables, a README that gives the source of
   every number, and the compiler. The compiler's read-back check must pass.
4. Tests that tie the tables to the technology file, as in `tests/test_process_tables.py`.
5. A table of the places where the public sources disagree, and which value you chose.

## Reporting a Lumerical problem

Include the Lumerical version, the product (FDTD, MODE, CHARGE, HEAT, INTERCONNECT), the script
and its arguments, and the full message. Many problems are property names that differ between
versions.
