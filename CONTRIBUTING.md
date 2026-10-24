# Contributing

Thank you for helping students learn photonic layout. Contributions of every size are welcome: typo fixes, clearer explanations, new device recipes, new foundry adapters and bug reports from your Lumerical version.

## Development set-up

```bash
git clone https://github.com/q3430468220-tech/photonics-layout-cookbook.git
cd photonics-layout-cookbook
uv sync                    # runtime + dev dependencies (pytest, ruff, pre-commit)
uv run pre-commit install  # optional: lint on every commit
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

## Adding a device recipe

A recipe is accepted when it has the following parts.

1. **Geometry** in `src/photonics_cookbook/devices/<device>.py`: a pure-Python function that takes a `Process` and returns a `Geometry` (polygons on roles, ports, `info`). No gdsfactory import here, so it can be unit-tested anywhere.
2. **A gdsfactory cell** in `src/photonics_cookbook/cells.py` decorated with `@gf.cell`, built with `geometry_to_component` (polygons) or by extruding a PDK cross-section, and added to `CELLS` so that the cookbook PDK registers it (`gf.get_component("<name>")`). New waveguide profiles go into the PDK as cross-sections (`photonics_cookbook/pdk/builder.py`), with their geometry in `devices/`.
3. **Simulation hints** in `info["lumerical"]` (cut line, origin, bend radius, normalisation length, contact roles) where they make sense.
4. **Tests** in `tests/`: dimensions on a cut line, ports, rejected parameters, and anything that would be a fabrication error (shorts, missing enclosures).
5. **An example folder** `examples/<level>/<nn>_<device>/` with numbered scripts and a README: what the device does, which Ansys example or paper it follows, a parameter table with trade-offs, and three to five exercises.

Please cite the source of every default number (Ansys example, paper, design manual) in a comment or the README.

## Adding a foundry adapter

Follow [docs/process-adapters.md](docs/process-adapters.md) and [docs/pdk-tutorial.md](docs/pdk-tutorial.md): a process YAML is all that is needed, the gdsfactory PDK is generated from it. Only use open PDKs and publicly available design documents, list them under `references:`, and never commit NDA data.

## Reporting a Lumerical problem

Include your Lumerical version (for example 2025 R1), the product (FDTD / MODE / CHARGE), the generated script and the full message from the script prompt. Many issues are property-name differences between versions, which we can fix with a fallback.
