"""Step 3 - FDTD: the coupler as drawn: split, loss and reflection across the band, and the field.

Model: the layout that devices/directional_coupler_builder.py writes, with a straight lead at each port,
loaded into a Layer Builder with gsip_process.lbr.  The length of the straight section is the 50:50
length of step 2.

    port 2 ════╗                  ╔════ port 3      cross
               ╚══════════════════╝
               ╔══════════════════╗
    port 1 ════╝                  ╚════ port 4      through        light enters at port 1

Step 2 found the length from a fit through other lengths.  This step simulates the device itself: the
check of that fit, and the numbers a circuit model needs across the band.  A directional coupler splits
50:50 at one wavelength only; how fast the split moves away from it is the main result here.

    python coupler_fdtd.py
    python coupler_fdtd.py --mesh 0.01 --name coupler_fdtd_fine     # the mesh check

Output in 3_coupler_fdtd/:  directional_coupler.gds / .fsp, coupler_fdtd.npz / .txt; of a mesh check only <name>.txt
"""

from __future__ import annotations

import argparse
import os
import time

import numpy as np
from common import GAP, LAM, LAM_MAX, LAM_MIN, LENGTH, REPO, WIDTH, coupler_gds, require_process_file, solvers, step_dir
from coupling_length_fdtd import PORTS, build

OUT = step_dir("3_coupler_fdtd")
SCRATCH = REPO / "build" / "scratch"  # projects of mesh checks


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--accuracy", type=int, default=2, help="FDTD mesh accuracy")
    ap.add_argument("--mesh", type=float, default=0.02, help="mesh step over the gap (um); 0.01 for the mesh check")
    ap.add_argument("--time", type=float, default=3e-12, help="simulation time (s)")
    ap.add_argument("--threads", type=int, default=min(16, os.cpu_count() or 4))
    ap.add_argument("--job-manager", action="store_true", help="run through Lumerical's job manager instead of the CPU engine")
    ap.add_argument("--name", default="coupler_fdtd", help="name of the result files (use another one for a mesh check)")
    a = ap.parse_args()
    require_process_file()
    kept = a.name == "coupler_fdtd"  # the run of the tutorial; any other name is a check, of which only the summary stays
    SCRATCH.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    gds, x = coupler_gds(OUT / "directional_coupler.gds")
    res = solvers.solve_fdtd(
        OUT / "directional_coupler.fsp" if kept else SCRATCH / f"{a.name}.fsp",
        lambda app: build(app, gds, x, GAP, a.accuracy, a.mesh, 101, a.time),
        PORTS,
        field="field_xy",
        threads=a.threads,
        job_manager=a.job_manager,
    )
    minutes = (time.time() - t0) / 60
    lam = res["lam"]
    back, cross, through = (np.abs(res[f"S{k}"]) ** 2 for k in "134")
    total = cross + through
    fraction = cross / total
    p = solvers.at_wavelength(res)
    lam_half = (
        float(np.interp(0.5, fraction, lam)) if fraction[0] < 0.5 < fraction[-1] else float("nan")
    )  # the fraction rises with wavelength
    slope = float(np.polyfit(lam, fraction, 1)[0]) / 1000  # per nm
    band = (lam >= LAM_MIN) & (lam <= LAM_MAX)
    within = lam[np.abs(fraction - 0.5) <= 0.05]  # where the split stays between 45:55 and 55:45
    res.update(
        length=LENGTH,
        gap=GAP,
        minutes=minutes,
        mesh=a.mesh,
        accuracy=a.accuracy,
        lam_half=lam_half,
        x_straight=x["straight"],
        x_bend=x["bend"],
        port_y=x["port_y"],
    )
    lines = [
        f"Directional coupler as drawn: gap {GAP} um, straight section {LENGTH} um, W = {WIDTH} um (gsip_process.lbr); 3D FDTD, "
        f"mesh accuracy {a.accuracy}, {a.mesh * 1000:.0f} nm over the gap, {minutes:.1f} min",
        f"\nat {LAM} um:  cross |S31|^2 = {p['3']:.4f}   through |S41|^2 = {p['4']:.4f}   sum = {p['3'] + p['4']:.4f} "
        f"({-10 * np.log10(p['3'] + p['4']):.3f} dB)   cross fraction {p['3'] / (p['3'] + p['4']):.4f}",
        f"             back |S11|^2 = {p['1']:.1e} ({10 * np.log10(p['1']):.1f} dB)   into port 2 |S21|^2 = {p['2']:.1e} ({10 * np.log10(p['2']):.1f} dB)",
        f"\nthe split is 50:50 at {lam_half * 1000:.1f} nm and moves by {slope * 100:.2f} percentage points per nm",
        f"it stays between 45:55 and 55:45 from {within.min() * 1000:.0f} to {within.max() * 1000:.0f} nm"
        if within.size
        else "it never comes within 45:55",
        f"across {LAM_MIN}-{LAM_MAX} um:  loss {(-10 * np.log10(total[band])).min():.3f} to {(-10 * np.log10(total[band])).max():.3f} dB, "
        f"reflection at most {10 * np.log10(back[band].max()):.1f} dB",
        f"\n{'lambda (um)':>12} {'cross':>8} {'through':>8} {'fraction':>9} {'loss dB':>8} {'back dB':>8}",
    ]
    for i in np.linspace(0, len(lam) - 1, 11).round().astype(int):
        lines.append(
            f"{lam[i]:12.4f} {cross[i]:8.4f} {through[i]:8.4f} {fraction[i]:9.4f} {-10 * np.log10(total[i]):8.3f} {10 * np.log10(back[i]):8.1f}"
        )
    if kept:
        np.savez_compressed(OUT / f"{a.name}.npz", **res)
    (OUT / f"{a.name}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    solvers.clean_logs(OUT)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
