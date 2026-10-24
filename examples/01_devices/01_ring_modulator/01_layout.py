"""01 -- Draw a doped microring modulator for the CORNERSTONE 220 nm active process.

Run:
    uv run python examples/01_devices/01_ring_modulator/01_layout.py

Outputs (in build/01_ring_modulator/):
    ring_modulator.gds          the layout (open in KLayout)
    ring_modulator_top.png      annotated top view with the CHARGE / FDE cut line
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from photonics_cookbook.cells import activate_pdk, ring_modulator
from photonics_cookbook.devices import ring_modulator_geometry
from photonics_cookbook.paths import build_dir
from photonics_cookbook.plotting import plot_geometry, save
from photonics_cookbook.process import load_process

PROCESS = "cornerstone_si220_active"

# In-plane parameters of the Ansys Lumerical "Ring Modulator" example.
PARAMS = dict(
    radius=10.0,  # um, ring radius (Ansys example: 10 um)
    width=0.5,  # um, rib width
    gap=0.2,  # um, bus-ring gap (sweep it in FDTD for critical coupling)
    junction_offset=0.0,  # um, PN junction position from the rib centre (+ = outwards)
    contact_spacing=0.8,  # um, rib edge -> P++/N++ (series resistance vs. optical loss)
)


def main() -> None:
    out = build_dir("01_ring_modulator")
    proc = load_process(PROCESS)
    print(proc.summary(), "\n")

    # --- step 0: activate the foundry PDK (cspdk for CORNERSTONE) -----------------
    # gdsfactory resolves layers through the *active* PDK, so do this before drawing.
    pdk = activate_pdk(PROCESS)
    print(f"active PDK: {pdk.name}\n")

    # --- the gdsfactory way: a cached, parametrised cell -------------------------
    c = ring_modulator(**PARAMS, process=PROCESS)
    gds = c.write_gds(out / "ring_modulator.gds")
    print(f"cell     : {c.name}")
    print(f"ports    : {[(p.name, p.port_type) for p in c.ports]}")
    print(f"doped arc: {c.info['doped_angle_deg']} deg = {c.info['doped_length_um']} um")
    print(f"GDS      : {gds}")

    # --- a teaching preview (same geometry, matplotlib) --------------------------
    g = ring_modulator_geometry(proc, **PARAMS)
    lum = g.info["lumerical"]
    cut = (tuple(lum["cut_p0_um"]), tuple(lum["cut_p1_um"]))
    fig, axs = plt.subplots(1, 2, figsize=(13, 6.5))
    plot_geometry(g, proc, ax=axs[0], cut=cut)
    r = PARAMS["radius"] + 5
    plot_geometry(g, proc, ax=axs[1], xlim=(-r - 3, r + 3), ylim=(-r - 1, r + 5), cut=cut)
    axs[1].set_title("zoom: implants, vias, CHARGE cut")
    print(f"preview  : {save(fig, out / 'ring_modulator_top.png')}")


if __name__ == "__main__":
    main()
