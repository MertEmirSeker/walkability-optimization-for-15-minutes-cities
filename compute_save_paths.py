"""
Compute and SAVE shortest paths to database for FAST MODE.
"""
import time
import random
from src.network.pedestrian_graph import PedestrianGraph
from src.network.shortest_paths import ShortestPathCalculator

print("="*70)
print("COMPUTING & SAVING SHORTEST PATHS (FAST MODE)")
print("="*70)

start = time.time()

# Load graph
print("\n[1/3] Loading graph...")
graph = PedestrianGraph()
graph.load_from_database()
print(f"  Full dataset: {len(graph.N)} residential, {len(graph.M)} candidates")

# Sample
print("\n[2/3] Sampling...")
sampled_N = random.sample(list(graph.N), 500)
sampled_M = random.sample(list(graph.M), 50)
graph.N = set(sampled_N)
graph.M = set(sampled_M)
print(f"  Sampled: {len(graph.N)} residential, {len(graph.M)} candidates")

# Compute paths
print("\n[3/3] Computing shortest paths...")
calc = ShortestPathCalculator(graph)
calc.compute_all_distances(save_to_db=True)  # SAVE TO DB!

print(f"\n✓ Complete in {time.time()-start:.1f}s")
print(f"  Computed and saved {len(calc.distance_matrix):,} pairs to database")
print("="*70)

