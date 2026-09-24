#!/usr/bin/env python3
"""Bounded line-level falsification in R225X hiPSC cardiomyocytes.

No network, no candidate selection, no raw-count differential-expression claim.
Exact registration, code, mapping, input bytes and dependencies bind each run.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
import math
import platform
from pathlib import Path

import numpy as np
import scipy
from scipy.stats import t as student_t


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text())


def write_json(path: Path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def holm(values):
    """Holm family-wise adjustment, retaining all prespecified hypotheses."""
    if not values or any(not math.isfinite(p) or p < 0 or p > 1 for p in values):
        raise ValueError('Invalid p-value family')
    order = sorted(range(len(values)), key=lambda i: (values[i], i))
    adjusted = [1.0] * len(values)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(values) - rank) * values[i]))
        adjusted[i] = running
    return adjusted


def welch_lower(case, control, minimum_effect=0.5):
    """Test H0 mean(case)-mean(control)>=-minimum_effect using Welch t.

    Small-n, approximate normal-theory model. Zero group variance is unqualified.
    """
    case, control = np.asarray(case, float), np.asarray(control, float)
    if len(case) < 3 or len(control) < 3 or not np.isfinite(case).all() or not np.isfinite(control).all():
        raise ValueError('Require three finite observations per line')
    effect = float(case.mean() - control.mean())
    variances = [float(case.var(ddof=1)), float(control.var(ddof=1))]
    if min(variances) <= 0:
        return {'delta': effect, 'p_lower': 1.0, 'status': 'zero_group_variance',
                'standard_error': None, 'df': None, 't': None}
    a, b = variances[0] / len(case), variances[1] / len(control)
    se = math.sqrt(a + b)
    df = (a + b) ** 2 / (a*a/(len(case)-1) + b*b/(len(control)-1))
    statistic = (effect + minimum_effect) / se
    return {'delta': effect, 'standard_error': se, 'df': df, 't': statistic,
            'p_lower': float(student_t.cdf(statistic, df)), 'status': 'model_evaluated'}


def pair_measurement(case, control, reg):
    pc = reg['analysis']['pseudocount_primary']
    minimum = reg['analysis']['minimum_log2_decrease']
    y_case, y_control = np.log2(case + pc), np.log2(control + pc)
    row = welch_lower(y_case, y_control, minimum)
    row['case_mean_fpkm'] = float(case.mean())
    row['control_mean_fpkm'] = float(control.mean())
    row['case_fpkm'] = case.tolist()
    row['control_fpkm'] = control.tolist()
    row['control_expression_eligible'] = bool((control >= 1).sum() >= 2 and control.mean() >= 1)
    loo = [float(np.delete(y_case, i).mean() - y_control.mean()) for i in range(len(case))]
    loo += [float(y_case.mean() - np.delete(y_control, i).mean()) for i in range(len(control))]
    row['loo_deltas'] = loo
    row['loo_all_negative'] = bool(max(loo) < 0)
    row['sensitivity_deltas'] = {
        str(pseudo): float(np.log2(case + pseudo).mean() - np.log2(control + pseudo).mean())
        for pseudo in reg['analysis']['pseudocount_sensitivity']
    }
    row['sensitivity_large_decrease'] = bool(all(x <= -minimum for x in row['sensitivity_deltas'].values()))
    return row


def read_fpkm(path, expected_header):
    seen, rows = set(), {}
    with gzip.open(path, 'rt', newline='') as stream:
        reader = csv.reader(stream, delimiter='\t')
        if next(reader) != expected_header:
            raise ValueError('FPKM header differs from frozen metadata')
        for row in reader:
            if len(row) != len(expected_header) or not row[0] or row[0] in seen:
                raise ValueError('Duplicate/empty identifier or incorrect row width')
            seen.add(row[0])
            values = np.asarray([float(x) for x in row[1:]], dtype=float)
            if not np.isfinite(values).all() or (values < 0).any() or (values > 1e9).any():
                raise ValueError('Invalid FPKM value')
            rows[row[0]] = values
            if len(rows) > 200_000:
                raise ValueError('Matrix exceeds row bound')
    if not rows:
        raise ValueError('Empty FPKM matrix')
    return rows


def evaluate(rows, reg, mapping):
    samples = reg['samples']
    header = reg['input']['header']
    case_ix = [header.index(x) - 1 for x in samples['mutant']]
    clone_ix = {name: [header.index(x) - 1 for x in columns]
                for name, columns in samples['corrected_clones'].items()}
    records = []
    for gene in reg['candidates']:
        identifiers = mapping['candidate_tracking_ids'].get(gene, [])
        record = {'gene': gene, 'tracking_ids': identifiers, 'family_p': 1.0,
                  'status': 'missing_or_ambiguous_mapping', 'pass': False}
        if len(identifiers) == 1:
            identifier = identifiers[0]
            if identifier not in rows:
                record['status'] = 'missing_expression_row'
            else:
                values = rows[identifier]
                pairs = {name: pair_measurement(values[case_ix], values[indices], reg)
                         for name, indices in clone_ix.items()}
                eligible = all(p['control_expression_eligible'] and p['status'] == 'model_evaluated'
                               for p in pairs.values())
                record.update({'status': 'evaluable' if eligible else 'expression_or_variance_ineligible',
                               'pairs': pairs,
                               'family_p': max(p['p_lower'] for p in pairs.values()) if eligible else 1.0})
        records.append(record)
    for record, adjusted in zip(records, holm([r['family_p'] for r in records])):
        record['holm_p'] = adjusted
        record['pass'] = bool(record['status'] == 'evaluable'
                              and adjusted <= reg['analysis']['family_alpha']
                              and all(p['delta'] <= -reg['analysis']['minimum_log2_decrease']
                                      and p['loo_all_negative'] and p['sensitivity_large_decrease']
                                      for p in record['pairs'].values()))
    return records


def validate_design(reg, mapping):
    if reg['status'] != 'frozen_before_numerical_outcome_access':
        raise ValueError('Protocol must be frozen before execution')
    if mapping['source_sha256'] != reg['mapping_source_sha256']:
        raise ValueError('Mapping source provenance differs from registration')
    if len(reg['candidates']) != 10 or len(set(reg['candidates'])) != 10:
        raise ValueError('Exactly ten frozen panel genes required')
    header = reg['input']['header']
    if len(header) != 10 or len(set(header)) != len(header) or header[0] != 'tracking_id':
        raise ValueError('Invalid frozen FPKM header')
    groups = [reg['samples']['mutant']] + list(reg['samples']['corrected_clones'].values())
    if len(groups) != 3 or any(len(group) != 3 for group in groups):
        raise ValueError('Expected three independent cultures in each of three lines')
    columns = [x for group in groups for x in group]
    if len(set(columns)) != 9 or set(columns) != set(header[1:]):
        raise ValueError('Overlapping or incomplete sample mapping')
    ids = [x for gene in reg['candidates'] for x in mapping['candidate_tracking_ids'].get(gene, [])]
    if len(ids) != len(set(ids)):
        raise ValueError('A tracking ID maps to multiple candidates')
    if reg['analysis'] != {
        'minimum_log2_decrease': 0.5, 'family_alpha': 0.05,
        'pseudocount_primary': 0.5, 'pseudocount_sensitivity': [0.1, 1.0],
        'test': 'one-sided Welch threshold t-test; union maximum over two corrected-clone comparisons; Holm10',
        'ineligible_policy': 'p=1, preserve family10',
        'promotion': 'both primary delta<=-0.5, Holm<=0.05, all leave-one-culture-out contrasts<0, both sensitivities<=-0.5'
    }:
        raise ValueError('Analysis rules differ from admitted implementation')


def run(args):
    if args.out.exists():
        raise ValueError('Output directory must be new')
    freeze, reg, mapping, intake = map(read_json, (args.freeze, args.registration, args.mapping, args.intake))
    for key, path in [('registration_sha256', args.registration), ('mapping_sha256', args.mapping),
                      ('code_sha256', Path(__file__)), ('requirements_sha256', Path(__file__).with_name('requirements.lock'))]:
        if sha(path) != freeze[key]:
            raise ValueError(f'Frozen artifact changed: {key}')
    if intake['registration_sha256'] != sha(args.registration) or intake['freeze_sha256'] != sha(args.freeze):
        raise ValueError('Intake not bound to frozen design')
    if args.counts.stat().st_size > reg['input']['max_compressed_bytes']:
        raise ValueError('Input exceeds registered compressed-byte limit')
    if args.counts.is_symlink() or sha(args.counts) != intake['matrix_sha256'] or args.counts.stat().st_size != intake['matrix_bytes']:
        raise ValueError('Input bytes differ from admitted intake')
    if (np.__version__, scipy.__version__) != ('2.3.3', '1.16.2'):
        raise ValueError('Scientific runtime differs from dependency lock')
    validate_design(reg, mapping)
    rows = read_fpkm(args.counts, reg['input']['header'])
    records = evaluate(rows, reg, mapping)
    args.out.mkdir()
    result = {'schema':'bio.r225x-falsification.v1', 'registration_sha256':sha(args.registration),
              'code_sha256':sha(Path(__file__)), 'mapping_sha256':sha(args.mapping),
              'freeze_sha256':sha(args.freeze), 'intake_sha256':sha(args.intake),
              'matrix_sha256':sha(args.counts), 'source_rows':len(rows),
              'runtime':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__},
              'fixed_panel_size':len(records), 'passed':sum(r['pass'] for r in records), 'outcomes':records,
              'claim_ceiling':reg['claim_ceiling'], 'limitations':reg['limitations']}
    write_json(args.out / 'summary.json', result)
    with (args.out / 'outcomes.tsv').open('x', newline='') as stream:
        fields = ['gene','status','pass','family_p','holm_p','clone1_delta','clone2_delta']
        writer = csv.DictWriter(stream, fields, delimiter='\t', lineterminator='\n')
        writer.writeheader()
        for row in records:
            item = {k:row[k] for k in fields[:5]}
            for k,name in [('clone1_delta','corrected_1'),('clone2_delta','corrected_2')]:
                item[k] = row.get('pairs',{}).get(name,{}).get('delta','')
            writer.writerow(item)
    print(json.dumps({'fixed_panel_size':len(records),'passed':sum(r['pass'] for r in records),
                      'outcomes':[{k:r[k] for k in ['gene','status','pass','family_p','holm_p']} for r in records]},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['registration','freeze','mapping','intake','counts','out']:
        parser.add_argument('--'+name, required=True, type=Path)
    run(parser.parse_args())
