"""
FAST MODE TEST
Test the complete pipeline with sampled data (500 residential, 50 candidates).
"""
import time
import random
from src.network.pedestrian_graph import PedestrianGraph
from src.network.shortest_paths import ShortestPathCalculator
from src.scoring.walkscore import WalkScoreCalculator
from src.algorithms.greedy import GreedyOptimizer

print("="*70)
print("FAST MODE TEST - Complete Pipeline")
print("="*70)

total_start = time.time()

# Step 1: Load graph
print("\n[1/5] Loading graph...")
graph = PedestrianGraph()
graph.load_from_database()
print(f"  Full dataset: {len(graph.N)} residential, {len(graph.M)} candidates")

# Sample for FAST MODE (FIXED SEED for reproducibility!)
print("\n[2/5] Sampling for FAST MODE...")
random.seed(42)  # Fixed seed!
sampled_N = random.sample(list(graph.N), 500)
sampled_M = random.sample(list(graph.M), 50)
graph.N = set(sampled_N)
graph.M = set(sampled_M)
print(f"  Sampled: {len(graph.N)} residential, {len(graph.M)} candidates")

# Step 2: Compute shortest paths (FAST!)
print("\n[3/5] Computing shortest paths (FAST MODE)...")
start = time.time()
calc = ShortestPathCalculator(graph)

destinations = set(graph.M)
for amenity_nodes in graph.L.values():
    destinations.update(amenity_nodes)

total_pairs = len(graph.N) * len(destinations)
print(f"  Computing {total_pairs:,} pairs...")

calc.compute_all_distances(save_to_db=False)  # Compute on-the-fly, don't save
print(f"  ✓ Complete in {time.time()-start:.1f}s")

# Step 3: Calculate baseline WalkScores
print("\n[4/5] Calculating baseline WalkScores...")
start = time.time()
scorer = WalkScoreCalculator(graph, calc)
baseline_scores = scorer.compute_baseline_scores(save_to_db=False)
baseline_avg = sum(baseline_scores.values()) / len(baseline_scores)
print(f"  Baseline avg: {baseline_avg:.2f}")
print(f"  ✓ Complete in {time.time()-start:.1f}s")

# Step 4: Run Greedy optimization
print("\n[5/5] Running Greedy optimization (k=1)...")
start = time.time()
optimizer = GreedyOptimizer(graph, scorer)
solution = optimizer.optimize(k=1)
print(f"  ✓ Complete in {time.time()-start:.1f}s")

# Calculate optimized scores
print("\nCalculating optimized WalkScores...")
optimized_scores = {}
for residential_id in graph.N:
    optimized_scores[residential_id] = scorer.compute_walkscore(residential_id, solution)

optimized_avg = sum(optimized_scores.values()) / len(optimized_scores)
improvement = optimized_avg - baseline_avg

# Results
print("\n" + "="*70)
print("FAST MODE TEST RESULTS")
print("="*70)
print(f"Dataset: {len(graph.N)} residential, {len(graph.M)} candidates")
print(f"Total time: {time.time()-total_start:.1f}s")
print(f"\nBaseline:")
print(f"  Average WalkScore: {baseline_avg:.2f}")
print(f"\nOptimized:")
print(f"  Average WalkScore: {optimized_avg:.2f}")
print(f"  Improvement: {improvement:+.2f} ({100*improvement/baseline_avg:+.1f}%)")
print(f"  Allocations: {sum(len(v) for v in solution.values())}")
print("\nAllocation details:")
for amenity_type, allocated in solution.items():
    print(f"  {amenity_type}: {len(allocated)} locations")

if improvement > 0:
    print("\n✓ SUCCESS: WalkScore improved!")
    print("  Algorithm is working correctly!")
else:
    print("\n✗ WARNING: No improvement detected")
    print("  Check if distances are computed correctly")

print("="*70)

