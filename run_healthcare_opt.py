from src.network.pedestrian_graph import PedestrianGraph
from src.network.shortest_paths import ShortestPathCalculator
from src.scoring.walkscore import WalkScoreCalculator
from src.algorithms.greedy import GreedyOptimizer

print("Loading graph...")
graph = PedestrianGraph()
graph.load_from_database()

print("Loading distances...")
path_calc = ShortestPathCalculator(graph)
path_calc.load_from_database()

scorer = WalkScoreCalculator(graph, path_calc)

print("Running Healthcare optimization...")
optimizer = GreedyOptimizer(graph, scorer)
# Optimize ONLY healthcare, append to greedy_k3
solution = optimizer.optimize(k=3, amenity_types=['healthcare'])

print("Saving results...")
optimizer.save_results(solution, scenario='greedy_k3')
print("Done!")
