"""One call from a GDS (or gdsfactory Component) to a folder of ready-to-run Lumerical scripts.

>>> from photonics_cookbook.lumerical import export_lumerical
>>> res = export_lumerical("build/ring_modulator.gds", "cornerstone_si220_active",
...                        cut=((5.45, 0), (14.55, 0)), origin=(10, 0),
...                        norm_length_um=46.5, bend_radius_um=10)

Writes next to the GDS:

=========================  ==============================================  ===========
file                       what                                            product
=========================  ==============================================  ===========
<p>_geometry3d.lsf         gdsimport of every drawn layer + background     FDTD / MODE
<p>_fdtd3d.lsf             geometry + 3D FDTD region + ports               FDTD
<p>_layerbuilder.lsf       Layer Builder + saveprocessfile -> <proc>.lbr   FDTD / MODE
<p>_charge2d.lsf           2D cut -> CHARGE (doping, contacts, bias)       CHARGE
<p>_fde2d.lsf              same cut -> FDE, imports CHARGE carriers        MODE
<p>_xsec.json / .png       the extracted cross-section (check it!)         --
<p>_lumerical.json         ports, cut, process -- for your own scripts     --
=========================  ==============================================  ===========
"""

from __future__ import annotations

import json
import shutil
import warnings
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from photonics_cookbook.lumerical.cutline import CrossSection2D, cross_section
from photonics_cookbook.lumerical.gds_reader import read_gds_polygons
from photonics_cookbook.lumerical.scripts_2d import charge2d_lsf, fde2d_lsf
from photonics_cookbook.lumerical.scripts_3d import OpticalPort, fdtd3d_lsf, geometry3d_lsf, layerbuilder_lsf
from photonics_cookbook.process import Process, load_process

ALL_TARGETS = ("geometry3d", "fdtd3d", "layerbuilder", "charge2d", "fde2d")


@dataclass
class ExportResult:
    out_dir: Path
    cell: str
    files: dict[str, Path] = field(default_factory=dict)
    xsec: CrossSection2D | None = None
    skipped: dict[str, str] = field(default_factory=dict)

    def __str__(self) -> str:
        lines = [f"Lumerical export of '{self.cell}' -> {self.out_dir}"]
        lines += [f"  {k:<13} {v.name}" for k, v in self.files.items()]
        lines += [f"  {k:<13} skipped: {why}" for k, why in self.skipped.items()]
        return "\n".join(lines)


# ------------------------------------------------------------- gdsfactory glue
def ports_from_component(component: Any) -> list[OpticalPort]:
    """Optical ports of a gdsfactory (>= 9) Component, in um."""
    out = []
    for p in component.ports:
        if getattr(p, "port_type", "optical") != "optical":
            continue
        cx, cy = p.center
        out.append(OpticalPort(str(p.name), float(cx), float(cy), float(p.width), float(p.orientation)))
    return out


def info_from_component(component: Any) -> dict[str, Any]:
    """``component.info`` as a plain dict (JSON text written by older kfactory versions is decoded)."""
    info = component.info
    data: dict[str, Any] | None = None
    for meth in ("model_dump", "dict"):
        if hasattr(info, meth):
            try:
                data = dict(getattr(info, meth)())
                break
            except Exception:
                pass
    if data is None:
        data = dict(info)
    for key, value in data.items():
        if isinstance(value, str) and value[:1] in "{[":
            try:
                data[key] = json.loads(value)
            except ValueError:
                pass
    return data


# ------------------------------------------------------------------- helpers
def _bbox(polys: dict, keys: list[tuple[int, int]]) -> tuple[float, float, float, float] | None:
    xs, ys = [], []
    for k in keys:
        for contours in polys.get(k, []):
            xs += [contours[0][:, 0].min(), contours[0][:, 0].max()]
            ys += [contours[0][:, 1].min(), contours[0][:, 1].max()]
    if not xs:
        return None
    return float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def export_lumerical(
    gds_path: str | Path,
    process: str | Path | Process,
    out_dir: str | Path | None = None,
    *,
    cell: str | None = None,
    ports: list[OpticalPort] | None = None,
    info: dict[str, Any] | None = None,
    cut: tuple[tuple[float, float], tuple[float, float]] | None = None,
    origin: tuple[float, float] | None = None,
    norm_length_um: float | None = None,
    bend_radius_um: float | None = None,
    bend_center_side: str | None = None,
    anode_role: str | None = None,
    cathode_role: str | None = None,
    v_stop: float = -4.0,
    n_points: int = 9,
    targets: tuple[str, ...] = ALL_TARGETS,
    prefix: str | None = None,
    preview: bool = True,
) -> ExportResult:
    """Generate Lumerical scripts for ``gds_path`` (see module docstring).

    Simulation hints default to ``info["lumerical"]`` as stored by the cookbook's
    gdsfactory cells (cut line, bend radius, norm length, contact roles); explicit
    arguments override them.
    """
    proc = process if isinstance(process, Process) else load_process(process)
    gds_path = Path(gds_path)
    out = Path(out_dir) if out_dir else gds_path.parent
    out.mkdir(parents=True, exist_ok=True)
    if not str(out.resolve()).isascii():
        warnings.warn(
            f"output folder {out} contains non-ASCII characters; Lumerical solvers may fail to "
            "write their data files there. Set PHOTONICS_BUILD_DIR to an ASCII path (e.g. D:\\photonics_build).",
            stacklevel=2,
        )
    gds_local = out / gds_path.name
    if gds_local.resolve() != gds_path.resolve():
        shutil.copy2(gds_path, gds_local)

    hint = dict((info or {}).get("lumerical", {}))
    if cut is None and "cut_p0_um" in hint:
        cut = (tuple(hint["cut_p0_um"]), tuple(hint["cut_p1_um"]))  # type: ignore[assignment]
    origin = origin or (tuple(hint["cut_origin_um"]) if "cut_origin_um" in hint else None)  # type: ignore[assignment]
    norm_length_um = norm_length_um or hint.get("norm_length_um")
    bend_radius_um = bend_radius_um or hint.get("bend_radius_um")
    bend_center_side = bend_center_side or hint.get("bend_center_side", "-x")
    anode_role = anode_role or hint.get("anode_role", "ppp")
    cathode_role = cathode_role or hint.get("cathode_role", "npp")

    gds_layers = [lay.gds for lay in proc.layers.values()]
    cell_name, polys, bbox_all = read_gds_polygons(gds_local, cell=cell, layers=gds_layers)
    pre = prefix or gds_path.stem
    res = ExportResult(out_dir=out, cell=cell_name)
    present = set(polys)
    struct_keys = [lay.gds for lay in proc.by_kind("structure")]
    bbox_opt = _bbox(polys, struct_keys) or bbox_all

    if "geometry3d" in targets:
        res.files["geometry3d"] = _write(out / f"{pre}_geometry3d.lsf", geometry3d_lsf(gds_local.name, cell_name, proc, bbox_all, present=present))
    if "fdtd3d" in targets:
        if ports:
            res.files["fdtd3d"] = _write(
                out / f"{pre}_fdtd3d.lsf",
                fdtd3d_lsf(
                    gds_local.name, cell_name, proc, bbox_all, bbox_opt, ports,
                    save_as=f"{pre}_fdtd.fsp", present=present,
                ),
            )
        else:
            res.skipped["fdtd3d"] = "no optical ports given (pass ports=ports_from_component(c))"
    if "layerbuilder" in targets:
        res.files["layerbuilder"] = _write(
            out / f"{pre}_layerbuilder.lsf",
            layerbuilder_lsf(gds_local.name, cell_name, proc, lbr_name=f"{pre}.lbr", present=present),
        )

    if cut is not None:
        xsec = cross_section(polys, proc, cut[0], cut[1], origin=origin, cell=cell_name, source=gds_local.name)
        res.xsec = xsec
        res.files["xsec_json"] = xsec.to_json(out / f"{pre}_xsec.json")
        if "charge2d" in targets:
            if norm_length_um:
                try:
                    res.files["charge2d"] = _write(
                        out / f"{pre}_charge2d.lsf",
                        charge2d_lsf(
                            xsec, proc, norm_length_um, anode_role, cathode_role,
                            v_stop=v_stop, n_points=n_points, out_prefix=pre,
                        ),
                    )
                except ValueError as err:
                    res.skipped["charge2d"] = str(err)
            else:
                res.skipped["charge2d"] = "norm_length_um unknown (doped length of the device)"
        if "fde2d" in targets:
            try:
                res.files["fde2d"] = _write(
                    out / f"{pre}_fde2d.lsf",
                    fde2d_lsf(
                        xsec, proc, bend_radius_um=bend_radius_um, bend_center_side=bend_center_side,
                        doped_length_um=norm_length_um, out_prefix=pre,
                    ),
                )
            except ValueError as err:
                res.skipped["fde2d"] = str(err)
        if preview:
            try:
                import matplotlib

                matplotlib.use("Agg")
                from photonics_cookbook.plotting import plot_cross_section, save

                res.files["xsec_png"] = save(plot_cross_section(xsec, proc), out / f"{pre}_xsec.png")
            except Exception as err:  # previews must never break an export
                res.skipped["xsec_png"] = f"{type(err).__name__}: {err}"
    else:
        for t in ("charge2d", "fde2d"):
            if t in targets:
                res.skipped[t] = "no cut line (pass cut=((x0, y0), (x1, y1)))"

    meta = {
        "cell": cell_name,
        "gds": gds_local.name,
        "process": proc.name,
        "process_file": proc.source,
        "bbox_um": bbox_all,
        "optical_bbox_um": bbox_opt,
        "ports": [asdict(p) for p in (ports or [])],
        "cut": {"p0": cut[0], "p1": cut[1], "origin": origin} if cut else None,
        "norm_length_um": norm_length_um,
        "bend_radius_um": bend_radius_um,
        "files": {k: v.name for k, v in res.files.items()},
        "skipped": res.skipped,
    }
    res.files["meta"] = out / f"{pre}_lumerical.json"
    res.files["meta"].write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return res
