"""Step 2 - FDTD: the splitter as drawn: split, loss and reflection across the band, and the field.

Model: the splitter of devices/mmi1x2_builder.py with a straight lead at each port, written to GDS and
loaded into a Layer Builder with gsip_process.lbr.  The length of the multimode section is the one step 1
found.

                         ┌────────────┐◁══ port 2
        port 1 ══▷       │            │                 light enters at port 1
                         └────────────┘◁══ port 3

Step 1 used EME at one wavelength.  FDTD solves Maxwell's equations on the same layout without choosing
modes first, and gives the whole band in one run.  It is the check of step 1, and it gives the numbers a
circuit model needs: |S21|^2 and |S31|^2 (the split), their sum (the loss) and |S11|^2 (the reflection).

    python mmi_fdtd.py --preview        # layout, simulation region and ports -> figures/check_mmi_setup.png
    python mmi_fdtd.py --dry            # coarse mesh, a minute or two
    python mmi_fdtd.py
    python mmi_fdtd.py --mesh 0.01 --name mmi_fdtd_fine     # the mesh check: the body meshed twice as fine

Output in 2_mmi_fdtd/:  mmi1x2.gds / .fsp, mmi_fdtd.npz / .txt; of a mesh check only <name>.txt
"""

from __future__ import annotations

import argparse
import os
import time

import numpy as np
from common import (
    FIGURES,
    LAM,
    LAM_MAX,
    LAM_MIN,
    LENGTH_MMI,
    OUTPUT_Y,
    REPO,
    WIDTH_MMI,
    add_layer_builder,
    layout_gds,
    require_process_file,
    solvers,
    step_dir,
    t,
)

OUT = step_dir("2_mmi_fdtd")
SCRATCH = REPO / "build" / "scratch"  # projects of dry runs and mesh checks
Y_HALF = 3.0  # um: the FDTD region reaches this far on each side of the axis
PORT_INSET = 1.0  # um: a port sits this far from the end of the region
REGION_INSET = 1.0  # um: the region ends this far before the end of the leads, which run on into the PML
PORT_SPAN = 2 * OUTPUT_Y  # um: an output port reaches from the axis to as far beyond its waveguide


def region(x: dict) -> dict:
    """The FDTD region and the port positions (um) from the x positions of the layout."""
    x0, x1 = x["lead_in"] + REGION_INSET, x["lead_out"] - REGION_INSET
    return dict(x0=x0, x1=x1, port_in=x0 + PORT_INSET, port_out=x1 - PORT_INSET)


def build(app, gds, x: dict, mesh_accuracy: int, body_mesh: float | None, frequency_points: int, sim_time: float) -> None:
    r = region(x)
    app.switchtolayout()
    app.deleteall()
    add_layer_builder(app, gds, name="mmi1x2")
    solvers.add_fdtd(app, (r["x0"], r["x1"]), (-Y_HALF, Y_HALF), mesh_accuracy, sim_time)
    if body_mesh is not None:  # the multimode section and the wide ends of the tapers decide the image
        solvers.add_fdtd_mesh(
            app, "mesh_body", (x["taper_in"], x["taper_out"]), (-WIDTH_MMI / 2 - 0.1, WIDTH_MMI / 2 + 0.1), body_mesh
        )
    solvers.add_fdtd_port(app, "port 1", r["port_in"], 0.0, "Forward")
    solvers.add_fdtd_port(app, "port 2", r["port_out"], OUTPUT_Y, "Backward", y_span=PORT_SPAN)
    solvers.add_fdtd_port(app, "port 3", r["port_out"], -OUTPUT_Y, "Backward", y_span=PORT_SPAN)
    solvers.set_fdtd_source(app, "port 1", frequency_points)
    solvers.add_field_monitor(app, "field_xy", (r["x0"], r["x1"]), (-Y_HALF, Y_HALF))


def preview(gds, x: dict) -> None:
    """Draw the layout with the FDTD region and the ports, to check the set-up before running."""
    import klayout.db as kdb
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Rectangle

    r = region(x)
    layout = kdb.Layout()
    layout.read(str(gds))
    fig, ax = plt.subplots(figsize=(10, 3.2))
    shapes = kdb.Region(layout.top_cell().begin_shapes_rec(layout.layer(*tuple(t.WG)))).merged()
    for i, poly in enumerate(shapes.each()):
        pts = [(p.x * layout.dbu, p.y * layout.dbu) for p in poly.each_point_hull()]
        ax.add_patch(Polygon(pts, fc=t.LAYER_COLORS["WG"], ec="none", label="WG (220 nm silicon)" if i == 0 else None))
    ax.add_patch(Rectangle((r["x0"], -Y_HALF), r["x1"] - r["x0"], 2 * Y_HALF, fill=False, ls="--", ec="k", label="FDTD region"))
    for name, px, py, span in (("port 1", r["port_in"], 0.0, solvers.PORT_Y_SPAN), ("port 2", r["port_out"], OUTPUT_Y, PORT_SPAN),
                               ("port 3", r["port_out"], -OUTPUT_Y, PORT_SPAN)):  # fmt: skip
        ax.plot([px, px], [py - span / 2, py + span / 2], color="C2", lw=2)
        ax.text(
            px,
            py + (span / 2 + 0.15) * (1 if py >= 0 else -1),
            name,
            color="C2",
            ha="center",
            va="bottom" if py >= 0 else "top",
            fontsize=8,
        )
    ax.set_xlim(x["lead_in"] - 0.5, x["lead_out"] + 0.5)
    ax.set_ylim(-Y_HALF - 0.8, Y_HALF + 0.8)
    ax.set_aspect("equal")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.set_title(f"1x2 MMI: multimode section {WIDTH_MMI} x {LENGTH_MMI} um")
    ax.legend(loc="lower center", ncol=2, fontsize=8)
    fig.tight_layout()
    FIGURES.mkdir(parents=True, exist_ok=True)
    path = FIGURES / "check_mmi_setup.png"
    fig.savefig(path, dpi=130)
    print("preview ->", path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--preview", action="store_true", help="only draw the layout and the simulation region")
    ap.add_argument("--dry", action="store_true", help="coarse mesh, no mesh override: a quick test of the set-up")
    ap.add_argument("--accuracy", type=int, default=2, help="FDTD mesh accuracy")
    ap.add_argument("--mesh", type=float, default=0.02, help="mesh step over the multimode section (um); 0.01 for the mesh check")
    ap.add_argument("--time", type=float, default=3e-12, help="simulation time (s)")
    ap.add_argument("--threads", type=int, default=min(16, os.cpu_count() or 4))
    ap.add_argument("--job-manager", action="store_true", help="run through Lumerical's job manager instead of the CPU engine")
    ap.add_argument("--name", default="mmi_fdtd", help="name of the result files (use another one for a mesh check)")
    a = ap.parse_args()
    gds, x = layout_gds(OUT / "mmi1x2.gds")
    if a.preview:
        preview(gds, x)
        return
    require_process_file()
    t0 = time.time()
    accuracy, body_mesh, points = (1, None, 21) if a.dry else (a.accuracy, a.mesh, 101)
    name = "dry" if a.dry else a.name
    kept = name == "mmi_fdtd"  # the run of the tutorial; any other name is a check, of which only the summary stays
    SCRATCH.mkdir(parents=True, exist_ok=True)
    res = solvers.solve_fdtd(
        OUT / "mmi1x2.fsp" if kept else SCRATCH / f"{name}.fsp",
        lambda app: build(app, gds, x, accuracy, body_mesh, points, a.time),
        ["port 1", "port 2", "port 3"],
        field="field_xy",
        threads=a.threads,
        job_manager=a.job_manager,
    )
    minutes = (time.time() - t0) / 60
    lam = res["lam"]
    T2, T3, R = np.abs(res["S2"]) ** 2, np.abs(res["S3"]) ** 2, np.abs(res["S1"]) ** 2
    total = T2 + T3
    p = solvers.at_wavelength(res)
    loss = -10 * np.log10(total)
    band = (lam >= LAM_MIN) & (lam <= LAM_MAX)
    res.update(
        length_mmi=LENGTH_MMI, width_mmi=WIDTH_MMI, output_y=OUTPUT_Y, minutes=minutes, mesh=body_mesh or 0.0, accuracy=accuracy
    )
    res.update({f"x_{k}": v for k, v in x.items()})
    lines = [
        f"1x2 MMI as drawn: multimode section {WIDTH_MMI} x {LENGTH_MMI} um (gsip_process.lbr); 3D FDTD, mesh accuracy {accuracy}, "
        + (f"{body_mesh * 1000:.0f} nm over the multimode section" if body_mesh else "no mesh override")
        + f", {minutes:.1f} min",
        f"\nat {LAM} um:  |S21|^2 = {p['2']:.4f}   |S31|^2 = {p['3']:.4f}   sum = {p['2'] + p['3']:.4f}  "
        f"({-10 * np.log10(p['2'] + p['3']):.3f} dB)   |S11|^2 = {p['1']:.1e} ({10 * np.log10(p['1']):.1f} dB)",
        f"imbalance at {LAM} um: {10 * np.log10(p['2'] / p['3']):+.4f} dB between the two outputs",
        f"\nacross {LAM_MIN}-{LAM_MAX} um:  loss {loss[band].min():.3f} to {loss[band].max():.3f} dB, "
        f"reflection at most {10 * np.log10(R[band].max()):.1f} dB",
        f"\n{'lambda (um)':>12} {'|S21|^2':>9} {'|S31|^2':>9} {'loss dB':>8} {'|S11|^2 dB':>11}",
    ]
    for i in np.linspace(0, len(lam) - 1, 11).round().astype(int):
        lines.append(f"{lam[i]:12.4f} {T2[i]:9.4f} {T3[i]:9.4f} {loss[i]:8.3f} {10 * np.log10(R[i]):11.1f}")
    if kept:
        np.savez_compressed(OUT / f"{name}.npz", **res)
    ((SCRATCH if a.dry else OUT) / f"{name}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    solvers.clean_logs(OUT)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
