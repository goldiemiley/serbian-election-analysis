"""Stages 2-3: municipality-level turnout and calibration to national participation scenarios.

Observed inputs come from s2_unit_panel (SQL). Scenario inputs (national participating voters) come from cfg_parameters.
Nothing here contains an electoral observation.

Why a calibrated shift and not "scale everybody by the same factor"?
  * Turnout is a rate in [0, 1]; a uniform multiplicative scaling pushes high-turnout units above 1 and gives the
    same absolute increase to units that are almost saturated.
  * The logit shift lets every unit move by the same *log-odds* amount, so units close to saturation move little in
    percentage points and units with low turnout move more. This is a modelling choice, not an estimate: with a single
    national election that has turnout totals, the cross-sectional pattern of turnout *change* is not identified.
    The pipeline therefore runs the alternatives below and reports the spread between them.

Allocation methods for the additional participants (all calibrated to the same national total):
  logit_shift      r_i = expit(logit(r0_i) + delta)
  abstainer_share  r_i = r0_i + k (1 - r0_i)   (target above baseline)  /  r0_i (1 - k)  (target below baseline)
  proportional     r_i = min(1, c r0_i)
"""
import numpy as np
from scipy.optimize import brentq
from scipy.special import expit, logit

METHODS = ('logit_shift', 'abstainer_share', 'proportional')
_EPS = 1e-9


def _clip(r):
    return np.clip(np.asarray(r, float), _EPS, 1 - _EPS)


def _rate_given(method, r0, param):
    if method == 'logit_shift':
        return expit(logit(_clip(r0)) + param)
    if method == 'abstainer_share':
        return r0 + param * (1 - r0) if param >= 0 else r0 * (1 + param)
    if method == 'proportional':
        return np.minimum(1.0, param * r0)
    raise ValueError(f'method must be one of {METHODS}, got {method!r}')


def _bracket(method):
    return {'logit_shift': (-12.0, 12.0), 'abstainer_share': (-1.0, 1.0), 'proportional': (0.0, 1.0 / _EPS)}[method]


def calibrate(registered, base_rate, target_voters, fixed=None, method='logit_shift', return_param=False):
    """Unit turnout rates whose weighted sum equals `target_voters` exactly (to solver tolerance).

    registered     register assumed for the target election (per unit)
    base_rate      baseline turnout rate (per unit)
    fixed          boolean mask: units whose RATE is held at baseline (their voters still scale with their register)
    """
    registered = np.asarray(registered, float)
    r0 = np.asarray(base_rate, float)
    fixed = np.zeros(len(r0), bool) if fixed is None else np.asarray(fixed, bool)

    def total(p):
        r = np.where(fixed, r0, _rate_given(method, r0, p))
        return float((registered * r).sum())

    lo, hi = _bracket(method)
    if method == 'proportional':
        hi = 1.0 / max(r0[~fixed].min(), 1e-6) + 1.0   # enough to saturate every free unit
    f_lo, f_hi = total(lo) - target_voters, total(hi) - target_voters
    if f_lo > 0 or f_hi < 0:
        raise ValueError(f'target {target_voters:,.0f} is outside the feasible range [{total(lo):,.0f}, {total(hi):,.0f}] '
                         f'for method {method}')
    p = brentq(lambda x: total(x) - target_voters, lo, hi, xtol=1e-12, rtol=1e-12, maxiter=500)
    r = np.where(fixed, r0, _rate_given(method, r0, p))
    return (r, p) if return_param else r


def estimate_unit_sd(valid_ratio, weights, free):
    """Robust SD of unit-level log changes in valid votes between the two latest national elections, after removing
    the weighted national mean. An EMPIRICAL REFERENCE for unit-level turnout dispersion: it mixes turnout change with
    register and boundary changes, so it is not a clean turnout estimate. Returns (sd, n_units, weighted_mean_log)."""
    x = np.log(np.asarray(valid_ratio, float))
    w = np.asarray(weights, float)
    m = np.asarray(free, bool) & np.isfinite(x) & (w > 0)
    mu = np.average(x[m], weights=w[m])
    resid = x[m] - mu
    mad = np.median(np.abs(resid - np.median(resid)))
    return float(1.4826 * mad), int(m.sum()), float(mu)


def simulate_calibrated(registered, base_rate, targets, sigma, fixed=None, method='logit_shift', rng=None):
    """Draw unit turnout rates with idiosyncratic logit noise and re-calibrate EACH draw to its own national target.

    targets  array of national participating voters (one per draw)
    sigma    SD of the unit-level logit shock (>= 0); 0 reproduces `calibrate`
    Returns an array (n_draws, n_units) of rates. Fixed units receive no shock.
    """
    registered = np.asarray(registered, float)
    r0 = np.asarray(base_rate, float)
    fixed = np.zeros(len(r0), bool) if fixed is None else np.asarray(fixed, bool)
    targets = np.asarray(targets, float)
    rng = np.random.default_rng() if rng is None else rng
    n_draws, n = len(targets), len(r0)
    eps = rng.normal(0.0, sigma, size=(n_draws, n)) * (~fixed)
    base_logit = logit(_clip(r0))
    out = np.empty((n_draws, n))
    for d in range(n_draws):      # per-draw scalar solve: robust, 192 units, fast enough
        z = base_logit + eps[d]

        def tot(delta, z=z):
            r = np.where(fixed, r0, expit(z + delta))
            return float((registered * r).sum())
        lo, hi = -12.0, 12.0
        if tot(lo) > targets[d] or tot(hi) < targets[d]:
            raise ValueError(f'draw {d}: target {targets[d]:,.0f} infeasible')
        delta = brentq(lambda x: tot(x) - targets[d], lo, hi, xtol=1e-11)
        out[d] = np.where(fixed, r0, expit(z + delta))
    return out


def ballots_and_valid(voters, ballots_per_turned_out, invalid_rate, invalid_rate_multiplier=1.0):
    """Turn participating voters into ballots cast, invalid and valid ballots using the unit's baseline ratios.
    invalid_rate_multiplier is a SCENARIO parameter (default 1 = unit baseline invalid rate)."""
    voters = np.asarray(voters, float)
    ballots = voters * np.asarray(ballots_per_turned_out, float)
    inv = ballots * np.minimum(1.0, np.asarray(invalid_rate, float) * invalid_rate_multiplier)
    return ballots, inv, ballots - inv


def national_denominators(voters, ballots, valid):
    """The three candidate bases for the 3% threshold (the pipeline reports all of them)."""
    return {'voters_turned_out': float(np.sum(voters)), 'ballots_cast': float(np.sum(ballots)),
            'valid_ballots': float(np.sum(valid))}
