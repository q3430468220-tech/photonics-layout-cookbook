"""Step 2 - FDTD: how long must the straight section be for a 50:50 split?  A length sweep, and a fit.

Model: the coupler of devices/directional_coupler_builder.py with a straight lead at each port, written
to GDS for several lengths of the straight section and loaded into a Layer Builder with gsip_process.lbr.

    port 2 ════╗                  ╔════ port 3      cross
               ╚══════════════════╝
               ╔══════════════════╗
    port 1 ════╝                  ╚════ port 4      through        light enters at port 1

Step 1 gives the cross-over length of the straight section alone.  The S-bends couple too: where they
approach the straight section the two cores are already close.  FDTD on the whole layout includes that.
The fraction that crosses follows

    cross / (cross + through) = sin^2( pi / 2 * (L + L_bends) / L_pi )

so a few lengths L are enough to find both L_pi and L_bends, the length of straight coupler that the
bends are worth.  The 50:50 length is then  L_pi / 2 - L_bends.

    python coupling_length_fdtd.py --preview     # layout, simulation region and ports -> figures/check_coupler_setup.png
    python coupling_length_fdtd.py --dry         # coarse mesh, one length
    python coupling_length_fdtd.py
    python coupling_length_fdtd.py --lengths 0 10 20

Output in 2_coupling_length/:  coupling_length.npz / .txt, sweep.fsp (the project of the last length)
"""

from __future__ import annotations

import argparse
import os
import time

import numpy as np
from common import FIGURES, GAP, LAM, REPO, WIDTH, add_layer_builder, coupler_gds, require_process_file, solvers, step_dir, t

OUT = step_dir("2_coupling_length")
SUPERMODES = OUT.parent / "1_supermodes" / "supermodes.npz"
SCRATCH = REPO / "build" / "scratch"  # layouts of the sweep, overwritten for every length
Y_MARGIN = 2.0  # um: the FDTD region reaches this far beyond the port waveguides
PORT_INSET = 1.0  # um: a port sits this far from the end of the region
REGION_INSET = 1.0  # um: the region ends this far before the end of the leads, which run on into the PML
PORTS = ["port 1", "port 2", "port 3", "port 4"]


def region(x: dict) -> dict:
    """The FDTD region and the port positions (um) from the positions of the layout."""
    x_half = x["lead"] - REGION_INSET
    return dict(x_half=x_half, y_half=x["port_y"] + Y_MARGIN, x_port=x_half - PORT_INSET)


def build(
    app, gds, x: dict, gap: float, mesh_accuracy: int, gap_mesh: float | None, frequency_points: int, sim_time: float
) -> None:
    r = region(x)
    app.switchtolayout()
    app.deleteall()
    add_layer_builder(app, gds, name="coupler")
    solvers.add_fdtd(app, (-r["x_half"], r["x_half"]), (-r["y_half"], r["y_half"]), mesh_accuracy, sim_time)
    if gap_mesh is not None:  # the gap sets the coupling: resolve it along the straight section and into the bends
        reach = WIDTH + gap / 2 + 0.3
        solvers.add_fdtd_mesh(app, "mesh_gap", (-x["straight"] - 4.0, x["straight"] + 4.0), (-reach, reach), gap_mesh)
    solvers.add_fdtd_port(app, "port 1", -r["x_port"], -x["port_y"], "Forward")
    solvers.add_fdtd_port(app, "port 2", -r["x_port"], x["port_y"], "Forward")
    solvers.add_fdtd_port(app, "port 3", r["x_port"], x["port_y"], "Backward")
    solvers.add_fdtd_port(app, "port 4", r["x_port"], -x["port_y"], "Backward")
    solvers.set_fdtd_source(app, "port 1", frequency_points)
    solvers.add_field_monitor(app, "field_xy", (-r["x_half"], r["x_half"]), (-r["y_half"], r["y_half"]))


def crossing(lengths: np.ndarray, l_pi: float, l_bends: float) -> np.ndarray:
    """Fraction of the transmitted power that leaves through the cross port."""
    return np.sin(np.pi / 2 * (lengths + l_bends) / l_pi) ** 2


def fit(lengths: np.ndarray, fraction: np.ndarray, l_pi_guess: float) -> tuple[float, float]:
    from scipy.optimize import curve_fit

    (l_pi, l_bends), _ = curve_fit(crossing, lengths, fraction, p0=(l_pi_guess, 3.0))
    return float(l_pi), float(l_bends)


def preview(gds, x: dict, length: float) -> None:
    """Draw the layout with the FDTD region and the ports, to check the set-up before running."""
    import klayout.db as kdb
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Rectangle

    r = region(x)
    layout = kdb.Layout()
    layout.read(str(gds))
    fig, ax = plt.subplots(figsize=(10, 3.4))
    shapes = kdb.Region(layout.top_cell().begin_shapes_rec(layout.layer(*tuple(t.WG)))).merged()
    for i, poly in enumerate(shapes.each()):
        pts = [(p.x * layout.dbu, p.y * layout.dbu) for p in poly.each_point_hull()]
        ax.add_patch(Polygon(pts, fc=t.LAYER_COLORS["WG"], ec="none", label="WG (220 nm silicon)" if i == 0 else None))
    ax.add_patch(
        Rectangle(
            (-r["x_half"], -r["y_half"]), 2 * r["x_half"], 2 * r["y_half"], fill=False, ls="--", ec="k", label="FDTD region"
        )
    )
    for name, sx, sy in (("port 1", -1, -1), ("port 2", -1, 1), ("port 3", 1, 1), ("port 4", 1, -1)):
        px, py = sx * r["x_port"], sy * x["port_y"]
        ax.plot([px, px], [py - solvers.PORT_Y_SPAN / 2, py + solvers.PORT_Y_SPAN / 2], color="C2", lw=2)
        ax.text(px + sx * 0.3, py, name, color="C2", ha="left" if sx > 0 else "right", va="center", fontsize=8)
    ax.set_xlim(-x["lead"] - 3.5, x["lead"] + 3.5)
    ax.set_ylim(-r["y_half"] - 0.8, r["y_half"] + 0.8)
    ax.set_aspect("equal")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.set_title(f"Directional coupler: gap {GAP} um, straight section {length} um")
    ax.legend(loc="lower center", ncol=2, fontsize=8)
    fig.tight_layout()
    FIGURES.mkdir(parents=True, exist_ok=True)
    path = FIGURES / "check_coupler_setup.png"
    fig.savefig(path, dpi=130)
    print("preview ->", path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--lengths", type=float, nargs="*", default=[0.0, 6.0, 12.0, 18.0], help="lengths of the straight section (um)"
    )
    ap.add_argument("--preview", action="store_true", help="only draw the layout and the simulation region")
    ap.add_argument("--dry", action="store_true", help="coarse mesh, first length only: a quick test of the set-up")
    ap.add_argument("--accuracy", type=int, default=2, help="FDTD mesh accuracy")
    ap.add_argument("--mesh", type=float, default=0.02, help="mesh step over the gap (um); 0.01 for the mesh check")
    ap.add_argument("--time", type=float, default=3e-12, help="simulation time (s)")
    ap.add_argument("--threads", type=int, default=min(16, os.cpu_count() or 4))
    ap.add_argument("--job-manager", action="store_true", help="run through Lumerical's job manager instead of the CPU engine")
    a = ap.parse_args()
    if a.preview:
        length = a.lengths[len(a.lengths) // 2]
        gds, x = coupler_gds(SCRATCH / "coupler_length_sweep.gds", length)
        preview(gds, x, length)
        return
    require_process_file()
    accuracy, gap_mesh, points = (1, None, 21) if a.dry else (a.accuracy, a.mesh, 101)
    lengths = a.lengths[:1] if a.dry else sorted(a.lengths)
    runs, t0 = [], time.time()
    for length in lengths:
        t1 = time.time()
        gds, x = coupler_gds(SCRATCH / "coupler_length_sweep.gds", length, cellname=f"coupler_L{round(length * 1000)}")
        res = solvers.solve_fdtd(
            OUT / "sweep.fsp",
            lambda app, gds=gds, x=x: build(app, gds, x, GAP, accuracy, gap_mesh, points, a.time),
            PORTS,
            threads=a.threads,
            job_manager=a.job_manager,
        )
        p = solvers.at_wavelength(res)
        runs.append(
            dict(
                length=length,
                minutes=(time.time() - t1) / 60,
                lam=res["lam"],
                **{f"S{k}": res[f"S{k}"] for k in "1234"},
                **{f"p{k}": v for k, v in p.items()},
            )
        )
        print(
            f"L = {length:5.1f} um: cross {p['3']:.4f}  through {p['4']:.4f}  sum {p['3'] + p['4']:.4f}  back {p['1']:.1e}  "
            f"({runs[-1]['minutes']:.1f} min)",
            flush=True,
        )
    solvers.clean_logs(OUT)
    if a.dry:
        return

    L = np.array([r["length"] for r in runs])
    cross, through = np.array([r["p3"] for r in runs]), np.array([r["p4"] for r in runs])
    fraction = cross / (cross + through)
    with np.load(SUPERMODES) as kept:
        l_pi_modes = float(kept["l_pi"])
    l_pi, l_bends = fit(L, fraction, l_pi_modes)
    l_half = l_pi / 2 - l_bends
    residual = float(np.max(np.abs(crossing(L, l_pi, l_bends) - fraction)))
    out = dict(gap=GAP, lam=LAM, lengths=L, cross=cross, through=through, fraction=fraction, back=np.array([r["p1"] for r in runs]),
               isolation=np.array([r["p2"] for r in runs]), l_pi=l_pi, l_bends=l_bends, l_half=l_half, l_pi_supermodes=l_pi_modes,
               sweep_lam=runs[0]["lam"], cross_lam=np.array([np.abs(r["S3"]) ** 2 for r in runs]),
               through_lam=np.array([np.abs(r["S4"]) ** 2 for r in runs]), minutes=np.array([r["minutes"] for r in runs]))  # fmt: skip
    lines = [
        f"Directional coupler, gap {GAP} um, W = {WIDTH} um, strip (gsip_process.lbr), {LAM} um; 3D FDTD, mesh accuracy {accuracy}, "
        f"{gap_mesh * 1000:.0f} nm over the gap; {(time.time() - t0) / 60:.0f} min for {len(runs)} lengths",
        f"\n{'L (um)':>7} {'cross':>8} {'through':>8} {'sum':>8} {'loss dB':>8} {'cross fraction':>15} {'fit':>8} {'back':>9} {'minutes':>8}",
    ]
    for r, fr, model in zip(runs, fraction, crossing(L, l_pi, l_bends), strict=True):
        total = r["p3"] + r["p4"]
        lines.append(
            f"{r['length']:7.1f} {r['p3']:8.4f} {r['p4']:8.4f} {total:8.4f} {-10 * np.log10(total):8.3f} {fr:15.4f} {model:8.4f} {r['p1']:9.1e} {r['minutes']:8.1f}"
        )
    lines += [
        f"\nfit of the cross fraction: L_pi = {l_pi:.2f} um, the S-bends are worth L_bends = {l_bends:.2f} um of straight coupler "
        f"(largest deviation from the points {residual:.4f})",
        f"step 1, supermodes of the cross-section: L_pi = {l_pi_modes:.2f} um ({(l_pi / l_pi_modes - 1) * 100:+.1f} % in FDTD)",
        f"50:50 at {LAM} um:  L = L_pi / 2 - L_bends = {l_half:.2f} um",
    ]
    np.savez_compressed(OUT / "coupling_length.npz", **out)
    (OUT / "coupling_length.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
