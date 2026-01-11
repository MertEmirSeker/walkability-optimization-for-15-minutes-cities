"""
Map visualization using Folium.
Creates interactive maps showing residential locations, amenities,
allocated facilities, and WalkScore heatmaps.
"""
import folium
from folium import plugins
import pandas as pd
import numpy as np
from typing import Dict, Set, List, Tuple, Optional
import yaml
import osmnx as ox
from sqlalchemy import text
from src.network.pedestrian_graph import PedestrianGraph
from src.scoring.walkscore import WalkScoreCalculator
from src.utils.database import get_db_manager
from src.data_collection.balikesir_center import get_balikesir_center_polygon


class MapVisualizer:
    """Creates interactive maps for walkability visualization."""
    
    def __init__(self, graph: PedestrianGraph, scorer: WalkScoreCalculator,
                 config_path: str = "config.yaml"):
        """Initialize map visualizer."""
        self.graph = graph
        self.scorer = scorer
        self.db = graph.db
        
        # Load configuration
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        viz_config = self.config['visualization']
        self.map_center = viz_config['map_center']
        self.zoom_level = viz_config['zoom_level']
        self.colors = viz_config['colors']
    
    def create_base_map(self) -> folium.Map:
        """Create base map centered on Balıkesir."""
        m = folium.Map(
            location=[self.map_center['latitude'], self.map_center['longitude']],
            zoom_start=self.zoom_level,
            tiles=self.config['visualization']['tile_layer']
        )
        return m
    
    def add_residential_locations(self, m: folium.Map, max_points: Optional[int] = None):
        """Add residential locations to map.
        
        If max_points is None, plot all residential nodes.
        Uses original building coordinates (not snapped network nodes) for visualization.
        """
        print("Adding residential locations to map...")
        
        # Load residential locations from DB (use original coordinates for display)
        with self.db.get_session() as session:
            query = """
                SELECT rl.residential_id,
                       COALESCE(rl.original_latitude, n.latitude) AS lat,
                       COALESCE(rl.original_longitude, n.longitude) AS lon
                FROM residential_locations rl
                JOIN nodes n ON n.node_id = rl.snapped_node_id
                ORDER BY rl.residential_id
            """
            if max_points is not None:
                query += f" LIMIT {max_points}"
            
            result = session.execute(text(query))
            residential_coords = []
            for row in result:
                res_id, lat, lon = row
                if lat and lon:
                    residential_coords.append([float(lat), float(lon)])
        
        if residential_coords:
            # Add markers
            for lat, lon in residential_coords:
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=3,
                    popup="Residential",
                    color=self.colors['residential'],
                    fill=True,
                    fillColor=self.colors['residential'],
                    fillOpacity=0.6
                ).add_to(m)
        
        print(f"Added {len(residential_coords)} residential locations")
    
    def add_all_buildings(self, m: folium.Map, max_points: Optional[int] = None):
        """Add all buildings (residential + commercial + industrial + etc.) to map.
        
        Loads all buildings from OSM within the Balıkesir center polygon.
        """
        print("Loading all buildings from OSM...")
        
        try:
            center_poly = get_balikesir_center_polygon()
            tags = {"building": True}
            
            try:
                gdf = ox.features_from_polygon(center_poly, tags=tags)
            except AttributeError:
                gdf = ox.geometries_from_polygon(center_poly, tags=tags)
            
            if len(gdf) == 0:
                print("No buildings found in center polygon.")
                return
            
            # Extract centroids for point locations
            gdf["geometry"] = gdf.geometry.centroid
            gdf = gdf[gdf.geometry.type == "Point"]
            
            if max_points is not None:
                gdf = gdf.head(max_points)
            
            building_coords = []
            for idx, row in gdf.iterrows():
                geom = row.geometry
                if geom and hasattr(geom, 'y') and hasattr(geom, 'x'):
                    building_coords.append([geom.y, geom.x])
            
            if building_coords:
                # Add all buildings as light gray markers
                for lat, lon in building_coords:
                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=2,
                        popup="Building",
                        color='#888888',
                        fill=True,
                        fillColor='#cccccc',
                        fillOpacity=0.4,
                        weight=0.5
                    ).add_to(m)
            
            print(f"Added {len(building_coords)} buildings to map")
            
        except Exception as e:
            print(f"Error loading all buildings: {e}")
            # Fallback: just show residential if all buildings fails
            pass
    
    def add_existing_amenities(self, m: folium.Map):
        """Add existing amenities to map (using original coordinates)."""
        print("Adding existing amenities to map...")
        
        amenity_colors = {
            'grocery': '#2ecc71',
            'restaurant': '#3498db',
            'school': '#9b59b6'
        }
        
        with self.db.get_session() as session:
            # Get amenities with original coordinates
            query = """
                SELECT at.type_name, ea.node_id,
                       COALESCE(ea.original_latitude, n.latitude) AS lat,
                       COALESCE(ea.original_longitude, n.longitude) AS lon,
                       ea.name
                FROM existing_amenities ea
                JOIN amenity_types at ON at.amenity_type_id = ea.amenity_type_id
                JOIN nodes n ON n.node_id = ea.node_id
            """
            result = session.execute(text(query))
            
            for row in result:
                amenity_type, node_id, lat, lon, name = row
                if lat and lon:
                    color = amenity_colors.get(amenity_type, self.colors['existing_amenity'])
                    popup_text = f"Existing {amenity_type}"
                    if name:
                        popup_text += f": {name}"
                    
                    folium.CircleMarker(
                        location=[float(lat), float(lon)],
                        radius=5,
                        popup=popup_text,
                        color=color,
                        fill=True,
                        fillColor=color,
                        fillOpacity=0.8
                    ).add_to(m)
        
        print("Added existing amenities")
    
    def add_allocated_amenities(self, m: folium.Map, 
                                solution: Dict[str, Set[int]],
                                scenario: str = "optimized"):
        """Add allocated amenities from optimization solution (using original coordinates)."""
        print(f"Adding allocated amenities ({scenario}) to map...")
        
        amenity_colors = {
            'grocery': '#e74c3c',
            'restaurant': '#e67e22',
            'school': '#c0392b'
        }
        
        with self.db.get_session() as session:
            for amenity_type, node_ids in solution.items():
                color = amenity_colors.get(amenity_type, self.colors['allocated_amenity'])
                
                # CRITICAL: solution contains snapped_node_id, not node_id
                for snapped_node_id in node_ids:
                    # Get original coordinates from candidate_locations
                    query = """
                        SELECT COALESCE(cl.original_latitude, n.latitude) AS lat,
                               COALESCE(cl.original_longitude, n.longitude) AS lon
                        FROM candidate_locations cl
                        JOIN nodes n ON n.node_id = cl.snapped_node_id
                        WHERE cl.snapped_node_id = :snapped_node_id
                    """
                    result = session.execute(text(query), {'snapped_node_id': snapped_node_id})
                    row = result.first()
                    
                    lat, lon = None, None
                    if row:
                        lat, lon = row
                    
                    if lat and lon:
                        folium.Marker(
                            location=[float(lat), float(lon)],
                            popup=f"Allocated {amenity_type} ({scenario})",
                            icon=folium.Icon(color='red', icon='star', prefix='fa')
                        ).add_to(m)
        
        print("Added allocated amenities")
    
    def add_candidate_locations(self, m: folium.Map, max_points: int = 100):
        """Add candidate locations to map."""
        print("Adding candidate locations to map...")
        
        candidate_coords = []
        for cand_id in list(self.graph.M)[:max_points]:
            lat, lon = self.graph.get_node_coordinates(cand_id)
            if lat and lon:
                candidate_coords.append([lat, lon])
        
        if candidate_coords:
            for lat, lon in candidate_coords:
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=4,
                    popup="Candidate Location",
                    color=self.colors['candidate_location'],
                    fill=True,
                    fillColor=self.colors['candidate_location'],
                    fillOpacity=0.5
                ).add_to(m)
        
        print(f"Added {len(candidate_coords)} candidate locations")
    
    def add_walkscore_heatmap(self, m: folium.Map, scenario: str = 'baseline'):
        """Add WalkScore heatmap layer to map."""
        print(f"Adding WalkScore heatmap ({scenario})...")
        
        # Load WalkScores from database
        with self.db.get_session() as session:
            query = """
                SELECT ws.residential_id, ws.walkscore,
                       COALESCE(rl.original_latitude, n.latitude) AS lat,
                       COALESCE(rl.original_longitude, n.longitude) AS lon
                FROM walkability_scores ws
                JOIN nodes n ON ws.residential_id = n.node_id
                LEFT JOIN residential_locations rl ON rl.snapped_node_id = n.node_id
                WHERE ws.scenario = :scenario
            """
            result = session.execute(text(query), {'scenario': scenario})
            
            heat_data = []
            for row in result:
                residential_id, score, lat, lon = row
                if lat and lon:
                    # Weight by WalkScore (0-100 scale, normalize to 0-1)
                    heat_data.append([float(lat), float(lon), float(score)/100.0])
        
        if heat_data:
            # Create heatmap with gradient
            plugins.HeatMap(
                heat_data,
                min_opacity=0.3,
                max_zoom=18,
                radius=15,
                blur=20,
                gradient={
                    0.0: 'blue',
                    0.3: 'cyan', 
                    0.5: 'lime',
                    0.7: 'yellow',
                    1.0: 'red'
                }
            ).add_to(m)
            print(f"Added heatmap with {len(heat_data)} points")
        else:
            print(f"No scores found for scenario: {scenario}")
    
    def add_residential_markers(self, m, scores: Dict[int, float]):
        """
        Add residential locations to map, colored by WalkScore.
        
        Args:
            m: Folium map object
            scores: Dict mapping residential_id -> WalkScore
        """
        print("Adding residential markers to map...")
        
        # Color scale function
        def get_color(score):
            if score >= 90: return "#2ecc71"  # Emerald
            if score >= 70: return "#f1c40f"  # Sunflower
            if score >= 50: return "#e67e22"  # Carrot
            return "#e74c3c"  # Alizarin
        
        # Add markers
        count = 0
        for residential_id, score in scores.items():
            # Get coordinates
            # optimization: look up from graph nodes if possible, or query db
            # For speed, let's assume we can get coords from graph.N nodes?
            # graph.residential_buildings has (res_id, snapped_id)
            
            # Find the snapped node ID first
            snapped_id = None
            for rid, sid in self.graph.residential_buildings:
                if rid == residential_id:
                    snapped_id = sid
                    break
            
            if snapped_id:
                lat, lon = self.graph.get_node_coordinates(snapped_id)
                if lat and lon:
                    color = get_color(score)
                    
                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=3,
                        color=color,
                        fill=True,
                        fill_color=color,
                        fill_opacity=0.7,
                        popup=f"Score: {score:.1f}",
                        weight=0
                    ).add_to(m)
                    count += 1
                    
        print(f"Added {count} residential markers")
    
    def add_fifteen_minute_circles(self, m: folium.Map, 
                                   solution: Dict[str, Set[int]]):
        """Add 15-minute walking radius circles around allocated amenities."""
        print("Adding 15-minute walking radius circles...")
        
        # 15 minutes = 1080 meters at 1.2 m/s
        radius_meters = self.config['walkscore']['fifteen_minutes_meters']
        
        for amenity_type, node_ids in solution.items():
            for node_id in node_ids:
                lat, lon = self.graph.get_node_coordinates(node_id)
                if lat and lon:
                    folium.Circle(
                        location=[lat, lon],
                        radius=radius_meters,
                        popup=f"15-min radius: {amenity_type}",
                        color='green',
                        fill=True,
                        fillColor='green',
                        fillOpacity=0.1
                    ).add_to(m)
        
        print("Added 15-minute radius circles")
    
    def create_baseline_map(self, output_path: str = "visualizations/baseline_map.html"):
        """Create map showing baseline state."""
        print("Creating baseline map...")
        
        m = self.create_base_map()
        self.add_all_buildings(m)  # Add all buildings as background
        self.add_residential_locations(m)  # Blue dots for residentials
        self.add_existing_amenities(m)
        self.add_candidate_locations(m)
        
        # Save map
        import os
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        m.save(output_path)
        print(f"Baseline map saved to {output_path}")
        
        return m
    
    def create_optimized_map(self, solution: Dict[str, Set[int]],
                            scenario: str = "optimized",
                            output_path: str = "visualizations/optimized_map.html"):
        """Create map showing optimized solution."""
        print(f"Creating optimized map ({scenario})...")
        
        m = self.create_base_map()
        self.add_all_buildings(m)  # Add all buildings as background
        self.add_residential_locations(m)  # Blue dots
        self.add_existing_amenities(m)
        self.add_allocated_amenities(m, solution, scenario)
        self.add_fifteen_minute_circles(m, solution)
        
        # Add legend
        self._add_legend(m)
        
        # Save map
        import os
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        m.save(output_path)
        print(f"Optimized map saved to {output_path}")
        
        return m
    
    def create_baseline_heatmap(self, output_path: str = "visualizations/baseline_heatmap.html"):
        """Create HEATMAP-ONLY baseline map with colored markers by WalkScore."""
        print("Creating baseline heatmap...")
        
        m = self.create_base_map()
        self.add_all_buildings(m, max_points=10000)  # Background
        self.add_existing_amenities(m)
        
        # Load baseline scores and add colored markers
        with self.db.get_session() as session:
            query = "SELECT residential_id, walkscore FROM walkability_scores WHERE scenario = 'baseline'"
            result = session.execute(text(query))
            baseline_scores = {row[0]: float(row[1]) for row in result}
        
        self.add_residential_markers(m, baseline_scores)  # Colored dots by score!
        
        # Save
        import os
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        m.save(output_path)
        print(f"Baseline heatmap saved to {output_path}")
        
        return m
    
    def create_optimized_heatmap(self, solution: Dict[str, Set[int]],
                                 scenario: str = "optimized",
                                 output_path: str = "visualizations/optimized_heatmap.html"):
        """Create HEATMAP-ONLY optimized map with colored markers by WalkScore."""
        print(f"Creating optimized heatmap ({scenario})...")
        
        m = self.create_base_map()
        self.add_all_buildings(m, max_points=10000)  # Background
        self.add_existing_amenities(m)
        self.add_allocated_amenities(m, solution, scenario)
        
        # Load scores and add colored markers
        with self.db.get_session() as session:
            query = "SELECT residential_id, walkscore FROM walkability_scores WHERE scenario = :scenario"
            result = session.execute(text(query), {'scenario': scenario})
            scores = {row[0]: float(row[1]) for row in result}
        
        self.add_residential_markers(m, scores)  # Colored dots by score!
        self.add_fifteen_minute_circles(m, solution)
        
        # Save
        import os
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        m.save(output_path)
        print(f"Optimized heatmap saved to {output_path}")
        
        return m
    
    def create_comparison_map(self, solution: Dict[str, Set[int]],
                            scenario: str = "optimized",
                            output_path: str = "visualizations/comparison_map.html"):
        """Create side-by-side comparison map."""
        print("Creating comparison map...")
        
        m = self.create_base_map()
        
        # Add baseline elements
        self.add_all_buildings(m, max_points=5000)  # Add buildings as background
        self.add_residential_locations(m, max_points=200)
        self.add_existing_amenities(m)
        
        # Add optimized elements
        self.add_allocated_amenities(m, solution, scenario)
        self.add_fifteen_minute_circles(m, solution)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Save map
        import os
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        m.save(output_path)
        print(f"Comparison map saved to {output_path}")
        
        return m
    
    def _add_legend(self, m: folium.Map):
        """Add legend to map."""
        legend_html = '''
        <div style="position: fixed; 
                     bottom: 50px; left: 50px; width: 200px; height: 150px; 
                     background-color: white; border:2px solid grey; z-index:9999; 
                     font-size:14px; padding: 10px">
        <h4>Legend</h4>
        <p><span style="color:blue;">●</span> Residential</p>
        <p><span style="color:green;">●</span> Existing Amenity</p>
        <p><span style="color:red;">★</span> Allocated Amenity</p>
        <p><span style="color:orange;">●</span> Candidate Location</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))


if __name__ == "__main__":
    from src.network.pedestrian_graph import PedestrianGraph
    from src.network.shortest_paths import ShortestPathCalculator
    from src.scoring.walkscore import WalkScoreCalculator
    
    print("Loading data...")
    graph = PedestrianGraph()
    graph.load_from_database()
    
    path_calc = ShortestPathCalculator(graph)
    path_calc.load_from_database()
    
    scorer = WalkScoreCalculator(graph, path_calc)
    
    # Create visualizer
    visualizer = MapVisualizer(graph, scorer)
    
    # Create baseline map
    visualizer.create_baseline_map()
    
    print("\nVisualization complete!")

