#!/usr/bin/env python3
"""Focused parser regressions; run directly with Python (no compiler needed)."""
import contextlib
import io
import unittest

from test_audio_normalized import compare


class ComparisonTests(unittest.TestCase):
    def check(self, old, new):
        with contextlib.redirect_stdout(io.StringIO()):
            return compare([old, old], [new, new])

    def test_empty_or_missing_modes(self):
        self.assertTrue(compare([], []))
        self.assertEqual(len(self.check("", "")), 2)

    def test_identical(self):
        self.assertEqual(self.check('rat 0.5\n', 'rat 0.5\n'), [])

    def test_aggregates_categories_and_modes(self):
        failures = self.check('rat 0\ndelay 0\n', 'rat 1\ndelay 1\n')
        self.assertEqual(len(failures), 4)

    def test_nonfinite_on_either_side(self):
        # C isfinite can be optimized away under fast-math; Python must reject.
        for value in ('nan', 'inf', '-inf'):
            for old, new in ((f'rat {value}\n', 'rat 0\n'),
                             ('rat 0\n', f'rat {value}\n')):
                self.assertEqual(len(self.check(old, new)), 2)

    def test_shape_and_malformed(self):
        for new in ('rat 0\nrat 0\n', 'delay 0\n', 'bad row extra\n'):
            self.assertEqual(len(self.check('rat 0\n', new)), 2)

    def test_ceiling_not_widened(self):
        self.assertEqual(self.check('rat 0\n', f'rat {0.019/32768}\n'), [])
        self.assertEqual(len(self.check('rat 0\n', f'rat {0.02/32768}\n')), 2)


if __name__ == '__main__':
    unittest.main()
