"""Cox-Ross-Rubinstein binomial tree for American option pricing.

Greeks via finite-difference bumps on the tree output: central for delta and
gamma, forward in T for theta. Reference: Hull (2022) Ch. 21.
"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Literal

import numpy as np

from app.risk.options.bsm import BSMResult


def _crr_price_american(
    s: float,
    k: float,
    t: float,
    r: float,
    sigma: float,
    q: float,
    option_type: Literal["call", "put"],
    n_steps: int,
) -> float:
    dt = t / n_steps
    u = math.exp(sigma * math.sqrt(dt))
    d = 1.0 / u
    p = (math.exp((r - q) * dt) - d) / (u - d)
    disc = math.exp(-r * dt)

    # Terminal node asset prices: S*u^j * d^(n-j) for j=0..n
    j_terminal = np.arange(n_steps + 1)
    prices = s * (u**j_terminal) * (d ** (n_steps - j_terminal))

    values = np.maximum(prices - k, 0.0) if option_type == "call" else np.maximum(k - prices, 0.0)

    for step in range(n_steps - 1, -1, -1):
        # Discounted risk-neutral expectation
        values = disc * (p * values[1 : step + 2] + (1 - p) * values[: step + 1])
        # Recompute node prices at time `step`: S*u^j*d^(step-j) for j=0..step
        j_step = np.arange(step + 1)
        prices_at_step = s * (u**j_step) * (d ** (step - j_step))
        # American early-exercise check
        if option_type == "call":
            intrinsic = np.maximum(prices_at_step - k, 0.0)
        else:
            intrinsic = np.maximum(k - prices_at_step, 0.0)
        values = np.maximum(values, intrinsic)
    return float(values[0])


def crr_american(
    S: Decimal,
    K: Decimal,
    T: Decimal,
    r: Decimal,
    sigma: Decimal,
    option_type: Literal["call", "put"],
    q: Decimal = Decimal("0"),
    n_steps: int = 500,
) -> BSMResult:
    """American option via CRR tree + bump-revalue Greeks."""
    s = float(S)
    k = float(K)
    t = float(T)
    r_f = float(r)
    vol = float(sigma)
    q_f = float(q)

    price = _crr_price_american(s, k, t, r_f, vol, q_f, option_type, n_steps)

    # Bumps — keep small enough for stability, large enough to avoid noise
    h_s = max(s * 0.01, 0.01)
    h_sigma = 0.01
    h_t = min(0.01, max(t * 0.01, 1e-4))
    h_r = 0.0001

    price_up = _crr_price_american(s + h_s, k, t, r_f, vol, q_f, option_type, n_steps)
    price_dn = _crr_price_american(s - h_s, k, t, r_f, vol, q_f, option_type, n_steps)
    delta = (price_up - price_dn) / (2 * h_s)
    gamma = (price_up - 2 * price + price_dn) / (h_s**2)

    price_vega_up = _crr_price_american(s, k, t, r_f, vol + h_sigma, q_f, option_type, n_steps)
    vega = (price_vega_up - price) / h_sigma

    price_theta_fwd = _crr_price_american(
        s, k, max(t - h_t, 1e-6), r_f, vol, q_f, option_type, n_steps
    )
    theta = (price_theta_fwd - price) / (-h_t)  # dV/dt is negative for long options

    price_rho_up = _crr_price_american(s, k, t, r_f + h_r, vol, q_f, option_type, n_steps)
    rho = (price_rho_up - price) / h_r

    return BSMResult(
        price=Decimal(str(price)),
        delta=Decimal(str(delta)),
        gamma=Decimal(str(gamma)),
        vega=Decimal(str(vega)),
        theta=Decimal(str(theta)),
        rho=Decimal(str(rho)),
    )
