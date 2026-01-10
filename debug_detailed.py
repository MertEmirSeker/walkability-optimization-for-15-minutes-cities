"""
Detailed debug - print every step.
"""
from src.network.pedestrian_graph import PedestrianGraph
from src.network.shortest_paths import ShortestPathCalculator
from src.scoring.walkscore import WalkScoreCalculator
from sqlalchemy import text

graph = PedestrianGraph()
graph.load_from_database()

path_calc = ShortestPathCalculator(graph)
path_calc.load_from_database()

scorer = WalkScoreCalculator(graph, path_calc)

# Find pair
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
    test_residential, test_candidate, dist_in_db = row

print("="*70)
print(f"Testing residential={test_residential}, candidate={test_candidate}")
print(f"Distance in DB: {dist_in_db:.2f}m")
print("="*70)

# Manually check allocated_amenities
allocated_amenities = {'grocery': {test_candidate}}

print(f"\n1. Check allocated_amenities parameter:")
print(f"   allocated_amenities = {allocated_amenities}")
print(f"   'grocery' in allocated_amenities: {'grocery' in allocated_amenities}")
print(f"   allocated_amenities['grocery']: {allocated_amenities['grocery']}")

print(f"\n2. Check existing grocery locations:")
existing_grocery = graph.get_all_amenity_locations('grocery')
print(f"   Count: {len(existing_grocery)}")
print(f"   First 5: {list(existing_grocery)[:5]}")

print(f"\n3. Check if allocated candidate will be added:")
all_locations = graph.get_all_amenity_locations('grocery')
print(f"   Before adding: {len(all_locations)} locations")

if 'grocery' in allocated_amenities:
    all_locations.update(allocated_amenities['grocery'])
    print(f"   After adding: {len(all_locations)} locations")
    print(f"   Is {test_candidate} in all_locations? {test_candidate in all_locations}")

print(f"\n4. Find nearest distance:")
min_dist = path_calc.D_infinity
for loc_id in all_locations:
    dist = path_calc.get_distance(test_residential, loc_id)
    if dist < min_dist:
        min_dist = dist
        nearest_loc = loc_id
        
print(f"   Nearest location: {nearest_loc}")
print(f"   Distance: {min_dist:.2f}m")
print(f"   Is it the candidate? {nearest_loc == test_candidate}")

print(f"\n5. Check distance to candidate specifically:")
dist_to_cand = path_calc.get_distance(test_residential, test_candidate)
print(f"   Distance from path_calc: {dist_to_cand:.2f}m")
print(f"   Distance from DB: {dist_in_db:.2f}m")
print(f"   Match? {abs(dist_to_cand - dist_in_db) < 1.0}")

print("="*70)

