"""One look for every figure of the cookbook: journal-style matplotlib settings and a few drawing helpers.

The conventions are those of the Nature journals' figure guide:

    * sans-serif type (Arial or Helvetica), 5-7 pt at final size; panel labels a, b, c in 8 pt bold
    * figure widths of 89 mm (one column), 120 mm or 183 mm (two columns)
    * thin lines (0.5 pt axes, 1 pt data), ticks outside, no box around the plot, no grid
    * colour that survives colour-vision deficiency and greyscale: no rainbow maps; magnitude is one hue
      from light to dark, signed quantities diverge from a neutral midpoint, categories take few fixed hues

    import figstyle as fs
    fig, axes = fs.figure(fs.DOUBLE, 70, ncols=3)      # width and height in mm
    fs.panel_label(axes[0], "a")
    fs.save(fig, "figures/fig1_coupling.png")           # PNG at 400 dpi; add pdf=True for a vector copy

The module needs matplotlib and numpy only.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap, ListedColormap
from matplotlib.patches import Rectangle

# ---- sizes ----
MM = 1 / 25.4  # inches per millimetre
SINGLE, ONE_AND_HALF, DOUBLE = 89.0, 120.0, 183.0  # figure widths in mm
DPI = 400

# ---- ink ----
INK = "#0b0b0b"  # text, axes
SECONDARY = "#52514e"  # annotations
MUTED = "#898781"  # reference lines, outlines of structures
HAIRLINE = "#c3c2b7"  # baselines
SURFACE = "#ffffff"

# ---- categorical: three hues that stay distinct for every pair, in this order (validated for CVD) ----
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
CATEGORICAL = [BLUE, ORANGE, AQUA]
RED = "#d03b3b"  # reserved for p-type silicon in doping and carrier maps (blue is n-type)

# ---- ordered series (a bias sweep, a gap sweep): one hue, light to dark ----
_BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
_REDS = ["#fbd5d1", "#f4a59f", "#ea766f", "#d94a45", "#b7302e", "#8b1f20", "#5f1114"]
_WARM = ["#fff4d6", "#fddc8c", "#f9b54a", "#ef8733", "#d9532a", "#aa2b25", "#6b1220"]
_SLATE = ["#f1f3f5", "#cfd6dd", "#a3aebb", "#75849a", "#4f5f78", "#31405a", "#17233b"]


def _ramp(name: str, colors: list[str], white: bool = False) -> LinearSegmentedColormap:
    return LinearSegmentedColormap.from_list(name, (["#ffffff"] if white else []) + colors)


CMAP_FIELD = _ramp("field", _BLUES, white=True)  # optical intensity: white -> dark blue
CMAP_N = _ramp("electrons", _BLUES, white=True)  # electron density
CMAP_P = _ramp("holes", _REDS, white=True)  # hole density
CMAP_HEAT = _ramp("heat", _WARM, white=True)  # temperature rise: the one multi-hue ramp (heat reads as heat)
CMAP_DOPING = LinearSegmentedColormap.from_list("doping", [*_REDS[::-1], "#f0efec", *_BLUES])  # p <- neutral -> n
CMAP_SWEEP = _ramp("sweep", _BLUES[1:])  # line colours of an ordered sweep
CMAP_SWEEP_WARM = _ramp("sweep_warm", _WARM[2:])  # a second ordered sweep in the same figure (heater power)

# ---- materials in cross-sections; the same colours as the layout layers of the PDK ----
MATERIAL_COLORS = {
    "oxide": "#f4f2ec",
    "silicon": "#4a5568",
    "substrate": "#a0aec0",
    "aluminium": "#ecc94b",
    "tin": "#805ad5",
    "air": "#ffffff",
    "n": "#9ecae1",
    "n+": "#4292c6",
    "n++": "#08519c",
    "p": "#fcbba1",
    "p+": "#fb6a4a",
    "p++": "#cb181d",
}


def _font() -> str:
    for name in ("Arial", "Helvetica", "Liberation Sans"):
        try:
            font_manager.findfont(name, fallback_to_default=False)
            return name
        except ValueError:
            continue
    return "DejaVu Sans"


FONT = _font()

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": [FONT, "DejaVu Sans"],
        "font.size": 7,
        "axes.labelsize": 7,
        "axes.titlesize": 7,
        "axes.titleweight": "normal",
        "xtick.labelsize": 6,
        "ytick.labelsize": 6,
        "legend.fontsize": 6,
        "legend.frameon": False,
        "legend.handlelength": 1.4,
        "legend.borderaxespad": 0.2,
        "axes.linewidth": 0.5,
        "axes.edgecolor": INK,
        "axes.labelcolor": INK,
        "axes.labelpad": 2.0,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "axes.prop_cycle": plt.cycler(color=CATEGORICAL),
        "xtick.color": INK,
        "ytick.color": INK,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "xtick.minor.size": 1.5,
        "ytick.minor.size": 1.5,
        "xtick.major.width": 0.5,
        "ytick.major.width": 0.5,
        "xtick.minor.width": 0.4,
        "ytick.minor.width": 0.4,
        "xtick.major.pad": 2.0,
        "ytick.major.pad": 2.0,
        "lines.linewidth": 1.0,
        "lines.markersize": 3.0,
        "lines.markeredgewidth": 0.0,
        "patch.linewidth": 0.5,
        "text.color": INK,
        "mathtext.fontset": "custom",
        "mathtext.rm": FONT,
        "mathtext.it": f"{FONT}:italic",
        "mathtext.bf": f"{FONT}:bold",
        "mathtext.default": "regular",
        "figure.dpi": 150,
        "figure.facecolor": SURFACE,
        "savefig.dpi": DPI,
        "savefig.facecolor": SURFACE,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
        "image.interpolation": "nearest",
    }
)


# =====================================================================================
# figure, labels, saving
# =====================================================================================
def figure(width_mm: float, height_mm: float, nrows: int = 1, ncols: int = 1, **kwargs):
    """``plt.subplots`` with the size given in millimetres and a constrained layout."""
    kwargs.setdefault("layout", "constrained")
    fig, axes = plt.subplots(nrows, ncols, figsize=(width_mm * MM, height_mm * MM), **kwargs)
    fig.get_layout_engine().set(w_pad=2 / 72, h_pad=2 / 72, wspace=0.04, hspace=0.04)
    return fig, axes


def mosaic(width_mm: float, height_mm: float, layout, **kwargs):
    """``plt.subplot_mosaic`` with the size given in millimetres and a constrained layout."""
    kwargs.setdefault("layout", "constrained")
    fig, axes = plt.subplot_mosaic(layout, figsize=(width_mm * MM, height_mm * MM), **kwargs)
    fig.get_layout_engine().set(w_pad=2 / 72, h_pad=2 / 72, wspace=0.04, hspace=0.04)
    return fig, axes


def panel_label(ax, letter: str, dx: float = -0.0, dy: float = 0.0) -> None:
    """Bold lower-case panel label above the top-left corner of the axes (offsets in points)."""
    ax.annotate(
        letter, xy=(0, 1), xycoords="axes fraction", xytext=(-18 + dx, 5 + dy), textcoords="offset points",
        fontsize=8, fontweight="bold", va="bottom", ha="left", annotation_clip=False,
    )  # fmt: skip


def panel_title(ax, text: str) -> None:
    """Short description of a panel, in the secondary ink, left-aligned above the axes."""
    ax.set_title(text, loc="left", fontsize=7, color=SECONDARY, pad=5)


def save(fig, path: str | Path, pdf: bool = False) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    if pdf:
        fig.savefig(path.with_suffix(".pdf"))
    plt.close(fig)
    print("figure ->", path)
    return path


# =====================================================================================
# helpers for the recurring plot elements
# =====================================================================================
def sweep_colors(n: int, cmap=None) -> list:
    """n colours of an ordered sweep, light to dark."""
    cmap = cmap or CMAP_SWEEP
    return [cmap(x) for x in (np.linspace(0, 1, n) if n > 1 else [0.7])]


def colorbar(fig, mappable, ax, label: str, **kwargs):
    """Slim colour bar with a label; it takes its room from ``ax``."""
    kwargs.setdefault("fraction", 0.045)
    kwargs.setdefault("pad", 0.02)
    kwargs.setdefault("aspect", 22)
    bar = fig.colorbar(mappable, ax=ax, **kwargs)
    bar.set_label(label, fontsize=6, labelpad=2)
    bar.ax.tick_params(labelsize=6, length=2, width=0.5)
    bar.outline.set_linewidth(0.5)
    return bar


def colorbar_beside(ax, mappable, label: str, width: float = 0.022, pad: float = 0.02, **kwargs):
    """Colour bar exactly as tall as an image panel: an inset to the right of ``ax`` (width and pad in axes fractions).

    ``fig.colorbar(ax=...)`` sizes the bar to the grid cell, which is taller than an equal-aspect image.
    """
    bar = ax.figure.colorbar(mappable, cax=ax.inset_axes([1 + pad, 0.0, width, 1.0]), **kwargs)
    bar.set_label(label, fontsize=6, labelpad=2)
    bar.ax.tick_params(labelsize=6, length=2, width=0.5)
    bar.outline.set_linewidth(0.5)
    return bar


def scale_bar(ax, length: float, label: str, loc: str = "lower right", color: str = INK, pad: float = 0.06) -> None:
    """Scale bar of ``length`` data units in a corner of an image panel."""
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    x = max(x0, x1) - pad * dx - length if "right" in loc else min(x0, x1) + pad * dx
    y = min(y0, y1) + pad * dy if "lower" in loc else max(y0, y1) - pad * dy
    ax.plot([x, x + length], [y, y], color=color, lw=1.2, solid_capstyle="butt")
    ax.text(x + length / 2, y + 0.03 * dy * (1 if "lower" in loc else -1), label, color=color, fontsize=6, ha="center",
            va="bottom" if "lower" in loc else "top")  # fmt: skip


def image_axes(ax, xlabel: str = "", ylabel: str = "") -> None:
    """An image panel: equal aspect and all four spines, as a thin frame."""
    ax.set_aspect("equal")
    for side in ("top", "right"):
        ax.spines[side].set_visible(True)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)


def rib_outline(ax, width: float, t_core: float, t_slab: float, slab_width: float | None = None, y0: float = 0.0,
                color: str = MUTED, lw: float = 0.5) -> None:  # fmt: skip
    """Outline of a rib waveguide cross-section (y horizontal, z vertical, z = 0 at the bottom of the silicon)."""
    x0, x1 = ax.get_xlim()
    left = max(min(x0, x1), y0 - slab_width / 2) if slab_width else min(x0, x1)
    right = min(max(x0, x1), y0 + slab_width / 2) if slab_width else max(x0, x1)
    y = [left, left, y0 - width / 2, y0 - width / 2, y0 + width / 2, y0 + width / 2, right, right]
    z = [0, t_slab, t_slab, t_core, t_core, t_slab, t_slab, 0]
    ax.plot(y, z, color=color, lw=lw, solid_joinstyle="miter")
    ax.plot([left, right], [0, 0], color=color, lw=lw)
    ax.set_xlim(x0, x1)


def box(ax, y0: float, y1: float, z0: float, z1: float, facecolor="none", edgecolor: str = MUTED, lw: float = 0.5, **kwargs):
    """Rectangle in a cross-section, by its corners."""
    patch = Rectangle((min(y0, y1), min(z0, z1)), abs(y1 - y0), abs(z1 - z0), facecolor=facecolor, edgecolor=edgecolor,
                      linewidth=lw, **kwargs)  # fmt: skip
    ax.add_patch(patch)
    return patch


def note(ax, text: str, xy, xytext=None, ha: str = "left", va: str = "center", color: str = SECONDARY, **kwargs) -> None:
    """Annotation in the secondary ink; with ``xytext`` a thin leader line points at ``xy``."""
    if xytext is None:
        ax.text(*xy, text, ha=ha, va=va, color=color, fontsize=6, **kwargs)
    else:
        ax.annotate(text, xy=xy, xytext=xytext, ha=ha, va=va, color=color, fontsize=6,
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.4, shrinkA=1, shrinkB=1), **kwargs)  # fmt: skip


def triangulation(y, z, elements):
    """Triangles of a Lumerical finite-element result (its node numbers start at 1)."""
    from matplotlib.tri import Triangulation

    return Triangulation(np.asarray(y), np.asarray(z), triangles=np.asarray(elements, dtype=int) - 1)


def material_map(index: np.ndarray) -> tuple[np.ndarray, ListedColormap, list[str]]:
    """Classify a complex refractive-index map at 1550 nm into materials, for a categorical image.

    Returns the integer map, its colour map, and the material names in the order of the integers.
    """
    names = ["oxide", "silicon", "aluminium", "tin"]
    real, imag = np.real(index), np.abs(np.imag(index))
    out = np.zeros(index.shape, dtype=int)  # oxide and anything else that is transparent and low-index
    out[(imag < 0.5) & (real > 2.5)] = 1  # silicon
    out[imag > 10] = 2  # aluminium: n = 1.44 + 16i
    out[(imag >= 0.5) & (imag <= 10)] = 3  # TiN: n = 3.5 + 6.5i
    return out, ListedColormap([MATERIAL_COLORS[n] for n in names]), names
