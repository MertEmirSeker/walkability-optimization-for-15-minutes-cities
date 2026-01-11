#!/usr/bin/env python
"""Quick test for map visualization only."""

from src.network.pedestrian_graph import PedestrianGraph
from src.network.shortest_paths import ShortestPathCalculator
from src.scoring.walkscore import WalkScoreCalculator
from src.visualization.map_visualizer import MapVisualizer

print("🗺️  Quick Map Visualization Test")
print("=" * 50)

# Load graph
print("Loading graph...")
graph = PedestrianGraph()
graph.load_from_database()

# Load path calculator (needed for scorer)
print("Loading path calculator...")
path_calc = ShortestPathCalculator(graph)
path_calc.load_from_database()

# Create scorer
print("Creating scorer...")
scorer = WalkScoreCalculator(graph, path_calc)

# Create visualizer
print("Creating visualizer...")
visualizer = MapVisualizer(graph, scorer)

# Create baseline map
print("\n📍 Creating baseline map...")
visualizer.create_baseline_map("visualizations/test_baseline_map.html")

print("\n✅ Done! Check: test_baseline_map.html")
print("   You should see:")
print("   - Gray buildings (background)")
print("   - Blue dots (residential locations)")
print("   - Colored dots (existing amenities)")
print("   - Orange markers (candidate locations)")
