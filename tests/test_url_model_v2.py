"""Behaviour checks at the URL representation and operating-point boundaries."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from url_model_v2 import normalize_url, numeric_features


class UrlRepresentationTest(unittest.TestCase):
    def test_http_root_slash_does_not_change_features(self):
        self.assertEqual(normalize_url('https://Example.COM'), 'https://example.com/')
        self.assertEqual(numeric_features('https://Example.COM'),
                         numeric_features('https://example.com/'))

    def test_meaningful_case_and_fragment_are_preserved(self):
        self.assertEqual(normalize_url('HTTPS://User:Pass@Example.COM/A?q=B#C'),
                         'https://User:Pass@example.com/A?q=B#C')
        self.assertNotEqual(normalize_url('https://example.com/A'),
                            normalize_url('https://example.com/a'))

    def test_learning_projection_ignores_collection_prefixes_without_merging_urls(self):
        from url_model_v2 import learning_projection
        self.assertEqual(learning_projection('HTTPS://www.Example.COM/A?q=B'),
                         learning_projection('http://example.com/A?q=B'))
        self.assertNotEqual(normalize_url('https://www.example.com/'),
                            normalize_url('http://example.com/'))


class OperatingPointTest(unittest.TestCase):
    def test_tied_normal_scores_do_not_violate_the_fpr_budget(self):
        from url_model_v2 import calibrate_threshold
        result = calibrate_threshold([0, 0, 1, 1], [.8, .8, .9, .7],
                                     ['source'] * 4, .5)
        self.assertGreater(result['threshold'], .8)
        self.assertEqual(result['by_source']['source']['fpr'], 0)
        self.assertEqual(result['by_source']['source']['recall'], .5)

    def test_probability_matrix_is_rejected_as_a_score_vector(self):
        from url_model_v2 import calibrate_threshold
        with self.assertRaises(ValueError):
            calibrate_threshold([0, 1], [[.8, .2], [.1, .9]], ['source'] * 2, .01)


if __name__ == '__main__':
    unittest.main()
