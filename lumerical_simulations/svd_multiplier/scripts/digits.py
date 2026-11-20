"""The handwritten digits of step 4: "Optical Recognition of Handwritten Digits" of the UCI Machine Learning Repository.

E. Alpaydin and C. Kaynak, 1998, doi:10.24432/C50P49, under the Creative Commons Attribution 4.0 International licence
(CC BY 4.0).  43 people wrote the digits on a form; each digit was scanned to a 32 x 32 bitmap, and the bitmap cut
into 8 x 8 blocks of 4 x 4 pixels: every value of the 8 x 8 image counts the pixels that are set in its block, 0 to
16.  The 30 writers of the training set (3823 digits) are not among the 13 of the test set (1797 digits).

The chapter keeps the two sets in data/optdigits.npz, as they are.  fetch() makes that file again from the archive of
the repository and checks every file against the SHA-256 that this module holds.

    python digits.py --fetch      # downloads the archive (0.6 MB) and writes data/optdigits.npz again
"""

from __future__ import annotations

import argparse
import hashlib
import io
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parents[1] / "data"
KEPT = DATA / "optdigits.npz"
URL = "https://archive.ics.uci.edu/static/public/80/optical+recognition+of+handwritten+digits.zip"
SHA256 = {
    "optdigits.tra": "e1b683cc211604fe8fd8c4417e6a69f31380e0c61d4af22e93cc21e9257ffedd",
    "optdigits.tes": "6ebb3d2fee246a4e99363262ddf8a00a3c41bee6014c373ed9d9216ba7f651b8",
}
CITATION = "E. Alpaydin and C. Kaynak, Optical Recognition of Handwritten Digits, UCI Machine Learning Repository (1998), doi:10.24432/C50P49, CC BY 4.0"


def _parse(raw: bytes) -> tuple[np.ndarray, np.ndarray]:
    """Lines of 64 counts and a class, separated by commas: images (n, 8, 8) of 0 ... 16 and labels (n,)."""
    a = np.loadtxt(io.StringIO(raw.decode("ascii")), delimiter=",", dtype=np.int64)
    if a.shape[1] != 65 or a[:, :64].min() < 0 or a[:, :64].max() > 16 or set(np.unique(a[:, 64])) != set(range(10)):
        raise ValueError("not the optdigits format")
    return a[:, :64].reshape(-1, 8, 8).astype(np.uint8), a[:, 64].astype(np.uint8)


def fetch(url: str = URL) -> Path:
    """Download the archive, check its two files and write data/optdigits.npz."""
    with urllib.request.urlopen(url, timeout=120) as response:  # a fixed https address
        archive = zipfile.ZipFile(io.BytesIO(response.read()))
    sets = {}
    for name, digest in SHA256.items():
        raw = archive.read(name)
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(f"{name} is not the file this chapter was made with")
        sets[name] = _parse(raw)
    DATA.mkdir(parents=True, exist_ok=True)
    (x_train, y_train), (x_test, y_test) = sets["optdigits.tra"], sets["optdigits.tes"]
    np.savez_compressed(KEPT, x_train=x_train, y_train=y_train, x_test=x_test, y_test=y_test, source=URL, citation=CITATION)
    return KEPT


def load() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """The training and the test set: images (n, 8, 8) as counts 0 ... 16, and their digits."""
    if not KEPT.exists():
        fetch()
    d = np.load(KEPT)
    return d["x_train"], d["y_train"], d["x_test"], d["y_test"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--fetch", action="store_true", help="download the archive and write data/optdigits.npz again")
    args = parser.parse_args()
    if args.fetch:
        print(f"-> {fetch()}")
    x_train, y_train, x_test, y_test = load()
    print(f"training set {x_train.shape[0]} digits, test set {x_test.shape[0]} digits, 8 x 8, counts 0 to 16; {CITATION}")
