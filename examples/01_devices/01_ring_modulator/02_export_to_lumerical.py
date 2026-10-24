"""02 -- From the GDS to Ansys Lumerical: generate FDTD / MODE / CHARGE scripts.

Run (after 01_layout.py):
    uv run python examples/01_devices/01_ring_modulator/02_export_to_lumerical.py

Or for *any* GDS, without Python code:
    uv run photonics-cookbook to-lumerical build/01_ring_modulator/ring_modulator.gds \
        --process cornerstone_si220_active --cut 5.45,0 14.55,0 --origin 10,0 \
        --norm-length 46.5 --bend-radius 10

The bridge reads *only* the GDS file + the process YAML, so it works for layouts
from KLayout, a foundry PCell or another tool as well.
"""

from __future__ import annotations

from photonics_cookbook.cells import activate_pdk, ring_modulator
from photonics_cookbook.lumerical import export_lumerical, info_from_component, ports_from_component
from photonics_cookbook.paths import build_dir
from photonics_cookbook.process import load_process

PROCESS = "cornerstone_si220_active"


def main() -> None:
    out = build_dir("01_ring_modulator")
    gds = out / "ring_modulator.gds"

    activate_pdk(PROCESS)
    c = ring_modulator(process=PROCESS)  # same parameters as 01_layout.py
    if not gds.exists():
        c.write_gds(gds)

    res = export_lumerical(
        gds,
        PROCESS,
        out / "lumerical",
        ports=ports_from_component(c),  # optical ports -> FDTD ports
        info=info_from_component(c),  # cut line, bend radius, doped length, contacts
        v_stop=-4.0,  # CHARGE sweep 0 .. -4 V (reverse bias)
        n_points=9,
    )
    print(res)
    if res.xsec is not None:
        print()
        print(res.xsec.describe(load_process(PROCESS)))
    print(
        "\nNext:\n"
        "  CHARGE : run ring_modulator_charge2d.lsf  (writes ring_modulator_charge.mat)\n"
        "  MODE   : run ring_modulator_fde2d.lsf     (neff, loss, pm/V vs bias)\n"
        "  FDTD   : run ring_modulator_fdtd3d.lsf    (3D: bus-ring coupling / spectrum)\n"
        "  or     : uv run python examples/01_devices/01_ring_modulator/03_run_lumerical.py"
    )


if __name__ == "__main__":
    main()
