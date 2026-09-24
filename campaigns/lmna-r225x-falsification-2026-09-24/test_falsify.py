"""Independent synthetic checks; these tests never read public expression data."""
from copy import deepcopy
from contextlib import redirect_stdout
import gzip
import io
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
from scipy import stats

import falsify


GENES = ['CMTM5', 'SLC2A14', 'NID2', 'DCAF8', 'PIANP', 'MEX3B',
         'ANKRD52', 'ZFTA', 'FYCO1', 'LYSMD3']


def design():
    """Artificial sample names and identities, with the admitted analysis rules."""
    groups = {'mutant': ['m1', 'm2', 'm3'],
              'corrected_clones': {'corrected_1': ['a1', 'a2', 'a3'],
                                   'corrected_2': ['b1', 'b2', 'b3']}}
    registration = {
        'status': 'frozen_before_numerical_outcome_access',
        'mapping_source_sha256': 'synthetic_source',
        'candidates': GENES,
        'samples': groups,
        'input': {'header': ['tracking_id', 'm1', 'm2', 'm3',
                             'a1', 'a2', 'a3', 'b1', 'b2', 'b3'],
                  'max_compressed_bytes': 2_000_000},
        'claim_ceiling': 'synthetic test', 'limitations': ['synthetic test'],
        'analysis': {
            'minimum_log2_decrease': 0.5, 'family_alpha': 0.05,
            'pseudocount_primary': 0.5, 'pseudocount_sensitivity': [0.1, 1.0],
            'test': 'one-sided Welch threshold t-test; union maximum over two corrected-clone comparisons; Holm10',
            'ineligible_policy': 'p=1, preserve family10',
            'promotion': 'both primary delta<=-0.5, Holm<=0.05, all leave-one-culture-out contrasts<0, both sensitivities<=-0.5',
        },
    }
    mapping = {'source_sha256': 'synthetic_source',
               'candidate_tracking_ids': {g: [f'synthetic_{i}'] for i, g in enumerate(GENES)}}
    return registration, mapping


class FormulaTests(unittest.TestCase):
    def test_welch_threshold_matches_scipy_on_250_synthetic_cases(self):
        rng = np.random.default_rng(260924)
        for _ in range(250):
            a = rng.normal(rng.uniform(-2, 2), rng.uniform(.02, 2), 3)
            b = rng.normal(rng.uniform(-2, 2), rng.uniform(.02, 2), 3)
            observed = falsify.welch_lower(a, b, .5)
            oracle = stats.ttest_ind(a + .5, b, equal_var=False, alternative='less')
            np.testing.assert_allclose(
                [observed['t'], observed['df'], observed['p_lower']],
                [oracle.statistic, oracle.df, oracle.pvalue], rtol=1e-12, atol=1e-12)

    def test_effect_boundary_is_half_tail_and_sign_is_down(self):
        b = np.array([1., 2., 3.])
        boundary = falsify.welch_lower(b - .5, b)
        self.assertAlmostEqual(boundary['p_lower'], .5)
        self.assertAlmostEqual(boundary['t'], 0.)
        self.assertGreater(falsify.welch_lower(b + 1., b)['p_lower'], .5)

    def test_degenerate_variance_cannot_be_promoted(self):
        observed = falsify.welch_lower([0., 0., 0.], [2., 2.1, 2.2])
        self.assertEqual(observed['status'], 'zero_group_variance')
        self.assertEqual(observed['p_lower'], 1.)
        for a, b in [([1, 2], [1, 2, 3]), ([1, 2, np.nan], [1, 2, 3])]:
            with self.assertRaises(ValueError):
                falsify.welch_lower(a, b)

    def test_holm_ten_oracle_order_and_ties(self):
        p = [.4, 1, .003, .001, 1, .002, 1, 1, 1, 1]
        np.testing.assert_allclose(falsify.holm(p), [1, 1, .024, .01, 1, .018, 1, 1, 1, 1])
        np.testing.assert_allclose(falsify.holm([.01, .01, .1]), [.03, .03, .1])
        for bad in [[], [math.nan], [-.1], [1.01]]:
            with self.assertRaises(ValueError):
                falsify.holm(bad)


class GateTests(unittest.TestCase):
    def test_missing_nine_keep_family_and_strong_candidate_passes(self):
        reg, mapping = design()
        values = np.array([1, 1.01, .99, 10, 10.02, 9.98, 11, 11.02, 10.98])
        outcomes = falsify.evaluate({'synthetic_0': values}, reg, mapping)
        self.assertEqual(len(outcomes), 10)
        observed = outcomes[0]
        self.assertTrue(observed['pass'])
        expected_p = max(pair['p_lower'] for pair in observed['pairs'].values())
        self.assertAlmostEqual(observed['family_p'], expected_p)
        self.assertAlmostEqual(observed['holm_p'], min(1, 10 * expected_p))
        self.assertTrue(all(r['family_p'] == 1 and not r['pass'] for r in outcomes[1:]))

    def test_one_clone_disagreement_cannot_pass_intersection(self):
        reg, mapping = design()
        values = np.array([10, 10.1, 9.9, 100, 101, 99, 2, 2.1, 1.9])
        observed = falsify.evaluate({'synthetic_0': values}, reg, mapping)[0]
        self.assertLess(observed['pairs']['corrected_1']['p_lower'], .001)
        self.assertGreater(observed['pairs']['corrected_2']['p_lower'], .99)
        self.assertGreater(observed['family_p'], .99)
        self.assertFalse(observed['pass'])

    def test_primary_significance_cannot_rescue_pseudocount_instability(self):
        reg, mapping = design()
        values = np.array([.8999, .9, .9001, 1.4999, 1.5, 1.5001, 1.4999, 1.5, 1.5001])
        observed = falsify.evaluate({'synthetic_0': values}, reg, mapping)[0]
        self.assertLess(observed['holm_p'], .05)
        self.assertLess(observed['pairs']['corrected_1']['delta'], -.5)
        self.assertGreater(observed['pairs']['corrected_1']['sensitivity_deltas']['1.0'], -.5)
        self.assertFalse(observed['pass'])

    def test_low_control_expression_forces_p_one(self):
        reg, mapping = design()
        values = np.array([.001, .002, .003, .5, .51, .49, .6, .61, .59])
        observed = falsify.evaluate({'synthetic_0': values}, reg, mapping)[0]
        self.assertEqual(observed['status'], 'expression_or_variance_ineligible')
        self.assertEqual(observed['family_p'], 1.)
        self.assertFalse(observed['pass'])

    def test_loo_matches_independent_explicit_combinations(self):
        reg, _ = design()
        a = np.array([1., 2., 4.]); b = np.array([8., 9., 10.])
        observed = falsify.pair_measurement(a, b, reg)
        al = np.log2(a + .5); bl = np.log2(b + .5)
        expected = [sum(al[j] for j in range(3) if j != i)/2 - sum(bl)/3 for i in range(3)]
        expected += [sum(al)/3 - sum(bl[j] for j in range(3) if j != i)/2 for i in range(3)]
        np.testing.assert_allclose(observed['loo_deltas'], expected)

    def test_design_rejects_overlap_mapping_aliasing_and_rule_changes(self):
        reg, mapping = design()
        falsify.validate_design(reg, mapping)
        bad = deepcopy(reg); bad['samples']['corrected_clones']['corrected_1'][0] = 'm1'
        with self.assertRaises(ValueError):
            falsify.validate_design(bad, mapping)
        bad = deepcopy(reg); bad['status'] = 'review_draft_before_outcome_access'
        with self.assertRaises(ValueError):
            falsify.validate_design(bad, mapping)
        bad_map = deepcopy(mapping); bad_map['source_sha256'] = 'another_source'
        with self.assertRaises(ValueError):
            falsify.validate_design(reg, bad_map)
        bad_map = deepcopy(mapping); bad_map['candidate_tracking_ids'][GENES[1]] = ['synthetic_0']
        with self.assertRaises(ValueError):
            falsify.validate_design(reg, bad_map)
        bad = deepcopy(reg); bad['analysis']['minimum_log2_decrease'] = .49
        with self.assertRaises(ValueError):
            falsify.validate_design(bad, mapping)


class IntakeTests(unittest.TestCase):
    def test_decimal_fpkm_preserved_and_invalid_intakes_rejected(self):
        reg, _ = design()
        header = reg['input']['header']
        good = '\t'.join(header) + '\nsynthetic\t' + '\t'.join(['1.25']*9) + '\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'synthetic.gz'
            def put(text):
                with gzip.open(path, 'wt') as stream:
                    stream.write(text)
            put(good)
            np.testing.assert_array_equal(falsify.read_fpkm(path, header)['synthetic'], [1.25]*9)
            for bad in [good + good.split('\n')[1]+'\n',
                        good.replace('1.25', 'nan', 1),
                        good.replace('1.25', '-1', 1),
                        good.replace('1.25', '1000000001', 1),
                        good.replace('tracking_id', 'gene'),
                        '\t'.join(header)+'\n']:
                put(bad)
                with self.assertRaises(ValueError):
                    falsify.read_fpkm(path, header)

    def test_run_rejects_oversize_before_read_and_replays_only_synthetic_data(self):
        reg, mapping = design()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = SimpleNamespace(registration=root/'reg.json', freeze=root/'freeze.json',
                                   mapping=root/'map.json', intake=root/'intake.json',
                                   counts=root/'synthetic.gz', out=root/'out')
            with gzip.open(args.counts, 'wt') as stream:
                stream.write('\t'.join(reg['input']['header'])+'\n')
                stream.write('synthetic_0\t1\t1.01\t.99\t10\t10.02\t9.98\t11\t11.02\t10.98\n')
            args.mapping.write_text(json.dumps(mapping))
            def bind():
                args.registration.write_text(json.dumps(reg))
                freeze = {'registration_sha256': falsify.sha(args.registration),
                          'mapping_sha256': falsify.sha(args.mapping),
                          'code_sha256': falsify.sha(Path(falsify.__file__)),
                          'requirements_sha256': falsify.sha(Path(falsify.__file__).with_name('requirements.lock'))}
                args.freeze.write_text(json.dumps(freeze))
                intake = {'registration_sha256': falsify.sha(args.registration),
                          'freeze_sha256': falsify.sha(args.freeze),
                          'matrix_sha256': falsify.sha(args.counts),
                          'matrix_bytes': args.counts.stat().st_size}
                args.intake.write_text(json.dumps(intake))
            reg['input']['max_compressed_bytes'] = 1
            bind()
            with patch.object(falsify, 'read_fpkm') as forbidden:
                with self.assertRaisesRegex(ValueError, 'compressed-byte'):
                    falsify.run(args)
                forbidden.assert_not_called()
            reg['input']['max_compressed_bytes'] = 2_000_000
            bind()
            with redirect_stdout(io.StringIO()):
                falsify.run(args)
            result = json.loads((args.out/'summary.json').read_text())
            self.assertEqual(result['fixed_panel_size'], 10)
            self.assertEqual(result['passed'], 1)
            self.assertEqual(result['source_rows'], 1)
            with self.assertRaisesRegex(ValueError, 'must be new'):
                falsify.run(args)


if __name__ == '__main__':
    unittest.main()
