"""Stage 13: charts (matplotlib, PNG). Colours are a colour-blind-safe categorical palette assigned by list ORDER, not by
party identity (neutral presentation). Every chart title says what the interval is."""
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

PALETTE = ['#0072B2', '#D55E00', '#009E73', '#CC79A7', '#E69F00', '#56B4E9', '#999999', '#F0E442', '#332288', '#117733']
plt.rcParams.update({'figure.dpi': 110, 'savefig.dpi': 140, 'axes.spines.top': False, 'axes.spines.right': False, 'font.size': 9})


def _color(model, k):
    return PALETTE[model.keys.index(k) % len(PALETTE)]


def _short(model, k, width=44):
    s = model.names.get(k, k)
    return s if len(s) <= width else s[:width - 1] + '…'


def _save(fig, out, name, files, desc, stage):
    fig.tight_layout()
    fig.savefig(out / name)
    plt.close(fig)
    files[name] = (stage, desc)


def chart_national(model, tab, out, files):
    d = tab[tab.share_median >= 0.008].sort_values('share_median')
    fig, ax = plt.subplots(figsize=(8, 0.38 * len(d) + 1.6))
    y = np.arange(len(d))
    ax.hlines(y, d.share_lo80, d.share_hi80, color='#444444', lw=3, alpha=0.5, label='80% interval')
    ax.hlines(y, d.share_lo95, d.share_hi95, color='#444444', lw=1, label='95% interval')
    ax.scatter(d.share_median, y, color=[_color(model, k) for k in d.list_key], zorder=3, s=36)
    ax.set_yticks(y)
    ax.set_yticklabels([_short(model, k) for k in d.list_key])
    thr = model.P['threshold_share']
    ax.axvline(thr, color='k', ls=':', lw=1)
    ax.text(thr + 0.004, 0.2, '3% of valid votes (the statutory base differs: see threshold chart)', fontsize=7, va='bottom')
    ax.set_xlabel('share of valid votes (median, Monte Carlo intervals)')
    ax.set_title('National vote shares: scenario- and prior-conditional forecast')
    ax.legend(loc='lower right', fontsize=7)
    _save(fig, out, 'fig_A_national_shares.png', files, 'A. National vote shares with 80% and 95% intervals', 'Stage 13')


def chart_seats(model, draws, seat_res, out, files):
    keys = draws['keys']
    show = model.polled[:3] if len(model.polled) >= 3 else model.polled
    fig, ax = plt.subplots(figsize=(8, 4))
    for k in show:
        s = seat_res['seats'][:, keys.index(k)]
        ax.hist(s, bins=np.arange(0, s.max() + 2) - 0.5, alpha=0.5, color=_color(model, k), label=_short(model, k, 28), density=True)
    ax.axvline(model.P['majority_seats'], color='k', ls='--', lw=1)
    ax.text(model.P['majority_seats'], ax.get_ylim()[1] * 0.95, f" majority ({model.P['majority_seats']})", fontsize=8, va='top')
    ax.set_xlabel('seats')
    ax.set_ylabel('probability density across draws')
    ax.set_title('Seat distributions of the largest lists and the near-threshold list (spike at 0 = misses the threshold)')
    ax.legend(fontsize=7)
    _save(fig, out, 'fig_B_seat_distributions.png', files, 'B. Seat distributions', 'Stage 13')


def chart_threshold(model, thr, out, files):
    focus = model.P.list('threshold_focus_list_keys')
    d = thr[thr.list_key.isin(focus)].copy()
    d['combo'] = d.threshold_denominator.str.replace('_', ' ') + '\n' + d.uplift_scope.str.replace('_', ' ')
    piv = d.pivot_table(index='combo', columns='list_key', values='p_takes_part')
    fig, ax = plt.subplots(figsize=(8, 4))
    w = 0.8 / len(piv.columns)
    for i, k in enumerate(piv.columns):
        ax.bar(np.arange(len(piv)) + i * w, piv[k], w, label=_short(model, k, 28), color=_color(model, k))
    ax.set_xticks(np.arange(len(piv)) + 0.4 - w / 2)
    ax.set_xticklabels(piv.index, fontsize=7)
    ax.set_ylabel('probability of taking part in the allocation')
    ax.set_ylim(0, 1)
    ax.set_title('Threshold sensitivity: base of the 3% rule x scope of the minority uplift (same draws)')
    ax.legend(fontsize=7)
    _save(fig, out, 'fig_B_threshold_sensitivity.png', files, 'B. Threshold sensitivity', 'Stage 13')


def chart_coalitions(per, out, files):
    d = per.sort_values('p_majority')
    cols = {'all': PALETTE[6], 'incumbent_anchored': PALETTE[1], 'student_anchored': PALETTE[0]}
    fig, ax = plt.subplots(figsize=(8, 0.45 * len(d) + 1.4))
    ax.barh(d.coalition_id + '  ' + d.coalition_name.str.slice(0, 54), d.p_majority, color=[cols.get(s, PALETTE[2]) for s in d.assumption_set])
    ax.set_xlim(0, 1)
    ax.set_xlabel('probability of at least 126 seats')
    ax.set_title('Coalition arithmetic (compatibility is an analyst assumption, not a forecast of agreement)')
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=v, label=k.replace('_', ' ')) for k, v in cols.items()], fontsize=7, loc='lower right')
    _save(fig, out, 'fig_C_coalitions.png', files, 'C. Majority probability by coalition', 'Stage 13')


def chart_scenarios(model, scen, out, files):
    ref, stu = model.ref, model.P['student_list_key']
    d = scen.copy().iloc[::-1]
    fig, axes = plt.subplots(1, 2, figsize=(11, 0.34 * len(d) + 1.6), sharey=True)
    y = np.arange(len(d))
    axes[0].scatter(d[f'share_median__{ref}'], y, color=_color(model, ref), label=_short(model, ref, 24))
    axes[0].scatter(d[f'share_median__{stu}'], y, color=_color(model, stu), label=_short(model, stu, 24))
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(d.scenario, fontsize=7)
    axes[0].set_xlabel('median share of valid votes')
    axes[0].legend(fontsize=7)
    axes[1].scatter(d.p_incumbent_anchored_majority, y, color=_color(model, ref), marker='s', label='incumbent-anchored coalition majority')
    axes[1].scatter(d.p_student_anchored_majority, y, color=_color(model, stu), marker='s', label='student-anchored coalition majority')
    axes[1].set_xlim(0, 1)
    axes[1].set_xlabel('probability')
    axes[1].legend(fontsize=7, loc='lower right')
    fig.suptitle('Scenario comparison (same random numbers across scenarios)')
    _save(fig, out, 'fig_E_scenarios.png', files, 'E. Scenario comparison', 'Stage 13')


def chart_sweeps(model, sweeps, out, files):
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    for k, g in sweeps.groupby('list_key', sort=False):
        axes[0].plot(100 * g.share_median, g.p_takes_part, marker='o', color=_color(model, k), label=_short(model, k, 28))
        axes[1].plot(100 * g.share_median, g.p_incumbent_anchored_majority, marker='o', ls='-', color=_color(model, k))
        axes[1].plot(100 * g.share_median, g.p_student_anchored_majority, marker='s', ls='--', color=_color(model, k))
    axes[0].axvline(100 * model.P['threshold_share'], color='k', ls=':')
    axes[0].set_xlabel('median share of valid votes of the swept list (%)')
    axes[0].set_ylabel('P(takes part in allocation)')
    axes[0].legend(fontsize=7)
    axes[1].set_xlabel('median share of the swept list (%)')
    axes[1].set_ylabel('P(coalition majority)')
    axes[1].text(0.02, 0.02, 'solid: incumbent-anchored, dashed: student-anchored', transform=axes[1].transAxes, fontsize=7)
    fig.suptitle('Threshold sweeps: shifting one near-threshold list at a time (illustrative)')
    _save(fig, out, 'fig_E_threshold_sweeps.png', files, 'E. Threshold sweeps', 'Stage 13')


def chart_municipal(model, units_base, out, files):
    u, long, turn = units_base
    ref, stu = model.ref, model.P['student_list_key']
    keep = turn.loc[~turn.low_count_flag, 'geo_id']
    a = long[(long.list_key == ref) & long.geo_id.isin(keep)].set_index('geo_id')
    b = long[(long.list_key == stu) & long.geo_id.isin(keep)].set_index('geo_id')
    t = turn[turn.geo_id.isin(keep)].set_index('geo_id')
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    reg = t.region_id.fillna('special')
    cmap = plt.get_cmap('Set2')
    codes = {r: cmap(i % 8) for i, r in enumerate(sorted(reg.unique()))}
    axes[0].scatter(a.share_mean, b.share_mean, s=t.registered_2026 / 1500, c=[codes[r] for r in reg.reindex(a.index)], alpha=0.7, edgecolor='k', lw=0.3)
    lim = [0, max(a.share_mean.max(), b.share_mean.max()) * 1.05]
    axes[0].plot(lim, lim, 'k:', lw=1)
    axes[0].set_xlabel(f'expected share: {_short(model, ref, 26)}')
    axes[0].set_ylabel(f'expected share: {_short(model, stu, 26)}')
    axes[0].set_title('Municipal expected shares (size = register; dotted = equal;\nunits with very few votes omitted)', fontsize=9)
    from matplotlib.lines import Line2D
    axes[0].legend(handles=[Line2D([], [], marker='o', ls='', color=c, label=r) for r, c in codes.items()], fontsize=7, title='region_id', title_fontsize=7)
    axes[1].scatter(t.turnout_baseline, t.turnout_mean, s=10, c=[codes[r] for r in reg], alpha=0.8)
    axes[1].plot([0, 1], [0, 1], 'k:', lw=1)
    axes[1].set_xlabel('turnout 2023 (observed)')
    axes[1].set_ylabel('turnout 2026 scenario (mean)')
    axes[1].set_title('Unit turnout: calibrated to the national scenario range')
    _save(fig, out, 'fig_D_municipal.png', files, 'D. Municipal expected shares and turnout', 'Stage 13')


def chart_polls(model, out, files):
    pl = model.poll
    import polls as PO
    obs, _ = PO.prepare_log_ratios(model.polls_panel, model.ref, model.targets, default_sample=model.P['poll_default_sample'],
                                   design_effect=model.P['poll_design_effect'])
    houses = sorted({o['house'] for o in obs})
    fig, ax = plt.subplots(figsize=(8, 4))
    for i, h in enumerate(houses):
        pts = [(o['date'], o['y'][o['idx'].index(0)]) for o in obs if o['house'] == h and 0 in o['idx']]
        if pts:
            ax.scatter(*zip(*pts), color=PALETTE[i % len(PALETTE)], label=h[:30], s=40)
    m, sd = pl['mean'][0], np.sqrt(pl['cov'][0, 0])
    ax.errorbar([model.election_date], [m], yerr=[1.28 * sd], fmt='D', color='k', capsize=4, label='posterior at election (80%)')
    ax.axhline(0, color='k', ls=':', lw=1)
    ax.set_ylabel(f'log({_short(model, model.targets[0], 20)} / {_short(model, model.ref, 20)})')
    ax.set_title('Polls (individual points) and the aggregate: pollster effects are NOT removed from the points')
    ax.legend(fontsize=7)
    fig.autofmt_xdate()
    _save(fig, out, 'fig_5_polls.png', files, 'Polls vs aggregate', 'Stage 13')


def chart_backtest(bt, out, files):
    d = bt['b1']
    d = d[d.family.str.startswith('ALL')]
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    ax.bar(d.method.str.replace('_', ' '), d.mae_pp, color=PALETTE[:len(d)])
    ax.set_ylabel('mean absolute error of unit shares (pp)')
    ax.set_title('Backtest 2022->2023 (known national margins): downscaling methods')
    plt.setp(ax.get_xticklabels(), fontsize=7, rotation=10)
    _save(fig, out, 'fig_12_backtest.png', files, 'Backtest of downscaling methods', 'Stage 12')


def chart_outcomes(model, tab, per, form, out, files):
    ref, stu = model.ref, model.P['student_list_key']
    t = tab.set_index('list_key')
    f = form.set_index('event').probability
    rows = [(f'{_short(model, ref, 26)}: most votes', t.loc[ref, 'p_most_votes']),
            (f'{_short(model, stu, 26)}: most votes', t.loc[stu, 'p_most_votes']),
            (f'{_short(model, ref, 26)}: most seats', per.set_index('coalition_id').p_anchor_largest_list.iloc[0]),
            ('incumbent-anchored coalition: majority', f['incumbent-anchored coalition has a majority']),
            ('student-anchored coalition: majority', f['student-anchored coalition has a majority']),
            ('only incumbent-anchored has a majority', f['only an incumbent-anchored coalition has a majority']),
            ('only student-anchored has a majority', f['only a student-anchored coalition has a majority']),
            ('both kinds have a majority', f['both kinds have a majority (order of invitation not modelled)'])]
    for k in model.P.list('threshold_focus_list_keys'):
        rows.append((f'{_short(model, k, 30)}: takes part (>= 3%)', t.loc[k, 'p_takes_part_in_allocation']))
    d = pd.DataFrame(rows, columns=['outcome', 'p']).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(d) + 1.3))
    ax.barh(d.outcome, d.p, color=PALETTE[6])
    for y, v in enumerate(d.p):
        ax.text(v + 0.01, y, f'{v:.0%}', va='center', fontsize=8)
    ax.set_xlim(0, 1.08)
    ax.set_xlabel('probability across Monte Carlo draws')
    ax.set_title('Probability of each electoral outcome (scenario- and prior-conditional)')
    _save(fig, out, 'fig_F_outcome_probabilities.png', files, 'F. Probability of each electoral outcome', 'Stage 13')


def chart_turnout_sensitivity(model, scen, out, files):
    names = ['turnout_low_end', 'baseline', 'turnout_high_end'] + [n for n in scen.scenario if n.startswith('turnout_') and n not in ('turnout_low_end', 'turnout_high_end')]
    d = scen[scen.scenario.isin(names)].copy()
    d['mid'] = d.description.str.extract(r'([\d,]+)')[0].str.replace(',', '').astype(float)
    d = d.sort_values('mid')
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    ax.plot(d.mid / 1e6, d.p_incumbent_anchored_majority, marker='s', color=_color(model, model.ref), label='incumbent-anchored coalition majority')
    ax.plot(d.mid / 1e6, d.p_student_anchored_majority, marker='s', color=_color(model, model.P['student_list_key']), label='student-anchored coalition majority')
    ax.set_xlabel('participating voters in the scenario (millions; user-specified range plus shifted ranges)')
    ax.set_ylabel('probability')
    ax.set_ylim(0, 1)
    ax.set_title('Turnout sensitivity: polls give SHARES, so turnout acts through minority lists and the closure only')
    ax.title.set_fontsize(9)
    ax.legend(fontsize=7)
    _save(fig, out, 'fig_F_turnout_sensitivity.png', files, 'F. Turnout sensitivity', 'Stage 13')


def chart_municipal_change(model, contrib, out, files):
    ref, stu = model.ref, model.P['student_list_key']
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    for ax, k in zip(axes, (ref, stu)):
        d = contrib[(contrib.list_key == k) & contrib.net_change.notna()].copy()
        d = d.reindex(d.net_change.abs().sort_values(ascending=False).index).head(12).iloc[::-1]
        ax.barh(d.geo_name.str.slice(0, 22), d.net_change / 1000, color=_color(model, k))
        ax.axvline(0, color='k', lw=0.8)
        ax.set_xlabel('expected votes 2026 minus 2023 votes of the main origin family (thousands)')
        ax.set_title(_short(model, k, 36), fontsize=9)
    fig.suptitle('Units contributing most to the national change (accounting against the 2023 origin family)')
    _save(fig, out, 'fig_D_unit_contributions.png', files, 'D. Units contributing most to the national change', 'Stage 13')


def chart_timeline(model, tl, out, files):
    stu = model.P['student_list_key']
    c = f'log_ratio_vs_ref__{stu}'
    d = tl.dropna(subset=[c]) if c in tl else tl.iloc[0:0]
    if len(d) < 2:
        return
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    for k in model.targets:
        col = f'log_ratio_vs_ref__{k}'
        if col in tl and tl[col].notna().sum() >= 1:
            g = tl.dropna(subset=[col])
            axes[0].plot(g.available_date, g[col], marker='o', color=_color(model, k), label=_short(model, k, 28))
            axes[0].fill_between(g.available_date, g[f'lo80__{k}'], g[f'hi80__{k}'], color=_color(model, k), alpha=0.15)
    axes[0].axhline(0, color='k', ls=':', lw=1)
    axes[0].set_ylabel(f'log(list / {_short(model, model.ref, 18)}) at the election date (80% band)')
    axes[0].legend(fontsize=6)
    axes[1].plot(d.available_date, d.p_reference_ahead_of_student, marker='o', color='#444444')
    axes[1].set_ylim(0, 1)
    axes[1].set_ylabel('P(reference list ahead of the student list), poll aggregate only')
    for ax in axes:
        ax.tick_params(axis='x', rotation=30)
    fig.suptitle('Forecast over time: poll aggregate as each poll became public (no events, no closure)', fontsize=9)
    _save(fig, out, 'fig_F_forecast_timeline.png', files, 'F. Poll-based forecast over time', 'Stage 13')


def make_all(model, draws, seat_res, tab, per, scen, thr, sweeps, units_base, bt, out, files, timeline=None, contrib=None, form=None):
    chart_national(model, tab, out, files)
    chart_seats(model, draws, seat_res, out, files)
    chart_threshold(model, thr, out, files)
    chart_coalitions(per, out, files)
    chart_scenarios(model, scen, out, files)
    chart_sweeps(model, sweeps, out, files)
    chart_municipal(model, units_base, out, files)
    chart_polls(model, out, files)
    chart_backtest(bt, out, files)
    if form is not None:
        chart_outcomes(model, tab, per, form, out, files)
    chart_turnout_sensitivity(model, scen, out, files)
    if contrib is not None:
        chart_municipal_change(model, contrib, out, files)
    if timeline is not None:
        chart_timeline(model, timeline, out, files)
