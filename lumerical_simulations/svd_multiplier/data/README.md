# Data of the real matrix multiplier

`optdigits.npz` holds the handwritten digits of step 4, as two sets of 8 × 8 images and their
digits:

| array | what it is |
|---|---|
| `x_train`, `y_train` | 3823 digits of 30 writers: images of counts 0 to 16, and the digit 0 to 9 |
| `x_test`, `y_test` | 1797 digits of 13 other writers |

**Source.** E. Alpaydin and C. Kaynak, *Optical Recognition of Handwritten Digits*, UCI Machine
Learning Repository (1998), [doi:10.24432/C50P49](https://doi.org/10.24432/C50P49). The files
`optdigits.tra` and `optdigits.tes` of the archive, unchanged apart from their format.

**Licence.** [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/)
(CC BY 4.0), as the repository states for this dataset. The licence of this cookbook does not
apply to this file.

**How it was made.** Each digit was written on a form, scanned and normalised to a 32 × 32 bitmap
with the programs of NIST. The bitmap was cut into 8 × 8 blocks of 4 × 4 pixels, and each value of
the image counts the pixels that are set in its block.

`python ../scripts/digits.py --fetch` downloads the archive from the repository again, checks
both files against their SHA-256 and writes this file anew.
