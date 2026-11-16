"""Device builders.  Each ``<device>_builder.py`` in this folder draws one device with the PDK.

    python devices/ring_modulator_builder.py      draw the device, check the design rules, write its layout

    devices/gds/<device>.gds          the layout: one flat cell, which the Layer Builder loads as it is
    build/drc/<device>.lyrdb          the DRC report, for KLayout's marker browser
    build/previews/<device>.png       a picture of the layout in the layer colours of the PDK

Every builder ends the same way, so that part lives here: ``write_device``.

    from devices import ring_modulator_builder as rm
    ring = rm.ring_modulator(radius=12, gap=0.40)
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GDS = Path(__file__).resolve().parent / "gds"
BUILD = REPO / "build"  # git-ignored: reports and previews are rebuilt by every run


def render_png(gds_path: Path, png_path: Path, box: tuple[float, float, float, float] | None = None,
               size: tuple[int, int] = (1600, 1200)) -> Path:  # fmt: skip
    """Picture of a GDS file, drawn by KLayout without a window, in the colours of klayout_tech/layers.lyp.

    box: (left, bottom, right, top) in um to zoom in; the whole layout otherwise.
    """
    import gdsfactory as gf
    import klayout.lay as lay

    import gsip_technology as t

    lyp = REPO / "klayout_tech" / "layers.lyp"
    if not lyp.exists():
        t.write_klayout_tech(lyp.parent)
    view = lay.LayoutView()
    view.load_layout(str(gds_path), True)
    view.load_layer_props(str(lyp))
    view.max_hier()
    view.zoom_box(gf.kdb.DBox(*box)) if box else view.zoom_fit()
    png_path.parent.mkdir(parents=True, exist_ok=True)
    view.save_image(str(png_path), *size)
    return png_path


def write_device(component, name: str, zoom: tuple[float, float, float, float] | None = None) -> int:
    """Write the layout of a device, check it, and draw it.  Returns 0 when the layout passes the DRC, 1 otherwise.

    name: the file name of the layout and the name of its cell, for example "ring_modulator".
    zoom: (left, bottom, right, top) in um for a second picture of the part that matters.
    """
    import gsip_technology as t
    from gsip_drc import run_drc

    gds = t.write_gds_for_lumerical(component, GDS / f"{name}.gds", cellname=name)
    print(f"GDS -> {gds.relative_to(REPO).as_posix()}   ports: {[p.name for p in component.ports]}")
    report = BUILD / "drc" / f"{name}.lyrdb"
    report.parent.mkdir(parents=True, exist_ok=True)
    result = run_drc(component, rdb_path=report)
    print(result.summary())
    render_png(gds, BUILD / "previews" / f"{name}.png")
    if zoom is not None:
        render_png(gds, BUILD / "previews" / f"{name}_zoom.png", box=zoom)
    return 0 if result.passed else 1
