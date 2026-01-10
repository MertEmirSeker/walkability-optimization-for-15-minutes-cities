"""
Debug script to test WalkScore calculation with allocations.
"""
from src.network.pedestrian_graph import PedestrianGraph
from src.network.shortest_paths import ShortestPathCalculator
from src.scoring.walkscore import WalkScoreCalculator

print("="*70)
print("DEBUG: WalkScore Calculation with Allocations")
print("="*70)

# Load graph
print("\nLoading graph...")
graph = PedestrianGraph()
graph.load_from_database()

print(f"  Residential: {len(graph.N)}")
print(f"  Candidates: {len(graph.M)}")

# Load paths
print("\nLoading shortest paths...")
path_calc = ShortestPathCalculator(graph)
path_calc.load_from_database()

# Create scorer
print("\nCreating WalkScore calculator...")
scorer = WalkScoreCalculator(graph, path_calc)

# Test with a single residential
test_residential = list(graph.N)[0]
print(f"\nTest residential: {test_residential}")

# Compute baseline WalkScore
print("\n1. Baseline (no allocations):")
baseline_score = scorer.compute_walkscore(test_residential, allocated_amenities=None)
baseline_dist = scorer.compute_weighted_distance(test_residential, allocated_amenities=None)
print(f"   Weighted distance: {baseline_dist:.2f}m")
print(f"   WalkScore: {baseline_score:.2f}")

# Test with one allocation
test_candidate = list(graph.M)[0]
print(f"\n2. With grocery allocated to candidate {test_candidate}:")
solution = {'grocery': {test_candidate}}
allocated_score = scorer.compute_walkscore(test_residential, allocated_amenities=solution)
allocated_dist = scorer.compute_weighted_distance(test_residential, allocated_amenities=solution)
print(f"   Weighted distance: {allocated_dist:.2f}m")
print(f"   WalkScore: {allocated_score:.2f}")
print(f"   Improvement: {allocated_score - baseline_score:.4f}")

# Check if allocated amenity is being used
print(f"\n3. Checking distance to allocated candidate:")
dist_to_candidate = path_calc.get_distance(test_residential, test_candidate)
print(f"   Distance: {dist_to_candidate:.2f}m")
print(f"   D_infinity: {path_calc.D_infinity:.2f}m")

# Check existing amenities
print(f"\n4. Existing grocery amenities:")
existing_grocery = graph.get_all_amenity_locations('grocery')
print(f"   Count: {len(existing_grocery)}")
if existing_grocery:
    sample_existing = list(existing_grocery)[0]
    dist_to_existing = path_calc.get_distance(test_residential, sample_existing)
    print(f"   Distance to nearest existing: {dist_to_existing:.2f}m")

# Debug: Check if allocated_amenities is used in get_all_amenity_locations
print(f"\n5. Testing get_all_amenity_locations:")
print(f"   Without allocation: {len(graph.get_all_amenity_locations('grocery'))} amenities")
# This should NOT include allocated ones - that's the bug!

print("\n" + "="*70)
print("DIAGNOSIS:")
print("="*70)

if allocated_score == baseline_score:
    print("❌ PROBLEM: Allocated amenities NOT affecting WalkScore!")
    print("\nLikely cause:")
    print("  - allocated_amenities parameter not being used in distance calculation")
    print("  - or distance to allocated candidate is >= D_infinity")
    print("  - or graph.get_all_amenity_locations not including allocated ones")
else:
    print("✓ OK: Allocated amenities ARE affecting WalkScore")
    print(f"  Improvement: {allocated_score - baseline_score:.4f}")

print("="*70)

