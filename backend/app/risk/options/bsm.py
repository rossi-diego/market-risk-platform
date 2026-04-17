"""Black-Scholes-Merton closed-form European option pricer.

Reference: Hull, Options Futures and Other Derivatives (2022) Ch. 13.
Accepts and returns `Decimal` at the boundary; all math is `float` internally.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from scipy.optimize import brentq
from scipy.stats import norm


@dataclass(frozen=True, slots=True)
class BSMResult:
    price: Decimal
    delta: Decimal
    gamma: Decimal
    vega: Decimal
    theta: Decimal
    rho: Decimal


def _d1_d2(s: float, k: float, t: float, r: float, sigma: float, q: float) -> tuple[float, float]:
    if t <= 0 or sigma <= 0:
        raise ValueError(f"t and sigma must be positive (got t={t}, sigma={sigma})")
    sqrt_t = math.sqrt(t)
    d1 = (math.log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    return d1, d2


def _to_float(*values: Decimal) -> tuple[float, ...]:
    return tuple(float(v) for v in values)


def bsm_price(
    S: Decimal,
    K: Decimal,
    T: Decimal,
    r: Decimal,
    sigma: Decimal,
    option_type: Literal["call", "put"],
    q: Decimal = Decimal("0"),
) -> BSMResult:
    """Closed-form BSM price + all 5 Greeks."""
    s, k, t, r_f, vol, q_f = _to_float(S, K, T, r, sigma, q)
    d1, d2 = _d1_d2(s, k, t, r_f, vol, q_f)
    sqrt_t = math.sqrt(t)
    disc_r = math.exp(-r_f * t)
    disc_q = math.exp(-q_f * t)
    pdf_d1 = float(norm.pdf(d1))

    if option_type == "call":
        price = s * disc_q * float(norm.cdf(d1)) - k * disc_r * float(norm.cdf(d2))
        delta = disc_q * float(norm.cdf(d1))
        theta = (
            -s * disc_q * pdf_d1 * vol / (2.0 * sqrt_t)
            - r_f * k * disc_r * float(norm.cdf(d2))
            + q_f * s * disc_q * float(norm.cdf(d1))
        )
        rho = k * t * disc_r * float(norm.cdf(d2))
    else:
        price = k * disc_r * float(norm.cdf(-d2)) - s * disc_q * float(norm.cdf(-d1))
        delta = -disc_q * float(norm.cdf(-d1))
        theta = (
            -s * disc_q * pdf_d1 * vol / (2.0 * sqrt_t)
            + r_f * k * disc_r * float(norm.cdf(-d2))
            - q_f * s * disc_q * float(norm.cdf(-d1))
        )
        rho = -k * t * disc_r * float(norm.cdf(-d2))

    gamma = disc_q * pdf_d1 / (s * vol * sqrt_t)
    vega = s * disc_q * pdf_d1 * sqrt_t

    return BSMResult(
        price=Decimal(str(price)),
        delta=Decimal(str(delta)),
        gamma=Decimal(str(gamma)),
        vega=Decimal(str(vega)),
        theta=Decimal(str(theta)),
        rho=Decimal(str(rho)),
    )


def implied_vol(
    S: Decimal,
    K: Decimal,
    T: Decimal,
    r: Decimal,
    market_price: Decimal,
    option_type: Literal["call", "put"],
    q: Decimal = Decimal("0"),
) -> Decimal:
    """Invert BSM on `market_price`. Raises ValueError if no root in [0.001, 5.0]."""
    target = float(market_price)

    def _f(sigma: float) -> float:
        res = bsm_price(S, K, T, r, Decimal(str(sigma)), option_type, q)
        return float(res.price) - target

    try:
        root = brentq(_f, 0.001, 5.0, maxiter=200)
    except ValueError as exc:
        raise ValueError(f"implied_vol did not converge for market_price={market_price}") from exc
    return Decimal(str(root))
