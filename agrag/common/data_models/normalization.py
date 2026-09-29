"""The Normalization model: how a loader turned source bytes into text."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Normalization(BaseModel):
    """How a loader turned source bytes into ``Document.text``.

    Provenance offsets index the normalized text. A caller who needs offsets into
    the raw source chooses ``Normalization(bom="keep", newline="keep",
    unicode_form="none")``.

    Attributes:
        bom: ``"strip"`` removes a leading byte-order mark. ``"keep"`` leaves it.
        newline: ``"lf"`` turns CRLF and CR into LF. ``"keep"`` leaves them.
        unicode_form: The Unicode normalization form to apply, or ``"none"``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    bom: Literal["strip", "keep"] = "strip"
    newline: Literal["lf", "keep"] = "lf"
    unicode_form: Literal["NFKC", "NFC", "NFD", "NFKD", "none"] = "NFKC"
