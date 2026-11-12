"""Step 1 - FDTD: power coupling between the bus and the ring, as a function of the gap.

Only the coupling region is simulated.  Around the coupling point the arm has the radius of the ring;
further out it bends back, so that it leaves the window parallel to the bus and all four ports are
normal to x:

    port 3 ______                               ______ port 4      ring arm (radius R near the bus)
                 `--.._                   _..--'
                       `--..__     __..--'
    port 1 ====================`==='==================== port 2      bus

Light enters at port 1:  t^2 = |S21|^2 stays in the bus,  kappa^2 = |S41|^2 crosses into the ring.

The arm's own loss is removed with a reference run without the bus: light sent from port 3 to port 4
passes the whole arm, light coupled from the bus only its second half, so  kappa^2 = |S41|^2 / sqrt(T_arm).
The arm loss is not bend radiation (at this radius step 2 finds none).  It is mode mismatch where the
curvature of the S-bend changes: at the two reversals and at the joins to the straight ends.

Model: the coupler is drawn with the PDK layers, written to GDS, and loaded into a Layer Builder
together with gsip_process.lbr.  The slab covers the whole window.  In the device it covers the ring and
the bus, and the two slabs merge in the coupling region.  The straight ends of the S-bend exist in the
simulation only; the reference run removes their loss.

    python coupling_coefficient_fdtd.py --preview          # layout and simulation window -> figures/
    python coupling_coefficient_fdtd.py --dry              # coarse mesh, one gap, a few minutes
    python coupling_coefficient_fdtd.py                    # reference + gaps 0.20 0.30 0.40 0.50 um
    python coupling_coefficient_fdtd.py --gaps 0.22 0.28
    python coupling_coefficient_fdtd.py --summary-only     # table from the kept .npz files, no Lumerical

How well is the mesh converged?  One gap was run three ways (raw |S41|^2 at 1550 nm, gap 0.40 um):
    20 nm over the coupler (the default)                0.010989      5.6 min
    the same step, with the mesh boxes cut at the silicon surfaces   0.010949   -0.4 %
    10 nm over the coupler (--gap-mesh 0.01)            0.010774      -2.0 %, 18.6 min
kappa^2 is therefore known to about 2 %, which is 2 nm in the gap of critical coupling.  The tables of
this folder are from the default mesh.  Running all gaps with --gap-mesh 0.01 is the exercise of this step.

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
    FIGURES,
    LAM,
    LAM_MAX,
    LAM_MIN,
    RADIUS,
    T_SI,
    WIDTH,
    add_layer_builder,
    import_lumapi,
    lumerical_root,
    require_process_file,
    step_dir,
    strip,
    t,
    um,
)

OUT = step_dir("1_coupling_coefficient")

ARM_ANGLE = 35.0  # deg: half-angle of the ring arc kept in the window; the reverse bends undo it
PORT_STRAIGHT = 2.5  # um of straight waveguide before each port
MARGIN = 3.0  # um the layout extends beyond the FDTD region, so that waveguides run through the PML
PORT_Y_SPAN, PORT_Z_SPAN = 2.8, 1.6
Y_BELOW, Y_ABOVE = 2.2, 2.2  # FDTD region below the bus / above the arm
Z_MIN, Z_MAX = -1.0, 1.0  # inside the 2 um BOX and below metal 1


def geometry(gap: float, radius: float = RADIUS) -> dict:
    """Window and port positions (um) for a given gap.  The window is centred on the origin."""
    phi = math.radians(ARM_ANGLE)
    rise = 2 * radius * (1 - math.cos(phi))  # the arm ends this far above its lowest point
    reach = 2 * radius * math.sin(phi)  # horizontal distance from the coupling point to the arm straight
    arm = WIDTH + gap + rise  # arm straight above the bus, centre to centre
    half = (arm + Y_ABOVE + Y_BELOW) / 2
    y_bus = Y_BELOW - half
    x_half = reach + PORT_STRAIGHT + 1.0
    return dict(gap=gap, radius=radius, y_bus=y_bus, y_ring=y_bus + WIDTH + gap, y_arm=y_bus + arm, reach=reach,
                x_half=x_half, x_port=x_half - 1.0, y_min=-half, y_max=half)  # fmt: skip


def write_gds(gap: float, radius: float = RADIUS, with_bus: bool = True, name: str | None = None) -> tuple[Path, dict]:
    import gdsfactory as gf

    g = geometry(gap, radius)
    x0, x1 = -g["x_half"] - MARGIN, g["x_half"] + MARGIN
    y0, y1 = g["y_min"] - MARGIN, g["y_max"] + MARGIN
    c = gf.Component()
    c.add_polygon(strip(x0, x1, y0, y1), layer=t.SLAB90)
    if with_bus:
        c.add_polygon(strip(x0, x1, g["y_bus"] - WIDTH / 2, g["y_bus"] + WIDTH / 2), layer=t.WG)
    ext = x1 - g["reach"]
    arm = (
        gf.path.straight(ext)
        + gf.path.arc(radius=radius, angle=-ARM_ANGLE)
        + gf.path.arc(radius=radius, angle=2 * ARM_ANGLE)
        + gf.path.arc(radius=radius, angle=-ARM_ANGLE)
        + gf.path.straight(ext)
    )
    ref = c << gf.path.extrude(arm, layer=t.WG, width=WIDTH)
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


def build(f, gds: Path, g: dict, *, with_bus: bool, source_port: str, mesh_accuracy: int, fine: bool,
          fpts: int, sim_time: float, gap_mesh: float = 0.02) -> None:  # fmt: skip
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
        f.set("x span", 1.0 * g["reach"] * um)
        f.set("y min", (g["y_bus"] - WIDTH / 2 - 0.1) * um)
        f.set("y max", (g["y_ring"] + WIDTH / 2 + 0.6) * um)
        f.set("z min", -0.04 * um)
        f.set("z max", (T_SI + 0.04) * um)
        f.set("override x mesh", 0)
        f.set("dy", gap_mesh * um)
        f.set("dz", gap_mesh * um)

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
    ``f`` is the open session when the project is still open.  With ``f=None`` the saved project is
    opened and run through the API; that is also the fallback when the engine binary is not found.
    """
    engine = lumerical_root() / "bin" / ("fdtd-engine.exe" if os.name == "nt" else "fdtd-engine")
    if job_manager or not engine.exists():
        if f is not None:
            f.run()
        else:
            with import_lumapi().FDTD(filename=str(fsp), hide=True) as g:
                g.run()
                g.save(str(fsp))  # the results go into the project file, where run_case reads them
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


def run_case(name: str, gap: float, *, radius: float, with_bus: bool = True, keep_results: bool = False,
             job_manager: bool = False, threads: int = 8, **mesh) -> dict:  # fmt: skip
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
    res.update(gap=gap, radius=radius, name=name, minutes=(time.time() - t0) / 60, with_bus=with_bus,
               y_bus=g["y_bus"], y_ring=g["y_ring"], y_arm=g["y_arm"], x_port=g["x_port"])  # fmt: skip
    np.savez_compressed(OUT / f"{name}.npz", **res)
    return res


def at_design_wavelength(res: dict) -> dict:
    """|S|^2 of every port at exactly LAM: the power is interpolated linearly between the grid points."""
    lam = np.asarray(res["lam"], dtype=float)
    order = np.argsort(lam)
    lam = lam[order]
    if not lam[0] <= LAM <= lam[-1]:  # np.interp would clamp to the end point without a word
        raise ValueError(f"design wavelength {LAM} um is outside the simulated range {lam[0]:.4f} to {lam[-1]:.4f} um")
    return {key[1]: float(np.interp(LAM, lam, np.abs(np.asarray(res[key])[order]) ** 2))
            for key in ("S1", "S2", "S3", "S4") if key in res}  # fmt: skip


def load_kept(path: Path) -> dict:
    """One kept .npz as a dict; gap, radius and minutes become Python floats."""
    with np.load(path) as data:
        out = {key: data[key] for key in data.files}
    out.update({key: float(out[key]) for key in ("gap", "radius", "minutes")})
    return out


def write_summary(use_reference: bool) -> None:
    """Build coupling_vs_gap.csv and .txt (step 6 reads the CSV) from the kept .npz files.  No Lumerical needed.

    Every coupler_gap*.npz in the folder is a row.  With the reference arm, kappa^2 = |S41|^2 / sqrt(T_arm).
    Without it (use_reference False, or the reference file missing), kappa^2 is the raw |S41|^2 and the
    arm transmission is NaN.
    """
    paths = sorted(OUT.glob("coupler_gap*.npz"))
    if not paths:
        raise SystemExit(f"no coupler_gap*.npz in {OUT}: run the simulations first")
    runs = [load_kept(p) for p in paths]
    ref_path = OUT / "coupler_reference_arm.npz"
    reference = load_kept(ref_path) if use_reference and ref_path.exists() else None
    arm = at_design_wavelength(reference)["4"] if reference is not None else math.nan  # port 3 -> port 4, no bus
    scale = 1 / math.sqrt(arm) if reference is not None else 1.0  # the de-embedding of kappa^2
    rows = []
    for res in runs:
        p = at_design_wavelength(res)
        rows.append((res["gap"], p["4"] * scale, p["2"], p["4"], p["1"], p["3"], res["minutes"]))
    rows.sort()
    gaps, kappa2 = np.array([r[0] for r in rows]), np.array([r[1] for r in rows])
    lines = [f"Coupling region, R = {runs[0]['radius']} um, W = {WIDTH} um, rib waveguide, lambda = {LAM} um"]
    if reference is not None:
        lines.append(f"arm alone (port 3 -> port 4, no bus): T = {arm:.4f}  ->  half an arm transmits {math.sqrt(arm):.4f}")
    else:
        lines.append("no reference arm: kappa^2 is the raw |S41|^2, not corrected for the arm loss (arm transmission NaN)")
    lines.append(f"{'gap (um)':>9} {'kappa^2':>9} {'t^2 |S21|^2':>12} {'kappa^2 + t^2':>14} {'raw |S41|^2':>12} {'|S11|^2':>9} {'|S31|^2':>9} {'minutes':>8}")  # fmt: skip
    lines += [
        f"{g:9.3f} {k2:9.5f} {t2:12.5f} {k2 + t2:14.4f} {raw:12.5f} {r1:9.2e} {r3:9.2e} {m:8.1f}"
        for g, k2, t2, raw, r1, r3, m in rows
    ]
    if len(rows) > 1:
        slope, intercept = np.polyfit(gaps, np.log(kappa2), 1)
        amp = math.exp(intercept)
        lo, hi = round(gaps.min() * 1000), round(gaps.max() * 1000)  # the gaps the fit is valid for
        warning = "; an interpolation formula, do not extrapolate" + (" (its amplitude exceeds 1)" if amp > 1 else "")
        lines.append(
            f"\nfit: kappa^2 = {amp:.4f} * exp(-gap / {-1000 / slope:.1f} nm); fitted for gaps of {lo} to {hi} nm{warning}"
        )
    if reference is not None:
        lines.append("kappa^2 is |S41|^2 divided by the transmission of half an arm; kappa^2 + t^2 = 1 for a lossless coupler.")
    else:
        lines.append("kappa^2 + t^2 = 1 for a lossless coupler.")
    (OUT / "coupling_vs_gap.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with open(OUT / "coupling_vs_gap.csv", "w", encoding="utf-8") as fh:
        fh.write("gap_um,kappa2,t2_S21,raw_S41,r_S11,r_S31,arm_transmission\n")
        fh.writelines(f"{g},{k2},{t2},{raw},{r1},{r3},{arm}\n" for g, k2, t2, raw, r1, r3, _ in rows)
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
    fig, ax = plt.subplots(figsize=(10, 4.2))
    for layer, color, label in ((t.SLAB90, "0.88", "SLAB90 (90 nm slab)"), (t.WG, t.LAYER_COLORS["WG"], "WG (220 nm core)")):
        region = kdb.Region(cell.begin_shapes_rec(layout.layer(*tuple(layer)))).merged()
        for i, poly in enumerate(region.each()):
            pts = [(p.x * layout.dbu, p.y * layout.dbu) for p in poly.each_point_hull()]
            ax.add_patch(Polygon(pts, fc=color, ec="none", label=label if i == 0 else None))
    ax.add_patch(
        Rectangle(
            (-g["x_half"], g["y_min"]), 2 * g["x_half"], g["y_max"] - g["y_min"], fill=False, ls="--", ec="k", label="FDTD region"
        )
    )
    ports = (("port 1", -g["x_port"], g["y_bus"]), ("port 2", g["x_port"], g["y_bus"]),
             ("port 3", -g["x_port"], g["y_arm"]), ("port 4", g["x_port"], g["y_arm"]))  # fmt: skip
    for name, x, y in ports:
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
    FIGURES.mkdir(parents=True, exist_ok=True)
    path = FIGURES / "check_coupler_setup.png"
    fig.savefig(path, dpi=130)
    print("preview ->", path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gaps", type=float, nargs="*", default=[0.20, 0.30, 0.40, 0.50], help="gaps in um")
    ap.add_argument("--radius", type=float, default=RADIUS)
    ap.add_argument("--dry", action="store_true", help="coarse mesh, first gap only, no reference")
    ap.add_argument("--no-reference", action="store_true", help="skip the run without the bus (no de-embedding)")
    ap.add_argument("--summary-only", action="store_true",
                    help="rebuild coupling_vs_gap.csv/.txt from the kept .npz files; no Lumerical")  # fmt: skip
    ap.add_argument("--preview", action="store_true", help="only draw the layout and the simulation window")
    ap.add_argument("--accuracy", type=int, default=2, help="FDTD mesh accuracy")
    ap.add_argument("--gap-mesh", type=float, default=0.02, help="mesh step over the coupler (um); 0.01 for the mesh check")
    ap.add_argument("--time", type=float, default=2.5e-12, help="simulation time (s)")
    ap.add_argument("--threads", type=int, default=min(16, os.cpu_count() or 4))
    ap.add_argument("--job-manager", action="store_true", help="run through Lumerical's job manager instead of the CPU engine")
    ap.add_argument("--keep-results", action="store_true", help="keep the fields in the .fsp files")
    a = ap.parse_args()
    if a.summary_only:
        write_summary(use_reference=not a.no_reference)
        return
    if a.preview:
        preview(a.gaps[0], a.radius)
        return
    require_process_file()
    mesh = dict(mesh_accuracy=a.accuracy, fine=True, fpts=101, sim_time=a.time, gap_mesh=a.gap_mesh)
    run = dict(radius=a.radius, keep_results=a.keep_results, job_manager=a.job_manager, threads=a.threads)
    prefix, gaps = "coupler", a.gaps
    if a.dry:
        mesh.update(mesh_accuracy=1, fine=False, fpts=21)
        prefix, gaps = "dry", a.gaps[:1]
    reference = None
    if not a.dry and not a.no_reference:
        print(f"==== reference arm started {time.strftime('%H:%M:%S')}", flush=True)
        reference = run_case("coupler_reference_arm", gaps[0], with_bus=False, **run, **mesh)
        print(f"     arm transmission = {at_design_wavelength(reference)['4']:.4f}  ({reference['minutes']:.1f} min)", flush=True)
    for gap in gaps:
        name = f"{prefix}_gap{round(gap * 1000):03d}nm"
        print(f"==== {name} started {time.strftime('%H:%M:%S')}", flush=True)
        res = run_case(name, gap, **run, **mesh)
        p = at_design_wavelength(res)
        print(
            f"     |S41|^2 = {p['4']:.5f}, t^2 = {p['2']:.5f}, sum = {sum(p.values()):.4f}  ({res['minutes']:.1f} min)",
            flush=True,
        )
    if not a.dry:
        write_summary(use_reference=not a.no_reference)


if __name__ == "__main__":
    main()
