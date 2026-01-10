"""
Debug with SAMPLED data (the ones we computed paths for).
"""
from src.network.pedestrian_graph import PedestrianGraph
from src.network.shortest_paths import ShortestPathCalculator
from src.scoring.walkscore import WalkScoreCalculator
from sqlalchemy import text

print("="*70)
print("DEBUG: WalkScore with SAMPLED DATA")
print("="*70)

# Load graph
graph = PedestrianGraph()
graph.load_from_database()

# Load paths
path_calc = ShortestPathCalculator(graph)
path_calc.load_from_database()

# Create scorer
scorer = WalkScoreCalculator(graph, path_calc)

# Find a residential-candidate pair that exists in database
print("\nFinding residential-candidate pair in database...")
with graph.db.get_session() as session:
    query = """
        SELECT DISTINCT from_node_id, to_node_id, distance_meters
        FROM shortest_paths sp
        JOIN residential_locations rl ON sp.from_node_id = rl.node_id
        JOIN candidate_locations cl ON sp.to_node_id = cl.node_id
        WHERE distance_meters < 2000
        LIMIT 1
    """
    result = session.execute(text(query))
    row = result.fetchone()
    
    if row:
        test_residential, test_candidate, dist_in_db = row
        print(f"  Found pair: residential={test_residential}, candidate={test_candidate}")
        print(f"  Distance in DB: {dist_in_db:.2f}m")
    else:
        print("  ✗ No pairs found!")
        exit(1)

# Test WalkScore
print(f"\n1. Baseline (no allocations):")
baseline_score = scorer.compute_walkscore(test_residential, allocated_amenities=None)
baseline_dist = scorer.compute_weighted_distance(test_residential, allocated_amenities=None)
print(f"   Weighted distance: {baseline_dist:.2f}m")
print(f"   WalkScore: {baseline_score:.2f}")

print(f"\n2. With grocery allocated to candidate {test_candidate}:")
solution = {'grocery': {test_candidate}}
allocated_score = scorer.compute_walkscore(test_residential, allocated_amenities=solution)
allocated_dist = scorer.compute_weighted_distance(test_residential, allocated_amenities=solution)
print(f"   Weighted distance: {allocated_dist:.2f}m")
print(f"   WalkScore: {allocated_score:.2f}")
print(f"   Improvement: {allocated_score - baseline_score:.4f}")

print("\n" + "="*70)
if allocated_score > baseline_score:
    print("✓ SUCCESS: WalkScore improved!")
    print("  Algorithm is working correctly!")
else:
    print("✗ Still no improvement...")
    print(f"  Distance to candidate: {dist_in_db:.2f}m")
    print(f"  Baseline weighted dist: {baseline_dist:.2f}m")
    print(f"  Allocated weighted dist: {allocated_dist:.2f}m")
print("="*70)

