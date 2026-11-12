"""Shared by the plot scripts: paths and a common look.  No Lumerical and no gdsfactory needed."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]  # lumerical_simulations/ring_modulator/
plt.rcParams.update({"figure.dpi": 130, "axes.grid": True, "grid.alpha": 0.3, "font.size": 9, "axes.titlesize": 10})


def data(step: str, name: str) -> Path:
    path = ROOT / step / name
    if not path.exists():
        raise SystemExit(f"{path} is missing: run the script of step {step[0]} first")
    return path


def save(fig, here: str, name: str) -> None:
    path = Path(here).resolve().parent / name
    fig.tight_layout()
    fig.savefig(path)
    print("plot ->", path)
