import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APIGATEWAY_APP_DIR = os.path.join(PROJECT_ROOT, "APIGateway", "app")
if APIGATEWAY_APP_DIR not in sys.path:
    sys.path.append(APIGATEWAY_APP_DIR)

from evaluate_scenarios import sample_pareto, sample_object_size_mb, sample_read_count


class EvaluateScenariosWorkloadTests(unittest.TestCase):
    def test_sample_pareto_returns_positive_values(self):
        rng = __import__('random').Random(123)
        for _ in range(20):
            value = sample_pareto(rng, alpha=1.2, scale=10.0, min_value=1.0, max_value=1000.0)
            self.assertGreaterEqual(value, 1.0)
            self.assertLessEqual(value, 1000.0)

    def test_sample_object_size_mb_is_realistic(self):
        rng = __import__('random').Random(42)
        size = sample_object_size_mb(rng)
        self.assertGreater(size, 0.0)
        self.assertLessEqual(size, 512.0)

    def test_sample_read_count_respects_minimum(self):
        rng = __import__('random').Random(7)
        reads = sample_read_count(rng)
        self.assertGreaterEqual(reads, 1)


if __name__ == "__main__":
    unittest.main()
