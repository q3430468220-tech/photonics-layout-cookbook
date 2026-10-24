"""03 -- Run the generated scripts through lumapi: CHARGE -> MODE (FDE).

Needs a local Ansys Lumerical installation (2022 R1 or newer) and licences.

Run:
    set LUMERICAL_ROOT=D:\\Program Files\\ANSYS Inc\\v251\\Lumerical      (Windows, cmd)
    $env:LUMERICAL_ROOT="D:\\Program Files\\ANSYS Inc\\v251\\Lumerical"  (PowerShell)
    uv run python examples/01_devices/01_ring_modulator/03_run_lumerical.py

Tip: if the repo lives under a non-ASCII path, also set PHOTONICS_BUILD_DIR=D:\\photonics_build
and re-run 01 / 02 so that the Lumerical working folder is ASCII-only.
"""

from __future__ import annotations

import argparse

from photonics_cookbook.lumerical.runner import run_script
from photonics_cookbook.paths import build_dir


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", help="Lumerical folder (overrides LUMERICAL_ROOT)")
    ap.add_argument("--hide", action="store_true", help="run without GUI windows")
    ap.add_argument("--fdtd", action="store_true", help="also build the 3D FDTD project")
    args = ap.parse_args()

    lum = build_dir("01_ring_modulator", "lumerical")
    steps = [
        ("charge", lum / "ring_modulator_charge2d.lsf"),
        ("mode", lum / "ring_modulator_fde2d.lsf"),
    ]
    if args.fdtd:
        steps.append(("fdtd", lum / "ring_modulator_fdtd3d.lsf"))
    for product, script in steps:
        if not script.exists():
            raise SystemExit(f"{script} missing -- run 02_export_to_lumerical.py first")
        print(f"== {product.upper():<6} {script.name}")
        run_script(product, script, root=args.root, hide=args.hide)
    print(f"done -- results (*.mat, *.ldev, *.lms) are in {lum}")


if __name__ == "__main__":
    main()
