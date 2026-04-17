# ruff: noqa: UP040
# PEP 604 `type` aliases not yet supported by the pinned pre-commit mypy,
# so we keep the TypeAlias form for toolchain compatibility.
from typing import Literal, TypeAlias

LiteralCommodity: TypeAlias = Literal["soja", "milho"]
LiteralSide: TypeAlias = Literal["buy", "sell"]
LiteralPositionStatus: TypeAlias = Literal["open", "partial", "closed", "expired"]
LiteralFixationMode: TypeAlias = Literal["flat", "cbot", "cbot_basis", "basis", "fx"]
LiteralCBOTInstrument: TypeAlias = Literal[
    "future", "swap", "european_option", "american_option", "barrier_option"
]
LiteralFXInstrument: TypeAlias = Literal[
    "ndf", "swap", "european_option", "american_option", "barrier_option"
]
LiteralOptionType: TypeAlias = Literal["call", "put"]
LiteralBarrierType: TypeAlias = Literal["up_and_in", "up_and_out", "down_and_in", "down_and_out"]
LiteralPriceSource: TypeAlias = Literal[
    "YFINANCE_CBOT", "YFINANCE_FX", "B3_OFFICIAL", "USER_MANUAL", "CBOT_PROXY_YFINANCE"
]
