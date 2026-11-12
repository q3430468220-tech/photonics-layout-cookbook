# legacy: the v0.1 architecture

Everything in this folder is the previous structure of the cookbook, kept for reference only:

- `src/photonics_cookbook/`: an installable package with a YAML process file, a generated PDK that
  extended `cspdk`, and a bridge that wrote Lumerical `.lsf` scripts from a GDS;
- `examples/`, `docs/`, `tests/`: its examples, documentation and tests.

It is no longer installed, tested or maintained. Since v0.2 the flat flow lives in
[more_processes/cornerstone_soi220a/](../more_processes/cornerstone_soi220a/README.md): technology
file, device builder, process file, numbered simulation steps. Since v0.3 the course is the root of
the repository, on the GSiP teaching PDK; see the [README](../README.md) there.

Two things changed in substance, not only in structure:

- the process data now comes from CORNERSTONE's official open PDK repository and the active design
  guidelines, and uses the official SOI220A layer names (v0.1 used the `cspdk` passive names plus
  layers `39/0` and `41/0`, which the active platform does not have);
- simulations build their geometry from a Layer Builder process file (`.lbr`) and drive the solvers
  through `lumapi`, instead of generating `.lsf` scripts.

The folder can be deleted once nothing in it is needed:

```bash
git rm -r legacy
```
