"""Step 1 - FDTD: power coupling between the bus and the ring, as a function of the gap.

Only the coupling region is simulated.  The ring arc is continued by reverse bends so that it
leaves the window parallel to the bus, and all four ports are normal to x:

    port 3 ______                               ______ port 4      ring arm (radius R near the bus)
                 `--.._                   _..--'
                       `--..__     __..--'
    port 1 ====================`==='==================== port 2      bus

Light enters at port 1:  t^2 = |S21|^2 stays in the bus,  kappa^2 = |S41|^2 crosses into the ring.

Model: the coupler is drawn with the PDK layers, written to GDS, and loaded into a Layer Builder
together with cornerstone_process.lbr.  The slab covers the whole window, as it does in the device,
where the slabs of ring and bus merge.

    python coupling_coefficient_fdtd.py --preview          # layout and simulation window -> plots/
    python coupling_coefficient_fdtd.py --dry              # coarse mesh, one gap, a few minutes
    python coupling_coefficient_fdtd.py                    # gaps 0.20 0.30 0.40 0.50 um
    python coupling_coefficient_fdtd.py --gaps 0.22 0.28

Output in 1_coupling_coefficient/:  coupler_gap<nm>nm.gds / .fsp / .npz, coupling_vs_gap.csv / .txt
"""

from __future__ import annotations

import argparse
import math
import os
import subprocess
import time
from pathlib import Path

import numpy as np
from common import (
    LAM,
    LAM_MAX,
    LAM_MIN,
    RADIUS,
    T_SI,
    WIDTH,
    add_layer_builder,
    import_lumapi,
    lumerical_root,
    plot_dir,
    require_process_file,
    step_dir,
    strip,
    t,
    um,
)

OUT = step_dir("1_coupling_coefficient")

ARM_ANGLE = 18.0  # deg: half-angle of the ring arc kept in the window; the reverse bends undo it
PORT_STRAIGHT = 2.5  # um of straight waveguide before each port
MARGIN = 3.0  # um the layout extends beyond the FDTD region, so that waveguides run through the PML
PORT_Y_SPAN, PORT_Z_SPAN = 2.8, 1.6
Y_BELOW, Y_ABOVE = 2.2, 2.2  # FDTD region below the bus / above the arm
Z_MIN, Z_MAX = -1.0, 1.2  # inside the BOX (2 um) and the top cladding (ends at 1.22 um)


def geometry(gap: float, radius: float = RADIUS) -> dict:
    """Window and port positions (um) for a given gap."""
    phi = math.radians(ARM_ANGLE)
    rise = 2 * radius * (1 - math.cos(phi))  # the arm ends this far above its lowest point
    reach = 2 * radius * math.sin(phi)  # horizontal distance from the coupling point to the arm straight
    arm = WIDTH + gap + rise  # arm straight above the bus
    half = (arm + Y_ABOVE + Y_BELOW) / 2  # the window is centred on y = 0, like the Layer Builder
    y_bus = Y_BELOW - half
    x_half = reach + PORT_STRAIGHT + 1.0
    return dict(
        gap=gap,
        radius=radius,
        y_bus=y_bus,
        y_ring=y_bus + WIDTH + gap,
        y_arm=y_bus + arm,
        reach=reach,
        x_half=x_half,
        x_port=x_half - 1.0,
        y_min=-half,
        y_max=half,
    )


def write_gds(gap: float, radius: float = RADIUS, with_bus: bool = True, name: str | None = None) -> tuple[Path, dict]:
    import gdsfactory as gf

    g = geometry(gap, radius)
    x0, x1 = -g["x_half"] - MARGIN, g["x_half"] + MARGIN
    y0, y1 = g["y_min"] - MARGIN, g["y_max"] + MARGIN
    c = gf.Component()
    c.add_polygon(strip(x0, x1, y0, y1), layer=t.SLAB)
    if with_bus:
        c.add_polygon(strip(x0, x1, g["y_bus"] - WIDTH / 2, g["y_bus"] + WIDTH / 2), layer=t.CORE)
    ext = x1 - g["reach"]
    arm = (
        gf.path.straight(ext)
        + gf.path.arc(radius=radius, angle=-ARM_ANGLE)
        + gf.path.arc(radius=radius, angle=2 * ARM_ANGLE)
        + gf.path.arc(radius=radius, angle=-ARM_ANGLE)
        + gf.path.straight(ext)
    )
    ref = c << gf.path.extrude(arm, layer=t.CORE, width=WIDTH)
    ref.dmove((x0, g["y_arm"]))
    name = name or f"coupler_gap{round(gap * 1000):03d}nm"
    g.update(x0=x0, x1=x1, y0=y0, y1=y1)
    return t.write_gds_for_lumerical(c, OUT / f"{name}.gds", cellname=name), g


def _port(f, name: str, direction: str, x: float, y: float) -> None:
    f.addport()
    f.set("name", name)
    f.set("injection axis", "x-axis")
    f.set("direction", direction)
    f.set("x", x * um)
    f.set("y", y * um)
    f.set("y span", PORT_Y_SPAN * um)
    f.set("z", T_SI / 2 * um)
    f.set("z span", PORT_Z_SPAN * um)
    f.set("mode selection", "fundamental TE mode")


def build(
    f, gds: Path, g: dict, *, with_bus: bool, source_port: str, mesh_accuracy: int, fine: bool, fpts: int, sim_time: float
) -> None:
    f.switchtolayout()
    f.deleteall()
    add_layer_builder(f, gds, g["x1"] - g["x0"], g["y1"] - g["y0"], name="coupler")

    f.addfdtd()
    f.set("dimension", "3D")
    f.set("x min", -g["x_half"] * um)
    f.set("x max", g["x_half"] * um)
    f.set("y min", g["y_min"] * um)
    f.set("y max", g["y_max"] * um)
    f.set("z min", Z_MIN * um)
    f.set("z max", Z_MAX * um)
    f.set("mesh accuracy", mesh_accuracy)
    f.set("simulation time", sim_time)
    f.set("auto shutoff min", 1e-5)
    f.setglobalsource("wavelength start", LAM_MIN * um)
    f.setglobalsource("wavelength stop", LAM_MAX * um)

    if fine:  # resolve the gap: it sets the coupling
        f.addmesh()
        f.set("name", "mesh_gap")
        f.set("x", 0)
        f.set("x span", 1.3 * g["reach"] * um)
        f.set("y min", (g["y_bus"] - WIDTH / 2 - 0.1) * um)
        f.set("y max", (g["y_ring"] + WIDTH / 2 + 0.6) * um)
        f.set("z min", -0.04 * um)
        f.set("z max", (T_SI + 0.04) * um)
        f.set("override x mesh", 0)
        f.set("dy", 0.02 * um)
        f.set("dz", 0.02 * um)

    if with_bus:
        _port(f, "port 1", "Forward", -g["x_port"], g["y_bus"])
        _port(f, "port 2", "Backward", g["x_port"], g["y_bus"])
    _port(f, "port 3", "Forward", -g["x_port"], g["y_arm"])
    _port(f, "port 4", "Backward", g["x_port"], g["y_arm"])
    f.select("FDTD::ports")
    f.set("source port", source_port)
    f.set("monitor frequency points", fpts)

    f.addpower()
    f.set("name", "field_xy")
    f.set("monitor type", "2D Z-normal")
    f.set("x", 0)
    f.set("x span", 2 * g["x_half"] * um)
    f.set("y min", g["y_min"] * um)
    f.set("y max", g["y_max"] * um)
    f.set("z", T_SI / 2 * um)
    f.set("override global monitor settings", 1)
    f.set("use source limits", 0)
    f.set("frequency points", 1)
    f.set("wavelength center", LAM * um)
    for comp in ("Hx", "Hy", "Hz", "Px", "Py", "Pz"):
        f.set(f"output {comp}", 0)


def run_engine(f, fsp: Path, job_manager: bool, threads: int) -> None:
    """Run the saved project.

    By default the CPU engine is started directly: on some machines the job manager picks a GPU
    resource or fails silently.  ``--job-manager`` uses Lumerical's own resource configuration.
    """
    engine = lumerical_root() / "bin" / ("fdtd-engine.exe" if os.name == "nt" else "fdtd-engine")
    if job_manager or not engine.exists():
        f.run()
        return
    log = fsp.with_name(fsp.stem + "_engine.out")
    with open(log, "w", encoding="utf-8", errors="replace") as fh:
        proc = subprocess.run(
            [str(engine), "-t", str(threads), str(fsp)], stdout=fh, stderr=subprocess.STDOUT, cwd=str(fsp.parent)
        )
    if proc.returncode != 0:
        tail = "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-8:])
        raise RuntimeError(f"fdtd-engine exited with code {proc.returncode}, see {log}\n{tail}")
    log.unlink(missing_ok=True)


def extract(f, ports: list[str]) -> dict:
    out = {}
    for p in ports:
        s = f.getresult(f"FDTD::ports::{p}", "S")
        out["lam"] = np.squeeze(s["lambda"]) / um
        out[f"S{p[-1]}"] = np.squeeze(s["S"])
    e = f.getresult("field_xy", "E")
    out["field_x"] = np.squeeze(e["x"]) / um
    out["field_y"] = np.squeeze(e["y"]) / um
    out["field_E"] = np.linalg.norm(np.squeeze(e["E"]), axis=-1).astype(np.float32)
    return out


def run_case(
    name: str,
    gap: float,
    *,
    radius: float,
    with_bus: bool = True,
    keep_results: bool = False,
    job_manager: bool = False,
    threads: int = 8,
    **mesh,
) -> dict:
    lumapi = import_lumapi()
    t0 = time.time()
    gds, g = write_gds(gap, radius, with_bus, name)
    fsp = OUT / f"{name}.fsp"
    source = "port 1" if with_bus else "port 3"
    ports = ["port 1", "port 2", "port 3", "port 4"] if with_bus else ["port 3", "port 4"]
    with lumapi.FDTD(hide=True) as f:
        build(f, gds, g, with_bus=with_bus, source_port=source, **mesh)
        f.save(str(fsp))
        if job_manager:
            run_engine(f, fsp, True, threads)
            res = extract(f, ports)
            if not keep_results:
                f.switchtolayout()
                f.save(str(fsp))
    if not job_manager:
        run_engine(None, fsp, False, threads)
        with lumapi.FDTD(filename=str(fsp), hide=True) as f:
            if int(f.layoutmode()) == 1:
                raise RuntimeError(f"{name}: the engine finished but the file holds no results, see {fsp.stem}_p0.log")
            res = extract(f, ports)
            if not keep_results:  # the numbers are in the .npz; a project with fields is hundreds of MB
                f.switchtolayout()
                f.save(str(fsp))
    res.update(gap=gap, radius=radius, name=name, minutes=(time.time() - t0) / 60, with_bus=with_bus)
    np.savez(OUT / f"{name}.npz", **res)
    return res


def at_design_wavelength(res: dict) -> dict:
    k = int(np.argmin(np.abs(res["lam"] - LAM)))
    return {key[1]: float(np.abs(res[key][k]) ** 2) for key in ("S1", "S2", "S3", "S4") if key in res}


def summarize(results: list[dict]) -> None:
    """Fit kappa^2(gap) = A exp(-gap / g0) and write the table that step 6 reads."""
    rows = []
    for res in results:
        p = at_design_wavelength(res)
        rows.append((float(res["gap"]), p["4"], p["2"], p["1"], p["3"], sum(p.values()), float(res["minutes"])))
    rows.sort()
    gaps, kappa2 = np.array([r[0] for r in rows]), np.array([r[1] for r in rows])
    lines = [
        f"Coupling region, R = {results[0]['radius']} um, W = {WIDTH} um, rib waveguide, lambda = {LAM} um",
        f"{'gap (um)':>9} {'kappa^2 |S41|^2':>16} {'t^2 |S21|^2':>12} {'|S11|^2':>9} {'|S31|^2':>9} {'sum':>7} {'minutes':>8}",
    ]
    lines += [f"{g:9.3f} {k2:16.5f} {t2:12.5f} {r1:9.2e} {r3:9.2e} {s:7.4f} {m:8.1f}" for g, k2, t2, r1, r3, s, m in rows]
    if len(rows) > 1:
        slope, intercept = np.polyfit(gaps, np.log(kappa2), 1)
        lines.append(f"\nfit: kappa^2 = {math.exp(intercept):.4f} * exp(-gap / {-1000 / slope:.1f} nm)")
    lines.append("sum < 1 is the loss of the coupler and of the arm's reverse bends inside the window.")
    (OUT / "coupling_vs_gap.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with open(OUT / "coupling_vs_gap.csv", "w", encoding="utf-8") as fh:
        fh.write("gap_um,kappa2_S41,t2_S21,r_S11,r_S31,sum\n")
        fh.writelines(f"{g},{k2},{t2},{r1},{r3},{s}\n" for g, k2, t2, r1, r3, s, _ in rows)
    print("\n".join(lines))


def preview(gap: float, radius: float) -> None:
    """Draw the layout with the FDTD region and the ports, to check the set-up before running."""
    import klayout.db as kdb
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Rectangle

    gds, g = write_gds(gap, radius)
    layout = kdb.Layout()
    layout.read(str(gds))
    cell = layout.top_cell()
    fig, ax = plt.subplots(figsize=(11, 4))
    for layer, color, label in ((t.SLAB, "0.88", "Si_Etch3_LF (100 nm slab)"), (t.CORE, "#7b68ee", "Si_Etch2_LF (220 nm core)")):
        region = kdb.Region(cell.begin_shapes_rec(layout.layer(*tuple(layer)))).merged()
        for i, poly in enumerate(region.each()):
            pts = [(p.x * layout.dbu, p.y * layout.dbu) for p in poly.each_point_hull()]
            ax.add_patch(Polygon(pts, fc=color, ec="none", label=label if i == 0 else None))
    ax.add_patch(
        Rectangle(
            (-g["x_half"], g["y_min"]), 2 * g["x_half"], g["y_max"] - g["y_min"], fill=False, ls="--", ec="k", label="FDTD region"
        )
    )
    for name, x, y in (
        ("port 1", -g["x_port"], g["y_bus"]),
        ("port 2", g["x_port"], g["y_bus"]),
        ("port 3", -g["x_port"], g["y_arm"]),
        ("port 4", g["x_port"], g["y_arm"]),
    ):
        ax.plot([x, x], [y - PORT_Y_SPAN / 2, y + PORT_Y_SPAN / 2], color="C2", lw=2)
        ax.text(x, y + PORT_Y_SPAN / 2 + 0.15, name, color="C2", ha="center", fontsize=8)
    ax.set_xlim(g["x0"], g["x1"])
    ax.set_ylim(g["y0"], g["y1"])
    ax.set_aspect("equal")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.set_title(f"Coupling region: R = {radius} um, W = {WIDTH} um, gap = {gap} um")
    ax.legend(loc="lower center", ncol=3, fontsize=8)
    fig.tight_layout()
    path = plot_dir("1_coupling_coefficient") / "coupler_geometry.png"
    fig.savefig(path, dpi=130)
    print("preview ->", path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gaps", type=float, nargs="*", default=[0.20, 0.30, 0.40, 0.50], help="gaps in um")
    ap.add_argument("--radius", type=float, default=RADIUS)
    ap.add_argument("--dry", action="store_true", help="coarse mesh, first gap only")
    ap.add_argument("--preview", action="store_true", help="only draw the layout and the simulation window")
    ap.add_argument("--accuracy", type=int, default=2, help="FDTD mesh accuracy")
    ap.add_argument("--time", type=float, default=2.5e-12, help="simulation time (s)")
    ap.add_argument("--threads", type=int, default=min(16, os.cpu_count() or 4))
    ap.add_argument("--job-manager", action="store_true", help="run through Lumerical's job manager instead of the CPU engine")
    ap.add_argument("--keep-results", action="store_true", help="keep the fields in the .fsp files")
    a = ap.parse_args()
    if a.preview:
        preview(a.gaps[0], a.radius)
        return
    require_process_file()
    mesh = dict(mesh_accuracy=a.accuracy, fine=True, fpts=101, sim_time=a.time)
    prefix, gaps = "coupler", a.gaps
    if a.dry:
        mesh.update(mesh_accuracy=1, fine=False, fpts=21)
        prefix, gaps = "dry", a.gaps[:1]
    results = []
    for gap in gaps:
        name = f"{prefix}_gap{round(gap * 1000):03d}nm"
        print(f"==== {name} started {time.strftime('%H:%M:%S')}", flush=True)
        res = run_case(
            name, gap, radius=a.radius, keep_results=a.keep_results, job_manager=a.job_manager, threads=a.threads, **mesh
        )
        p = at_design_wavelength(res)
        print(
            f"     kappa^2 = {p['4']:.5f}, t^2 = {p['2']:.5f}, sum = {sum(p.values()):.4f}  ({res['minutes']:.1f} min)",
            flush=True,
        )
        results.append(res)
    if not a.dry:
        summarize(results)


if __name__ == "__main__":
    main()
