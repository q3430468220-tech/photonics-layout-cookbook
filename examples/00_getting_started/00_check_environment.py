"""00 -- Check that the environment works and meet the CORNERSTONE PDK.

Run:
    uv run python examples/00_getting_started/00_check_environment.py

What it shows
    1. versions of gdsfactory / cspdk / klayout,
    2. how to *activate* a foundry PDK and list its cells and layers,
    3. that the cookbook's process file agrees with the PDK's layer numbers,
    4. a first layout: a PDK cell written to GDS (open it in KLayout).

Next: 01_define_your_pdk.py -- how such a PDK is defined, and how the cookbook
extends cspdk with the active layers (implants, vias, metal).
"""

from __future__ import annotations

import importlib.metadata as md

import gdsfactory as gf

from photonics_cookbook.paths import build_dir
from photonics_cookbook.process import load_process
from photonics_cookbook.process.upstream import check_against_pdk, import_pdk

PROCESS = "cornerstone_si220_active"


def version(pkg: str) -> str:
    try:
        return md.version(pkg)
    except md.PackageNotFoundError:
        return "not installed"


def main() -> None:
    print("== 1. versions")
    for pkg in ("gdsfactory", "kfactory", "cspdk", "klayout", "photonics-layout-cookbook"):
        print(f"   {pkg:<22} {version(pkg)}")

    print("\n== 2. activate the foundry PDK")
    proc = load_process(PROCESS)
    module, pdk = import_pdk(proc.upstream_pdk["modules"])  # cspdk.si220 (>=2.0) or .cband (<2.0)
    pdk.activate()
    cells = sorted(pdk.cells)
    print(f"   {module}: {len(cells)} cells, e.g. {', '.join(cells[:12])} ...")
    xs = sorted(getattr(pdk, "cross_sections", {}) or {})
    print(f"   cross-sections: {', '.join(xs[:10])}")

    print("\n== 3. cookbook process vs PDK layers")
    _, checks = check_against_pdk(proc)
    for c in checks:
        print(f"   [{c.status:<9}] {c.role:<13} {c.name:<10} {c.process_gds}")
    print("   ('extension' = not in cspdk, added by the cookbook PDK in the next lesson)")

    print("\n== 4. first layout from a PDK cell")
    name = next((n for n in ("straight", "ring_single", "mmi1x2") if n in pdk.cells), cells[0])
    c = gf.get_component(name)
    gds = c.write_gds(build_dir("00_getting_started") / f"{name}.gds")
    print(f"   {name}: ports {[p.name for p in c.ports]}")
    print(f"   written {gds}  -> open it in KLayout (or call c.show() with klive running)")


if __name__ == "__main__":
    main()
