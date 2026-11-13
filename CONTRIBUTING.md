# Contributing

Contributions of every size are welcome: typo fixes, clearer explanations, bug reports from your
Lumerical version, new devices and new open processes. The course is written for a reader who
has simulated devices but has never written a PDK, so explanations matter as much as code.

## Set-up

The project uses [uv](https://docs.astral.sh/uv/) for a reproducible Python environment. Python
3.12 or 3.13 is required.

```bash
git clone https://github.com/q3430468220-tech/photonics-layout-cookbook.git
cd photonics-layout-cookbook
uv sync                    # creates .venv from uv.lock: runtime and development dependencies
uv run pre-commit install  # optional: ruff, ruff format and whitespace checks on every commit
```

Layout, the DRC, the tests and the figures need no Lumerical. Only the process-file compiler and
the simulation scripts need it, with its FDTD, MODE, CHARGE, HEAT and INTERCONNECT licences.
Set `LUMERICAL_ROOT` if Lumerical is not in a standard location.

## Checks before a pull request

Run these from the root of the repository. CI runs the lint and both test suites on Linux and
Windows, with Python 3.12 and 3.13. It does not run the format check, so run that one yourself.

```bash
uv run ruff check .                                   # lint (CI runs this)
uv run ruff format --check .                          # formatting (only you run this)
uv run pytest                                         # the tests of the main example (85 tests)
cd more_processes/cornerstone_soi220a && uv run pytest  # the tests of the second process (24 passed, 1 skipped)
```

If the format check fails, run `uv run ruff format .` and look at the diff before you commit.
The `ruff` settings, the line length of 130 and the rule sets, are in `pyproject.toml`. Ruff leaves
Markdown alone: `pyproject.toml` excludes `*.md`, so the snippets and tables of the course keep their
hand-set alignment.

The second process has its own folder and its own `pytest.ini`. Run its tests from that folder,
as shown above. One of its tests is skipped unless the environment variable `CORNERSTONE_PDK` is set.

## The rule about data

**Only public data.** Every layer name, layer number, thickness, doping level and design rule must
come from a document anyone can download. Three rules follow.

1. **A source tag on every number.** Put the tag next to the value in the code, in the CSV tables
   and in the text. The repository uses these tags:
   - `[B]`, `[BJ]`, `[GF]`, `[T]` for the main example. The list is in the docstring of
     `gsip_technology.py` and in `gsip_process_file_py/gsip_csv/README.md`.
   - `[YAML]`, `[DG]`, `[XS]`, `[MZM]`, `[HTR]` for CORNERSTONE SOI220A, defined in the docstring
     of `more_processes/cornerstone_soi220a/cornerstone_technology.py`.
   - `[assumed]` for a value that no public source gives. Say what you used instead and why.
2. **Public sources that disagree are recorded, not hidden.** Add a row to the table of
   inconsistencies, as in `more_processes/cornerstone_soi220a/cornerstone_process_file_py/cornerstone_csv/README.md`,
   and say which value the code uses.
3. **Never commit anything received under an NDA.** That includes a PDK, a design manual, a
   tape-out file, and numbers from a foundry, also when they are "anonymised" or "rounded". If a
   value is public, cite the public document. If it is not, it does not go into the repository.

A public source is one that anyone can download without a licence or a registration with a
foundry. A repository that you can clone without permission counts. A document that a foundry or
a partner gave you under an agreement does not, even if a copy is found on the internet.

## Adding a device

A device follows the structure of the ring modulator. The steps below name the files to copy. The
main example is the template; the second process has the same structure with different names.

1. **Write the builder.** Copy `rm_builder.py` to `<device>_builder.py` in the root. Keep the
   cross-sections, the layers and the rules from the technology file (`gsip_technology.py`). Do
   not define layers or dimensions that a rule owns. Its `__main__` block writes the GDS with
   `write_gds_for_lumerical`, runs `run_drc` and prints the report.
2. **Add tests.** In `tests/`, add one file per device. Check that the builder passes the DRC at
   its default and at two or three other parameter sets, that it rejects a parameter set that
   breaks a rule, and that its key dimensions are the ones the arguments say. Copy the pattern of
   `tests/test_layout.py`.
3. **Add the simulation steps.** Create `lumerical_simulations/<device>/scripts/` with a
   `common.py` (copy the one of `ring_modulator`, and change only the device parameters). Add one
   script per solver run, named after the question it answers. Each script builds a small GDS with
   the PDK, loads it with the process file through `add_layer_builder`, and writes a `.txt` summary
   and a `.npz` of the result arrays. No thickness, material or doping level goes into a script.
4. **Add the figures.** Create `lumerical_simulations/<device>/figures/` with one `fig<n>_<name>.py`
   per figure. Each script reads the `.npz` files of its steps, so that it runs without Lumerical.
   Follow the rules in the next section.
5. **Write the README.** Create `lumerical_simulations/<device>/README.md` with what each step
   answers, how to run it, the results, the settings that matter and the limits of the model. The
   README of `ring_modulator` is the template.

State which runs you actually executed and with which Lumerical version. Do not report numbers from
a run you did not make.

## Adding a simulation step

A step is one solver run with one question. To add one to an existing device:

1. Write `scripts/<step>.py` in the device's folder. It uses `common.py` for the process file and
   the geometry, and writes its results to a step folder such as `6_interconnect_ring_modulator/`.
2. Name the step folder with the next number, and keep its small GDS and its `.txt` summary there.
   Ignore the Lumerical projects in `.gitignore`, as the other folders do.
3. Add `figures/fig<n>_<name>.py` that draws the result from the `.npz` file. Add it to the list in the
   README of the device.
4. If the step needs the output of an earlier step, say so in its docstring and in the README.

## Adding a process

A process gets its own technology file, DRC and process tables. The second process is the model:
copy the folder `more_processes/cornerstone_soi220a/` to start, and replace the contents.

1. **The technology file.** Copy `cornerstone_technology.py` to `<foundry>_technology.py`. Replace the
   constants, the layer map, the design rules and the cross-sections. Keep the foundry's own layer
   names, and give the source of each constant in a comment.
2. **The DRC.** Copy `cornerstone_drc.py` to `<foundry>_drc.py`, and change the rules it checks to
   those of the process. Write the check as a pure Python function that returns a result with a
   `passed` flag.
3. **The process file.** Copy the folder `cornerstone_process_file_py/` to `<foundry>_process_file_py/`
   and fill the CSV tables. Keep the column names of the Ansys template, so that each table can
   be compared with the Ansys example line by line. The README in the `csv` folder gives the source
   of every number. The compiler must write the `.lbr` and read it back, and the read-back must
   pass before the process is accepted.
4. **Tests.** Add tests that tie the tables to the technology file, as in
   `tests/test_process_tables.py`.
5. **The inconsistencies table.** List every place where the public sources disagree, and which value
   you chose.

## Figures

Every figure of the course is drawn by a script from data kept in the repository. The rules are
short.

- **Use `figstyle.py`.** It sets the fonts, sizes, line widths, colour maps and panel labels of the
  journal style. Do not set your own style in a figure script. Read its docstring first: it lists the
  widths (89, 120 and 183 mm), the thin lines, the colour rules that survive colour-vision
  deficiency and greyscale, and the call that saves a figure.
- **One script per figure.** A file `fig<n>_<name>.py` draws one figure and writes one PNG, at 400
  dpi, into its folder. The script must run without Lumerical.
- **Numbers computed from the data.** Every number in a title, a label or an annotation comes from
  the `.npz` or `.txt` file, computed in the script. Do not type a number into a figure.
- **Panel labels.** Label the panels a, b, c with `figstyle.panel_label`, in the order the caption
  describes them.
- **Caption and README.** Each figure has a caption in the README that says what each panel shows,
  and the source it was drawn from.

## Writing style of the documents

The course is read by students, so the documents follow one style.

- Plain, direct English. Short sentences. Say what a thing is before what it is for. Define a term the
  first time it appears (PDK, DRC, process file, Layer Builder, FSR, critical coupling).
- A teaching text, not marketing. No superlatives, and no "powerful", "seamless", "simply" or "just".
- No em-dashes. Use the micro sign µ and a real minus sign − in text. Code blocks stay ASCII.
- Tables for parallel facts. Numbered lists for procedures. Short paragraphs for reasoning.
- Every number has a unit and a source, which is a file of the repository or one of the references.
- Code blocks must be copy-paste correct. Commands follow the script docstrings. Python snippets must
  run against the current code.
- Lead each section with the idea, then the detail, then how to check it. Prefer one worked example
  to three abstract sentences.
- Figures are shown as `<p align="center"><img src="RELATIVE/PATH.png" width="100%" alt="..."></p>`,
  followed by a caption that starts with `**Figure N.**`. Links are relative to the document's folder.
- A chapter starts with a line of navigation: the previous chapter, the course map, the next chapter.
  It ends with "Check yourself" (three to six questions that the text answers) and "Exercises"
  (concrete changes to try, each naming the file to edit and what to observe).

## Reporting a Lumerical problem

Include the Lumerical version, the product (FDTD, MODE, CHARGE, HEAT or INTERCONNECT), the script
and its arguments, and the full message. Many problems are property names that differ between
versions.

## Licence

By contributing you agree that your contribution is released under the MIT licence of the
repository.
