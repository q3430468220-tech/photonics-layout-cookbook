"""Compile the GSiP teaching process tables into a Lumerical Layer Builder process file (.lbr).

The procedure is the one of the Ansys article "Layer builder - Simulation object" (section
"Creating a process file using Python script"), and the CSV column names are those of its template,
so the tables can be compared line by line with the Ansys example.  Where each number comes from is
documented in gsip_csv/README.md.

    1. FDTD     create the custom optical materials (dielectric_materials.csv, index_perturbation_data.csv),
                add the process layers (process_layers.csv), save the .lbr with the material data inside
    2. CHARGE   reload the .lbr, add the doping layers (doping_process_layers.csv), attach an electrical (CT)
                and a thermal (HT) model to every material (active_material_models.csv) and adjust the models
                the database does not have (material_property_overrides.csv: the TiN heater film), save again
    3. optional append process variations (pattern_variations.csv, stack_variations.csv)
    4. QA       reload the finished file and compare it with the CSV; exit code 1 on a mismatch.  It covers the
                process layers, the doping layers, the CT and HT model names, and the overridden properties with
                their model switch.  It does not read back the index-perturbation and dielectric materials
                (index_perturbation_data.csv, dielectric_materials.csv): steps 0 and 5 exercise those.

Needs a local Lumerical installation with FDTD and CHARGE licences; no GUI is opened.

    python gsip_process_file_compiler.py      ->  gsip_process.lbr next to this script

In Lumerical, load the result and a layout into a Layer Builder object:

    addlayerbuilder;  loadgdsfile("rm_ring.gds");  loadprocessfile("gsip_process.lbr");
"""

from __future__ import annotations

import csv
import re
import sys
from math import isclose
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from lumerical_env import import_lumapi  # noqa: E402

# ================================== settings ==================================
CSV_DIR = HERE / "gsip_csv"
OUTPUT_LBR = HERE / "gsip_process.lbr"

PROCESS_NAME = "gsip"  # prefix of the materials after loading, e.g. "gsip Si_np"
SIDEWALL_POSITION_REF = "middle"  # which height of a slanted sidewall the GDS edge refers to
EXPORT_MATERIALS = True  # embed the material data, so that loading does not depend on the local database

ELECTRICAL_PROCESS_FILE = True  # doping layers and CT material models (CHARGE licence)
THERMAL_PROCESS_FILE = True  # HT material models (CHARGE licence)
STATISTICAL_PROCESS_FILE = False  # append the process variations; see the README for what they are based on
QA_TEST = True

PROCESS_LAYERS_CSV = CSV_DIR / "process_layers.csv"
DOPING_CSV = CSV_DIR / "doping_process_layers.csv"
ACTIVE_MATERIAL_CSV = CSV_DIR / "active_material_models.csv"
OVERRIDES_CSV = CSV_DIR / "material_property_overrides.csv"
INDEX_PERTURBATION_CSV = CSV_DIR / "index_perturbation_data.csv"
DIELECTRIC_CSV = CSV_DIR / "dielectric_materials.csv"
PATTERN_VARIATION_CSV = CSV_DIR / "pattern_variations.csv"
STACK_VARIATION_CSV = CSV_DIR / "stack_variations.csv"
STATISTICAL_NAME = "statistical_1"
# ==============================================================================

NM = 1e-9
PREFIX = PROCESS_NAME + " "


def read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit(f"error: {path.name} has no data rows")
    return rows


def is_none(value: str) -> bool:
    return value.strip() in ("", "None", "NA")


def save_process_file(app, path: Path) -> None:
    flag = str(EXPORT_MATERIALS).lower()
    app.eval(f'saveprocessfile("{path.as_posix()}", {{"export materials": {flag}}});')


def _set_color(fdtd, name: str, row: dict[str, str]) -> None:
    rgba = [row[k] for k in ("rgba_r", "rgba_g", "rgba_b", "rgba_a")]
    if not any(is_none(c) for c in rgba):
        fdtd.setmaterial(name, "color", np.array([float(c) for c in rgba]))


# ------------------------------------------------------------------ FDTD part
def add_dielectric_materials(fdtd, rows: list[dict[str, str]]) -> None:
    """Constant-index materials that the default database lacks (here: air, for openings and trenches)."""
    for m in rows:
        name = m["name"]
        fdtd.setmaterial(fdtd.addmaterial("(n,k) Material"), "name", name)
        fdtd.setmaterial(name, "Refractive Index", float(m["refractive index"]))
        fdtd.setmaterial(name, "Imaginary Refractive Index", 0.0)
        _set_color(fdtd, name, m)


def add_index_perturbation_materials(fdtd, rows: list[dict[str, str]]) -> None:
    """Index-perturbation materials: they turn the carriers from CHARGE and the temperature from HEAT
    into a change of refractive index."""
    for m in rows:
        name = m["name"]
        fdtd.setmaterial(fdtd.addmaterial("Index perturbation"), "name", name)
        fdtd.setmaterial(name, "base material", m["base material"])

        fdtd.setmaterial(name, "include np density", int(m["include np density"]))
        if int(m["include np density"]):
            if m["np density model"] != "Soref and Bennett" or m["coefficients"].strip().lower() == "user input":
                sys.exit(f"error: material {name}: only the built-in Soref and Bennett coefficients are implemented")
            fdtd.setmaterial(name, "np density model", "Soref and Bennett")
            fdtd.setmaterial(name, "coefficients", m["coefficients"])

        fdtd.setmaterial(name, "include temperature effects", int(m["include temperature effects"]))
        if int(m["include temperature effects"]):
            if not int(m["linear sensitivity"]) or m["table of values"].strip() == "1":
                sys.exit(f"error: material {name}: only the linear temperature model is implemented")
            fdtd.setmaterial(name, "linear sensitivity", 1)
            fdtd.setmaterial(name, "Tref", float(m["Tref"]))
            fdtd.setmaterial(name, "dn/dt", float(m["dn/dt"]))
            fdtd.setmaterial(name, "dk/dt", float(m["dk/dt"]))
        _set_color(fdtd, name, m)


def add_process_layers(fdtd, rows: list[dict[str, str]], custom_materials: set[str]) -> None:
    available = set(fdtd.getmaterial().split("\n")) | custom_materials
    for r in rows:
        name = r["name"]
        for col in ("pattern_material", "background_material"):
            if not is_none(r[col]) and r[col] not in available:
                sys.exit(f"error: layer {name}: material '{r[col]}' is not in the FDTD material database")

        fdtd.addlayer(name)
        fdtd.setlayer(name, "enabled", bool(int(r["enabled"])))
        fdtd.setlayer(name, "process", r["process"])
        if not is_none(r["layer_number"]):
            fdtd.setlayer(name, "layer number", r["layer_number"])  # GDS layer or a not()/and/or/xor expression
        start = r["start_position"].strip()
        fdtd.setlayer(name, "start position", "Auto" if start == "Auto" else float(start) * NM)
        fdtd.setlayer(name, "thickness", float(r["thickness"]) * NM)
        if not is_none(r["pattern_material"]):
            fdtd.setlayer(name, "pattern material", r["pattern_material"])
        if not is_none(r["background_material"]):
            fdtd.setlayer(name, "background material", r["background_material"])
        fdtd.setlayer(name, "sidewall angle", float(r["sidewall_angle"]))
        fdtd.setlayer(name, "pattern growth delta", float(r["pattern_growth_delta"]) * NM)


# ---------------------------------------------------------------- CHARGE part
DOPING_FLOAT_KEYS = (
    "concentration",
    "z surface position",
    "range",
    "straggle",
    "skewness",
    "kurtosis",
    "lateral scatter",
    "theta",
    "phi",
)
DOPING_TEXT_KEYS = ("mask layer number", "dopant", "process", "function")


def material_model_kinds() -> list[tuple[str, str]]:
    """Model kinds to attach and their column in active_material_models.csv."""
    kinds = []
    if ELECTRICAL_PROCESS_FILE:
        kinds.append(("CT", "CT material"))
    if THERMAL_PROCESS_FILE:
        kinds.append(("HT", "HT material"))
    return kinds


def add_doping_layers(device, rows: list[dict[str, str]]) -> None:
    device.select("layer group")
    for r in rows:
        name = r["name"]
        device.adddopinglayer(name)
        device.setlayer(name, "enabled", bool(int(r["enabled"])))
        for key in DOPING_TEXT_KEYS:
            device.setlayer(name, key, r[key])
        for key in DOPING_FLOAT_KEYS:
            device.setlayer(name, key, float(r[key]))


def add_ct_ht_models(device, rows: list[dict[str, str]], lumapi) -> None:
    """Attach a CHARGE (CT) and a HEAT (HT) model to every optical material of the process file."""
    for r in rows:
        parent = f"materials::{PREFIX}{r['material']}"
        for kind, col in material_model_kinds():
            try:
                device.eval(f'select("{parent}"); addmaterialproperties("{kind}", "{r[col]}");')
            except lumapi.LumApiError:
                sys.exit(f"error: cannot attach the {kind} model '{r[col]}' to '{parent}' (unknown material or model)")


def _model_path(row: dict[str, str], active: dict[str, dict[str, str]]) -> str:
    """Path of the CT or HT model attached to a material: materials::<process material>::<model name>."""
    column = {"CT": "CT material", "HT": "HT material"}[row["model"]]
    return f"materials::{PREFIX}{row['material']}::{active[row['material']][column]}"


NO_SWITCH = ("mass density",)  # constant-only properties: they have no ".active model" switch


def has_switch(prop: str) -> bool:
    """True for a ".constant" property whose model has an ".active model" switch (every one but mass density)."""
    return prop.endswith(".constant") and not prop.startswith(NO_SWITCH)


def apply_property_overrides(device, rows: list[dict[str, str]], active_rows: list[dict[str, str]], lumapi) -> None:
    """Change single numbers of an attached model.

    The CHARGE / HEAT database has no TiN, so the heater film borrows the aluminium model and gets its own
    thermal conductivity, density, specific heat and electrical conductivity.  A property that ends in
    ".constant" also switches its model to "constant", except mass density, which has no switch.
    """
    active = {r["material"]: r for r in active_rows}
    for r in rows:
        path, prop, value = _model_path(r, active), r["property"], float(r["value"])
        try:
            device.select(path)
            if has_switch(prop):
                device.set(prop.removesuffix(".constant") + ".active model", "constant")
            device.set(prop, value)
        except lumapi.LumApiError:
            sys.exit(f"error: cannot set '{prop}' of '{path}'")


def qa_property_overrides(device, rows: list[dict[str, str]], active_rows: list[dict[str, str]]) -> int:
    """Each overridden number, and the model switch of every ".constant" property, which must read "Constant".

    The switch is compared case-insensitively.  Mass density has no switch and is not checked for one.
    """
    active = {r["material"]: r for r in active_rows}
    bad = 0
    for r in rows:
        prop = r["property"]
        device.select(_model_path(r, active))
        bad += _mismatch(r["material"], f"{r['model']} {prop}", float(r["value"]), device.get(prop))
        if has_switch(prop):
            switch = prop.removesuffix(".constant") + ".active model"
            got = str(device.get(switch))
            if got.lower() != "constant":
                print(f"  mismatch  {r['material']} / {r['model']} {switch}: CSV='Constant'  LBR={got!r}")
                bad += 1
    return bad


# ------------------------------------------------- process variations (optional)
def append_process_variation(path: Path, n_layers: int) -> None:
    """Append pattern and stack variations in the format of the Ansys template.

    Row format: name, distribution, sigma, delta, then one 0/1 flag per process layer
    (pattern: N flags for pattern_growth_delta; stack: N for thickness followed by N for start_position).
    """
    lines = ["    <process_variation>", f'        <statistical name="{STATISTICAL_NAME}">']
    with open(PATTERN_VARIATION_CSV, newline="") as f:
        for name, dist, sigma, delta, *flags in csv.reader(f):
            if len(flags) != n_layers:
                sys.exit(f"error: pattern_variations.csv row {name}: {n_layers} flags expected, {len(flags)} found")
            lines.append(
                f'            <pattern name="{name}" distribution="({dist},{sigma})" delta="{delta}" '
                f'pattern_growth_delta="{" ".join(flags)}"/>'
            )
    with open(STACK_VARIATION_CSV, newline="") as f:
        for name, dist, sigma, delta, *flags in csv.reader(f):
            if len(flags) != 2 * n_layers:
                sys.exit(f"error: stack_variations.csv row {name}: {2 * n_layers} flags expected, {len(flags)} found")
            lines.append(
                f'            <stack name="{name}" distribution="({dist},{sigma})" delta="{delta}" '
                f'thickness="{" ".join(flags[:n_layers])}" start_position="{" ".join(flags[n_layers:])}"/>'
            )
    lines += ["        </statistical>", "    </process_variation>"]

    text = path.read_text(encoding="utf-8")
    text = re.sub(r"\n\s*<revisions [^>]*/>", "", text)  # its checksum no longer matches after a manual edit
    text = text.replace("</layer_builder>", "\n".join(lines) + "\n</layer_builder>")
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------- QA
def _mismatch(layer: str, prop: str, want, got) -> int:
    if isinstance(got, str):
        got = got.removeprefix(PREFIX)
        ok = got == want or (is_none(want) and is_none(got))
    else:
        ok = isclose(float(got), float(want), rel_tol=1e-6, abs_tol=1e-15)
    if not ok:
        print(f"  mismatch  {layer} / {prop}: CSV={want!r}  LBR={got!r}")
    return 0 if ok else 1


def _layer_lookup(app) -> dict[str, str]:
    """Layer names may carry the process prefix after loading: CSV name -> actual name."""
    return {n.removeprefix(PREFIX): n for n in app.getlayer().split("\n") if n.strip()}


def qa_process_layers(fdtd, rows: list[dict[str, str]]) -> int:
    fdtd.addlayerbuilder()
    fdtd.loadprocessfile(OUTPUT_LBR.as_posix())
    actual = _layer_lookup(fdtd)
    bad = 0
    for r in rows:
        if r["name"] not in actual:
            print(f"  missing   process layer {r['name']}")
            bad += 1
            continue
        lname = actual[r["name"]]
        expect = {
            "enabled": float(r["enabled"]),
            "process": r["process"],
            "layer number": r["layer_number"],
            "thickness": float(r["thickness"]) * NM,
            "pattern material": r["pattern_material"],
            "background material": r["background_material"],
            "sidewall angle": float(r["sidewall_angle"]),
            "pattern growth delta": float(r["pattern_growth_delta"]) * NM,
        }
        if r["start_position"].strip() != "Auto":
            expect["start position"] = float(r["start_position"]) * NM
        for prop, want in expect.items():
            bad += _mismatch(r["name"], prop, want, fdtd.getlayer(lname, prop))
    return bad


def qa_doping_and_materials(device, doping_rows, active_rows) -> int:
    device.addlayerbuilder()
    device.loadprocessfile(OUTPUT_LBR.as_posix())
    actual = _layer_lookup(device)
    bad = 0
    for r in doping_rows:
        if r["name"] not in actual:
            print(f"  missing   doping layer {r['name']}")
            bad += 1
            continue
        lname = actual[r["name"]]
        bad += _mismatch(r["name"], "enabled", float(r["enabled"]), device.getlayer(lname, "enabled"))
        for key in DOPING_TEXT_KEYS:
            bad += _mismatch(r["name"], key, r[key], device.getlayer(lname, key))
        for key in DOPING_FLOAT_KEYS:
            bad += _mismatch(r["name"], key, float(r[key]), device.getlayer(lname, key))

    for r in active_rows:
        parent = f"materials::{PREFIX}{r['material']}"
        device.eval(
            f'groupscope("{parent}"); selectall; n = getnumber; s = ""; '
            f'for (i = 1:n) {{ s = s + get("name", i) + "\\n"; }} groupscope("::model");'
        )
        children = device.getv("s").split("\n")
        for kind, col in material_model_kinds():
            if r[col] not in children:
                print(f"  missing   {kind} model {r[col]!r} of material {r['material']}; found {children}")
                bad += 1
    return bad


# -------------------------------------------------------------------- main
def main() -> None:
    lumapi = import_lumapi()
    process_rows = read_csv(PROCESS_LAYERS_CSV)
    ip_rows = read_csv(INDEX_PERTURBATION_CSV)
    dielectric_rows = read_csv(DIELECTRIC_CSV)
    doping_rows = read_csv(DOPING_CSV) if ELECTRICAL_PROCESS_FILE else []
    active_rows = read_csv(ACTIVE_MATERIAL_CSV) if (ELECTRICAL_PROCESS_FILE or THERMAL_PROCESS_FILE) else []
    kinds = {kind for kind, _ in material_model_kinds()}
    override_rows = [r for r in read_csv(OVERRIDES_CSV) if r["model"] in kinds] if active_rows else []

    with lumapi.FDTD(hide=True) as fdtd:
        add_dielectric_materials(fdtd, dielectric_rows)
        add_index_perturbation_materials(fdtd, ip_rows)
        fdtd.addlayerbuilder()
        fdtd.set("process name", PROCESS_NAME)
        fdtd.set("GDS sidewall angle position reference", SIDEWALL_POSITION_REF)
        add_process_layers(fdtd, process_rows, {m["name"] for m in ip_rows + dielectric_rows})
        save_process_file(fdtd, OUTPUT_LBR)
    print(
        f"[FDTD]   {len(process_rows)} process layers, {len(ip_rows) + len(dielectric_rows)} custom materials -> {OUTPUT_LBR.name}"
    )

    if active_rows:
        with lumapi.DEVICE(hide=True) as device:
            device.addlayerbuilder()
            device.loadprocessfile(OUTPUT_LBR.as_posix())
            if doping_rows:
                add_doping_layers(device, doping_rows)
            add_ct_ht_models(device, active_rows, lumapi)
            apply_property_overrides(device, override_rows, active_rows, lumapi)
            device.select("layer group")
            save_process_file(device, OUTPUT_LBR)
        print(
            f"[CHARGE] {len(doping_rows)} doping layers, CT/HT models of {len(active_rows)} materials, "
            f"{len(override_rows)} adjusted properties -> {OUTPUT_LBR.name}"
        )

    if STATISTICAL_PROCESS_FILE:
        append_process_variation(OUTPUT_LBR, len(process_rows))
        print(f"[XML]    appended <process_variation> ({STATISTICAL_NAME})")

    if QA_TEST:
        print("[QA]     reloading and comparing with the CSV tables ...")
        with lumapi.FDTD(hide=True) as fdtd:
            bad = qa_process_layers(fdtd, process_rows)
        if active_rows:
            with lumapi.DEVICE(hide=True) as device:
                bad += qa_doping_and_materials(device, doping_rows, active_rows)
                bad += qa_property_overrides(device, override_rows, active_rows)
        if bad:
            sys.exit(f"[QA]     {bad} mismatches")
        print("[QA]     everything matches")

    print(f"done: {OUTPUT_LBR}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
