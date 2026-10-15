"""Stage 4: what recent municipal elections can and cannot tell us (small-n, non-random sample).

Data: s4_local_swing_panel (SQL). Each row is a municipality; the outcome is the change, in percentage points, between
the baseline national-election share of the electoral families that formed the local lead coalition and the local lead
list share. Results are fully enumerated counts, not survey samples, so unit-level sampling variance is ~0 and the
spread across municipalities is real heterogeneity (plus proxy-construction error that cannot be separated out).

Method recommended for THIS data (and why the heavier options are not used):
  * Hierarchical normal model  y_i = mu + u_i, u_i ~ N(0, tau^2), Jeffreys prior on (mu, tau^2) => closed-form Student-t
    posterior and predictive. With ~9 municipalities, a full Bayesian hierarchical regression with covariates, a
    difference-in-differences design or an event-study would be over-parameterised or unidentified:
      - DiD / event study needs municipalities WITHOUT a local election observed AFTER the baseline in the same outcome.
        The package has none, so the "effect of holding a local election" is not identified.
      - partial pooling of individual municipalities needs a per-unit measurement variance; enumerated results give ~0,
        so observed municipalities keep their own values; pooling matters only for PREDICTING unobserved municipalities.
  * Descriptive association of swing with turnout change (OLS, leave-one-out) to expose how fragile it is.
The estimates are an input to scenario analysis (a transfer coefficient alpha in [0, 1] that is NOT identified), never a
substitute for parliamentary vote shares.
"""
import numpy as np
from scipy import stats


def t_summary(y, weights=None, levels=(0.8, 0.95)):
    """Posterior of the mean and posterior predictive for a NEW municipality (Normal model, Jeffreys prior)."""
    y = np.asarray(y, float)
    keep = np.isfinite(y)
    yy = y[keep]
    n = len(yy)
    if n < 3:
        raise ValueError('need at least 3 municipalities for a t-based summary')
    m, s = yy.mean(), yy.std(ddof=1)
    out = {'n': n, 'mean': float(m), 'sd_between': float(s), 'median': float(np.median(yy))}
    for lv in levels:
        q = stats.t.ppf(0.5 + lv / 2, n - 1)
        out[f'mean_ci_{int(lv*100)}'] = (float(m - q * s / np.sqrt(n)), float(m + q * s / np.sqrt(n)))
        out[f'predictive_{int(lv*100)}'] = (float(m - q * s * np.sqrt(1 + 1 / n)), float(m + q * s * np.sqrt(1 + 1 / n)))
    if weights is not None:
        out['register_weighted_mean'] = float(np.average(yy, weights=np.asarray(weights, float)[keep]))
    return out


def predictive_draws(y, n_draws, rng):
    """Draws from the Student-t posterior predictive for a new municipality (for Monte Carlo)."""
    y = np.asarray(y, float)
    y = y[np.isfinite(y)]
    n = len(y)
    m, s = y.mean(), y.std(ddof=1)
    return m + s * np.sqrt(1 + 1 / n) * rng.standard_t(n - 1, size=n_draws)


def association(y, x):
    """OLS of y on x with t-based CI for the slope, Spearman rho, and the leave-one-out range of slopes."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    ok = np.isfinite(y) & np.isfinite(x)
    y, x = y[ok], x[ok]
    n = len(y)
    res = stats.linregress(x, y)
    q = stats.t.ppf(0.975, n - 2)
    loo = [stats.linregress(np.delete(x, i), np.delete(y, i)).slope for i in range(n)]
    rho = stats.spearmanr(x, y)
    return {'n': n, 'slope': float(res.slope), 'slope_ci95': (float(res.slope - q * res.stderr), float(res.slope + q * res.stderr)),
            'intercept': float(res.intercept), 'r2': float(res.rvalue ** 2), 'p_value': float(res.pvalue),
            'spearman_rho': float(rho.statistic), 'loo_slope_min': float(min(loo)), 'loo_slope_max': float(max(loo))}


def time_weight(months_since, half_life_months):
    """Exponential time decay for local information (a SCENARIO choice: the data contain only two distinct ages)."""
    return 0.5 ** (np.asarray(months_since, float) / half_life_months)


def eb_random_effects(y, se):
    """REML estimate of (mu, tau^2) when per-unit measurement standard errors `se` are KNOWN. Provided for the day
    such errors exist (e.g. survey-based local estimates); not used on enumerated results where se ~ 0."""
    from scipy.optimize import minimize_scalar
    y, se = np.asarray(y, float), np.asarray(se, float)

    def nll(t2):
        v = se ** 2 + t2
        w = 1 / v
        mu = (w * y).sum() / w.sum()
        return 0.5 * (np.log(v).sum() + np.log(w.sum()) + (w * (y - mu) ** 2).sum())
    r = minimize_scalar(nll, bounds=(0.0, 1e4), method='bounded')
    t2 = float(r.x)
    w = 1 / (se ** 2 + t2)
    mu = float((w * y).sum() / w.sum())
    shrink = se ** 2 / (se ** 2 + t2)
    return {'mu': mu, 'tau2': t2, 'mu_se': float(np.sqrt(1 / w.sum())), 'posterior_unit_means': shrink * mu + (1 - shrink) * y,
            'shrinkage_factor': shrink}
