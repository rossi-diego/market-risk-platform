from enum import StrEnum


class Commodity(StrEnum):
    SOJA = "soja"
    MILHO = "milho"


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class PositionStatus(StrEnum):
    OPEN = "open"
    PARTIAL = "partial"
    CLOSED = "closed"
    EXPIRED = "expired"


class FixationMode(StrEnum):
    FLAT = "flat"
    CBOT = "cbot"
    CBOT_BASIS = "cbot_basis"
    BASIS = "basis"
    FX = "fx"


class CBOTInstrument(StrEnum):
    FUTURE = "future"
    SWAP = "swap"
    EUROPEAN_OPTION = "european_option"
    AMERICAN_OPTION = "american_option"
    BARRIER_OPTION = "barrier_option"


class FXInstrument(StrEnum):
    NDF = "ndf"
    SWAP = "swap"
    EUROPEAN_OPTION = "european_option"
    AMERICAN_OPTION = "american_option"
    BARRIER_OPTION = "barrier_option"


class OptionType(StrEnum):
    CALL = "call"
    PUT = "put"


class BarrierType(StrEnum):
    UP_AND_IN = "up_and_in"
    UP_AND_OUT = "up_and_out"
    DOWN_AND_IN = "down_and_in"
    DOWN_AND_OUT = "down_and_out"


class PriceSource(StrEnum):
    YFINANCE_CBOT = "YFINANCE_CBOT"
    YFINANCE_FX = "YFINANCE_FX"
    B3_OFFICIAL = "B3_OFFICIAL"
    USER_MANUAL = "USER_MANUAL"
    CBOT_PROXY_YFINANCE = "CBOT_PROXY_YFINANCE"
