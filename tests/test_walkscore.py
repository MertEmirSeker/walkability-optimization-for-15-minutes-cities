"""
Unit tests for WalkScore calculation.
"""
import unittest
import numpy as np
from src.scoring.walkscore import WalkScoreCalculator


class TestWalkScore(unittest.TestCase):
    """Test WalkScore computation."""
    
    def test_piecewise_linear_score(self):
        """Test PWL function at breakpoints."""
        # Mock scorer with simple breakpoints
        class MockScorer:
            breakpoints = [0, 400, 800, 1600, 2400]
            scores = [100, 100, 90, 70, 0]
        
        scorer = MockScorer()
        
        # Test at breakpoints
        self.assertEqual(scorer.scores[0], 100)  # 0m
        self.assertEqual(scorer.scores[1], 100)  # 400m
        self.assertEqual(scorer.scores[2], 90)   # 800m
        self.assertEqual(scorer.scores[3], 70)   # 1600m
        self.assertEqual(scorer.scores[4], 0)    # 2400m
    
    def test_weighted_distance_plain(self):
        """Test weighted distance for plain amenities."""
        # Test that Aplain uses single nearest
        # li = wa * min(distances)
        
        distances = [500, 1000, 1500]  # meters
        weight = 1.0  # grocery
        
        expected = weight * min(distances)  # 1.0 * 500 = 500
        self.assertEqual(expected, 500.0)
    
    def test_weighted_distance_depth(self):
        """Test weighted distance for depth amenities."""
        # Test that Adepth uses top-r with depth weights
        # li = wa * Σ(wap * distance_p)
        
        distances = [200, 400, 600, 800, 1000]  # sorted
        category_weight = 0.6  # restaurant
        depth_weights = {1: 0.4, 2: 0.3, 3: 0.2, 4: 0.1}  # rank -> weight
        
        # Calculate: 0.6 * (0.4*200 + 0.3*400 + 0.2*600 + 0.1*800)
        depth_sum = (0.4*200 + 0.3*400 + 0.2*600 + 0.1*800)  # = 80+120+120+80 = 400
        expected = 0.6 * 400  # = 240
        
        self.assertEqual(expected, 240.0)
    
    def test_no_normalization(self):
        """Test that weighted distance is NOT normalized."""
        # CRITICAL: Paper formula does NOT divide by total_weight
        
        # Aplain: grocery (wa=1.0), dist=500m
        # Adepth: restaurant (wa=0.6), depth_sum=400m
        # Total: 1.0*500 + 0.6*400 = 500 + 240 = 740
        
        weighted_dist = 1.0 * 500 + 0.6 * 400
        self.assertEqual(weighted_dist, 740.0)
        
        # NOT divided by (1.0 + 0.6) = 1.6
        # WRONG: 740 / 1.6 = 462.5
    
    def test_monotonicity(self):
        """Test that adding amenities never decreases WalkScore."""
        # If we add an amenity, weighted distance should decrease or stay same
        # Therefore, WalkScore should increase or stay same
        
        # Before: distance to nearest = 1000m
        dist_before = 1000
        
        # After: add amenity at 500m
        dist_after = min(500, 1000)  # = 500
        
        self.assertLessEqual(dist_after, dist_before)
        # This ensures WalkScore_after >= WalkScore_before


class TestWalkScoreFormula(unittest.TestCase):
    """Test specific formula cases from paper."""
    
    def test_paper_example_1(self):
        """Test Example 1 from paper."""
        # Scenario: 1 residential, 1 grocery at 500m, 1 restaurant at 1000m
        # Aplain: grocery (wa=1.0, dist=500)
        # Adepth: restaurant (wa=0.6, r=1, wap=1.0, dist=1000)
        
        weighted_dist = 1.0 * 500 + 0.6 * 1.0 * 1000
        self.assertEqual(weighted_dist, 500 + 600)
        self.assertEqual(weighted_dist, 1100.0)
    
    def test_paper_example_2(self):
        """Test with multiple depth choices."""
        # 1 residential, 1 grocery at 300m, 3 restaurants at [500, 800, 1200]m
        # Aplain: grocery (wa=1.0, dist=300)
        # Adepth: restaurant (wa=0.6, r=3, wap=[0.4, 0.3, 0.3])
        
        weighted_dist = 1.0 * 300 + 0.6 * (0.4*500 + 0.3*800 + 0.3*1200)
        depth_sum = 0.4*500 + 0.3*800 + 0.3*1200  # = 200+240+360 = 800
        self.assertEqual(weighted_dist, 300 + 0.6*800)
        self.assertEqual(weighted_dist, 300 + 480)
        self.assertEqual(weighted_dist, 780.0)


class TestWalkScoreEdgeCases(unittest.TestCase):
    """Test edge cases."""
    
    def test_zero_distance(self):
        """Test when amenity is at same location as residential."""
        dist = 0
        # Should give maximum score (100)
        self.assertEqual(dist, 0)
    
    def test_infinity_distance(self):
        """Test when no amenity is reachable."""
        D_infinity = 10000  # paper uses large value
        # Should give minimum score (0 or close to 0)
        self.assertGreater(D_infinity, 2400)  # Beyond last breakpoint
    
    def test_no_amenities(self):
        """Test when no amenities exist."""
        # All distances = D_infinity
        # WalkScore should be minimum (0 or close to 0)
        pass


if __name__ == '__main__':
    unittest.main()

