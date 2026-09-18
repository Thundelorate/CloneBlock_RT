"""Protocol checks that do not require audio, model weights, or a GPU."""

import random
import unittest
import importlib.util
from pathlib import Path

import torch
import torch.nn.functional as F

# The package initializer eagerly imports ASR; these tests need only real tensor selection.
_spec = importlib.util.spec_from_file_location(
    'session_attack_under_test',
    Path(__file__).resolve().parents[1] / 'src' / 'metrics' / 'session_attack.py',
)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
pick_indices = _module.pick_indices
selection_protocol = _module.selection_protocol


class SessionAttackTests(unittest.TestCase):
    def setUp(self):
        self.observed = F.normalize(torch.tensor([
            [1.0, 0.0], [0.8, 0.2], [0.0, 1.0], [-1.0, 0.2],
        ]), dim=-1)

    def test_realistic_selection_does_not_depend_on_clean_values(self):
        for k in (1, 2, 4):
            first = pick_indices('bestK_by_self_consistency', self.observed, k,
                                 random.Random(2), selection_z=self.observed)
            second = pick_indices('bestK_by_self_consistency', -self.observed, k,
                                  random.Random(2), selection_z=self.observed)
            self.assertEqual(first, second)
            self.assertEqual(len(set(first)), k)

    def test_realistic_selection_requires_observations(self):
        with self.assertRaises(ValueError):
            pick_indices('bestK_by_self_consistency', self.observed, 2, random.Random(2))

    def test_realistic_selection_rejects_duplicate_enrollment(self):
        with self.assertRaises(ValueError):
            pick_indices('bestK_by_self_consistency', self.observed, 5,
                         random.Random(2), selection_z=self.observed)

    def test_invalid_strategy_and_k_fail(self):
        with self.assertRaises(ValueError):
            pick_indices('typo', self.observed, 2, random.Random(2))
        with self.assertRaises(ValueError):
            pick_indices('random_K', self.observed, 0, random.Random(2))

    def test_protocol_labels_reflect_information_access(self):
        self.assertEqual(selection_protocol('bestK_by_self_consistency', 'tele_defended')
                         ['attacker_view'], 'realistic')
        self.assertEqual(selection_protocol('bestK_by_self_consistency', 'defended')
                         ['attacker_view'], 'pre_channel_ablation')
        self.assertEqual(selection_protocol('bestK_by_clean_consistency', 'tele_defended')
                         ['attacker_view'], 'oracle_reference')
        with self.assertRaises(ValueError):
            selection_protocol('bestK_by_self_consistency', 'clean')

    def test_legacy_observed_centroid_selection_is_preserved(self):
        for k in (1, 2, 4):
            old = pick_indices('bestK_by_ref_similarity', -self.observed, k,
                               random.Random(2), selection_z=self.observed)
            new = pick_indices('bestK_by_self_consistency', -self.observed, k,
                               random.Random(2), selection_z=self.observed)
            self.assertEqual(old, new)


if __name__ == '__main__':
    unittest.main()
