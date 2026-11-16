"""Panels that the figures of more than one device draw: a mode on a cross-section, a field seen from above, a sweep.

    import panels                      # from a figure script: lumerical_simulations/ is put on the path first
    d = panels.load(step_folder / "strip_modes.npz")

Every figure goes through figstyle.py (sizes, type, colours); this file only saves repeating the same
panel in the strip waveguide, the rib waveguide, the coupler and the splitter.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
import figstyle as fs  # noqa: E402
import gsip_technology as t  # noqa: E402

NEFF = "n$_{\\mathrm{eff}}$"
NG = "n$_{\\mathrm{g}}$"


def load(path: Path) -> dict:
    """Every array and scalar of a kept result file, by its key."""
    if not path.exists():
        raise SystemExit(f"{path} is missing: run the simulation step of this folder first")
    with np.load(path) as npz:
        return {key: npz[key] for key in npz.files}


def minus(value: float, fmt: str) -> str:
    """Number with a typographic minus sign."""
    return format(value, fmt).replace("-", "−")


def decibel(power) -> np.ndarray:
    return -10 * np.log10(np.asarray(power, float))


# =====================================================================================
# cross-sections
# =====================================================================================
def strip_outline(ax, width: float, y0: float = 0.0) -> None:
    fs.box(ax, y0 - width / 2, y0 + width / 2, 0.0, t.T_SI, edgecolor=fs.INK, lw=0.5, zorder=4)


def core_share(y, z, e, width: float, y0: float = 0.0) -> float:
    """Share of |E|^2 that lies inside a strip core of the given width, every cell weighted by its area."""
    cell = np.outer(np.gradient(y), np.gradient(z))
    inside = (np.abs(np.asarray(y) - y0)[:, None] <= width / 2) & ((np.asarray(z) >= 0) & (np.asarray(z) <= t.T_SI))[None, :]
    return float((e * cell * inside).sum() / (e * cell).sum())


def mode_map(ax, y, z, e, window_y: tuple[float, float], window_z: tuple[float, float], text: str = "", outline=None):
    """Normalised intensity of a mode on the cross-section, with the outline of the silicon."""
    image = ax.pcolormesh(y, z, (e / e.max()).T, cmap=fs.CMAP_FIELD, vmin=0, vmax=1, shading="auto", rasterized=True)
    ax.set_xlim(*window_y)
    ax.set_ylim(*window_z)
    fs.image_axes(ax, "y (µm)", "z (µm)")
    ax.set_anchor("N")  # an image is shorter than its grid cell: keep it at the top, level with the plots beside it
    if outline is not None:
        outline(ax)
    if text:
        fs.note(ax, text, (0.03, 0.96), ha="left", va="top", transform=ax.transAxes)
    return image


# =====================================================================================
# the device seen from above
# =====================================================================================
def layout_polygons(gds: Path, layer=t.WG) -> list[np.ndarray]:
    """Outlines (um) of the merged shapes of one layer of a GDS file."""
    import klayout.db as kdb

    layout = kdb.Layout()
    layout.read(str(gds))
    region = kdb.Region(layout.top_cell().begin_shapes_rec(layout.layer(*tuple(layer)))).merged()
    return [np.array([(p.x * layout.dbu, p.y * layout.dbu) for p in poly.each_point_hull()]) for poly in region.each()]


def field_map(ax, x, y, e, gds: Path | None = None, xlim=None, ylim=None, vmax: float | None = None, power: float = 1.0):
    """|E| on the plane through the middle of the silicon, with the outline of the layout drawn over it.

    The colour scale is linear in |E| (``power`` = 1) and runs to ``vmax`` times the largest value (1 by default).
    """
    e = np.asarray(e, float)
    top = e.max() * (vmax or 1.0)
    image = ax.pcolormesh(
        x, y, (np.clip(e / top, 0, 1) ** power).T, cmap=fs.CMAP_FIELD, vmin=0, vmax=1, shading="auto", rasterized=True
    )
    if gds is not None:
        for points in layout_polygons(gds):
            closed = np.vstack([points, points[:1]])
            ax.plot(closed[:, 0], closed[:, 1], color=fs.INK, lw=0.4, zorder=4)
    ax.set_xlim(*(xlim or (float(np.min(x)), float(np.max(x)))))
    ax.set_ylim(*(ylim or (float(np.min(y)), float(np.max(y)))))
    for side in ("top", "right"):
        ax.spines[side].set_visible(True)
    ax.set_xlabel("x (µm)")
    ax.set_ylabel("y (µm)")
    return image


def stretch_note(ax, loc: tuple[float, float] = (0.985, 0.06)) -> None:
    """Say by how much y is stretched against x in a panel whose aspect is left to the layout.

    A long, narrow device fills its panel only if y is stretched.  The factor depends on the final size
    of the panel, so the figure is laid out first and the factor is read from it.
    """
    ax.figure.canvas.draw()
    box = ax.get_window_extent()
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    factor = (box.height / abs(y1 - y0)) / (box.width / abs(x1 - x0))
    fs.note(ax, f"y stretched {factor:.1f} times", loc, ha="right", va="bottom", transform=ax.transAxes)


# =====================================================================================
# sweeps of a waveguide
# =====================================================================================
def dispersion(ax, d: dict, ylim: tuple[float, float]) -> None:
    """n_eff of TE0 against wavelength, with the group index."""
    lam, neff = d["sweep_lam"] * 1000, d["sweep_neff"]
    ax.axvline(float(d["lam"]) * 1000, color=fs.HAIRLINE, lw=0.5, zorder=0)
    ax.plot(lam, neff, "o-", color=fs.BLUE, ms=3, lw=1, zorder=2, clip_on=False)
    ax.set_xlim(lam.min(), lam.max())
    ax.set_xticks([1500, 1550, 1600])
    ax.set_ylim(*ylim)
    ax.set_xlabel("wavelength (nm)")
    ax.set_ylabel(f"effective index {NEFF}")
    text = f"{NG} at {float(d['lam']) * 1000:.0f} nm = {float(d['ng']):.3f}\n{NG} from the slope = {float(d['ng_fit']):.3f}"
    fs.note(ax, text, (0.97, 0.96), ha="right", va="top", transform=ax.transAxes)


def bend_loss(ax, d: dict, ylim: tuple[float, float], floor: float = 1e-5) -> None:
    """Loss of a 90 degree bend between two straights against the radius: two junctions, and radiation.

    Radiation at or below ``floor`` (dB per 90 degrees) is the noise of the solver and is drawn on the floor, hollow.
    """
    r = d["bend_radii"]
    junctions, radiation = 2 * d["bend_junction_dB"], d["bend_radiation_dB_90"]
    real = radiation > floor
    ax.axvline(float(d["radius"]), color=fs.MUTED, lw=0.5, zorder=1)
    ax.semilogy(r, junctions, "o-", color=fs.BLUE, ms=3, lw=1, zorder=3, label="two junctions")
    ax.semilogy(r[real], radiation[real], "s-", color=fs.ORANGE, ms=3, lw=1, zorder=3, label="radiation")
    ax.semilogy(r[~real], np.full(int(np.sum(~real)), floor), "s", mfc=fs.SURFACE, mec=fs.ORANGE, mew=0.8, ms=3, zorder=3)
    ax.set_ylim(*ylim)
    if (~real).any():  # say from which radius on the radiation is only solver noise
        text = (
            "radiation: below the solver floor"
            if not real.any()
            else f"radiation: below the solver floor from {r[~real].min():g} µm"
        )
        ax.text(
            0.97,
            floor * 2.2,
            text,
            ha="right",
            va="center",
            fontsize=6,
            color=fs.SECONDARY,
            zorder=2,
            transform=ax.get_yaxis_transform(),
            bbox=dict(fc=fs.SURFACE, ec="none", pad=0.6),
        )
    ax.set_xlabel("bend radius (µm)")
    ax.set_ylabel("loss of a 90° bend (dB)")
    ax.legend(loc="upper right")


def width_sweep(ax, widths, series: dict[str, np.ndarray], reference: float, reference_label: str, design: float, ylim) -> None:
    """n_eff of several modes against the core width, with the index a guided mode must exceed."""
    w = np.asarray(widths) * 1000
    ax.axhline(reference, color=fs.MUTED, lw=0.8, zorder=1)
    ax.axvline(design * 1000, color=fs.HAIRLINE, lw=0.5, zorder=0)
    for (label, values), colour in zip(series.items(), fs.CATEGORICAL, strict=False):
        ok = np.isfinite(values)
        ax.plot(w[ok], values[ok], "o-", color=colour, ms=3, lw=1, zorder=3)
        ax.text(w[ok][-1] + 0.02 * (w.max() - w.min()), values[ok][-1], label, va="center", fontsize=6, color=fs.INK)
    ax.set_xlim(w.min() - 30, w.max() + 0.12 * (w.max() - w.min()))
    ax.set_ylim(*ylim)
    ax.text(
        w.min() - 20,
        reference + 0.012 * (ylim[1] - ylim[0]),
        reference_label,
        ha="left",
        va="bottom",
        fontsize=6,
        color=fs.SECONDARY,
    )
    ax.set_xlabel("core width (nm)")
    ax.set_ylabel(f"effective index {NEFF}")
