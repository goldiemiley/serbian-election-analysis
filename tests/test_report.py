"""End-to-end smoke test of the reporting layer on a small run: every promised file is produced and internally consistent."""
import json

import numpy as np
import pandas as pd

import report as RP


def test_run_all_small(model, tmp_path):
    res = RP.run_all(model, tmp_path, n=1500, n_unit=60, make_charts=True, verbose=False)
    man = pd.read_csv(tmp_path / 'OUTPUT_MANIFEST.csv')
    on_disk = {p.name for p in tmp_path.iterdir()} - {'OUTPUT_MANIFEST.csv'}
    assert set(man.file) == on_disk, 'manifest and directory disagree'
    for must in ('A_national_votes_shares_seats.csv', 'B_threshold_sensitivity.csv', 'C_coalitions.csv', 'C_government_formation_conditional.csv',
                 'D_municipal_list_shares_alpha0.csv', 'D_municipal_turnout.csv', 'E_scenario_comparison.csv', 'E_threshold_sweeps.csv',
                 'F_backtest_geography_methods.csv', 'fig_A_national_shares.png', 'fig_E_scenarios.png', 'run_metadata.json'):
        assert must in on_disk, must
    tab = pd.read_csv(tmp_path / 'A_national_votes_shares_seats.csv')
    assert abs(tab.seats_mean.sum() - model.P['seats_total']) < 1e-6
    assert abs(tab.share_mean.sum() - 1) < 1e-9
    f = pd.read_csv(tmp_path / 'C_government_formation_conditional.csv').set_index('event').probability
    assert ((f >= 0) & (f <= 1)).all()
    sc = pd.read_csv(tmp_path / 'E_scenario_comparison.csv')
    assert sc.scenario.iloc[0] == 'baseline' and sc.filter(like='share_median').notna().all().all()
    mt = pd.read_csv(tmp_path / 'D_municipal_turnout.csv')
    assert len(mt) == len(model.panel) and mt.turnout_mean.between(0, 1).all()
    meta = json.loads((tmp_path / 'run_metadata.json').read_text())
    assert meta['random_seed'] == model.P['random_seed']


def test_scenarios_use_common_random_numbers(model):
    sc, _ = RP.run_scenarios(model, n=800, scenarios=RP.scenario_set(model)[:3], verbose=False)
    a, b = sc.iloc[0], sc.iloc[1]
    assert a.scenario == 'baseline' and b.scenario == 'polls_only'
    # same draws except for the event mixture: reference-list share identical up to the realignment effect on the student list
    assert abs(a['share_median__' + model.ref] - b['share_median__' + model.ref]) < 0.01
