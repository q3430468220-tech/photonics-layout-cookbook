"""1x2 multimode interference (MMI) splitter on the GSiP teaching process, ready for the Lumerical Layer Builder.

                          ┌──────────────┐◁════ o2
    o1 ════▷              │   multimode  │
                          └──────────────┘◁════ o3
         taper              section        tapers

The input waveguide widens into a short, wide section that guides several modes.  They travel at different
speeds, and at a certain length they add up to two copies of the input field, side by side.  Two output
waveguides sit there.  The split is 50:50 by symmetry; the length decides the loss.

    mmi1x2()   the device; the widths, the length and the taper dimensions are arguments

The cross-section, the layers and the design rules come from gsip_technology.py.

    python devices/mmi1x2_builder.py     ->  devices/gds/mmi1x2.gds, DRC report, preview image
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the repository root: gsip_technology, devices
import gdsfactory as gf

import gsip_technology as t

WIDTH = 0.5  # um, core width of the three access waveguides
WIDTH_MMI = 2.5  # um, width of the multimode section
LENGTH_MMI = 5.5  # um, the length of lowest loss at 1.55 um: step 1 of lumerical_simulations/mmi1x2
WIDTH_TAPER = 1.0  # um, width of each access waveguide where it meets the multimode section
LENGTH_TAPER = 10.0  # um
GAP_MMI = 0.25  # um, between the two output tapers at the multimode section


@gf.cell
def mmi1x2(
    length_mmi: float = LENGTH_MMI,
    width_mmi: float = WIDTH_MMI,
    width_taper: float = WIDTH_TAPER,
    length_taper: float = LENGTH_TAPER,
    gap_mmi: float = GAP_MMI,
    width: float = WIDTH,
) -> gf.Component:
    """1x2 MMI splitter, with the input face of the multimode section at x = 0.

    Args:
        length_mmi: length of the multimode section (um).  The default is the length of lowest loss
            found by step 1 of the simulations.
        width_mmi: width of the multimode section (um).
        width_taper: width of the access waveguides at the multimode section (um).
        length_taper: length of the three tapers (um).
        gap_mmi: edge-to-edge gap between the two output tapers at the multimode section (um).
        width: core width of the access waveguides away from the device (um).

    Ports: o1 (input, west), o2 (upper output) and o3 (lower output), both east.
    ``info`` stores the dimensions and the distance between the two outputs.
    """
    space = t.MIN_WIDTH_SPACE["WG"][1]
    if gap_mmi < space:
        raise ValueError(f"gap_mmi {gap_mmi} um is below the minimum space of the waveguide layer, {space} um")
    if min(width, width_taper) < t.MIN_WIDTH_SPACE["WG"][0]:
        raise ValueError(
            f"the access waveguides are narrower than the minimum width of the waveguide layer, {t.MIN_WIDTH_SPACE['WG'][0]} um"
        )
    if 2 * width_taper + gap_mmi > width_mmi:
        raise ValueError(
            f"the two output tapers ({width_taper} um each) and their gap ({gap_mmi} um) are wider than the "
            f"multimode section ({width_mmi} um)"
        )
    xs = gf.get_cross_section("strip", width=width)
    c = gf.Component()
    ref = c << gf.components.mmi1x2(width=width, width_taper=width_taper, length_taper=length_taper, length_mmi=length_mmi,
                                    width_mmi=width_mmi, gap_mmi=gap_mmi, cross_section=xs)  # fmt: skip
    c.add_ports(ref.ports)
    c.info["length_mmi"] = length_mmi
    c.info["width_mmi"] = width_mmi
    c.info["width_taper"] = width_taper
    c.info["length_taper"] = length_taper
    c.info["gap_mmi"] = gap_mmi
    c.info["output_pitch"] = round(width_taper + gap_mmi, 3)
    return c


if __name__ == "__main__":
    from devices import write_device

    device = mmi1x2()
    info = device.info
    print(f"MMI: multimode section {info['width_mmi']} x {info['length_mmi']} um, tapers {info['width_taper']} um wide "
          f"and {info['length_taper']} um long, outputs {info['output_pitch']} um apart")  # fmt: skip
    sys.exit(write_device(device, "mmi1x2"))
