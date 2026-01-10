"""
Comprehensive visualization system for walkability optimization results.

Features:
- Interactive maps with folium
- WalkScore heatmaps
- Before/after comparisons
- Network visualization
- Statistical plots
"""
import folium
from folium import plugins
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from typing import Dict, Set, List, Optional
from sqlalchemy import text
import json


class MapPlotter:
    """Create interactive maps for walkability visualization."""
    
    def __init__(self, graph, scorer, db):
        """Initialize map plotter."""
        self.graph = graph
        self.scorer = scorer
        self.db = db
        
        # Balıkesir center
        self.center_lat = 39.6400
        self.center_lon = 27.8750
    
    def create_base_map(self, zoom_start=13):
        """Create base folium map centered on Balıkesir."""
        m = folium.Map(
            location=[self.center_lat, self.center_lon],
            zoom_start=zoom_start,
            tiles='OpenStreetMap'
        )
        return m
    
    def plot_walkability_map(self, scores: Dict[int, float], 
                            solution: Optional[Dict[str, Set[int]]] = None,
                            output_file: str = "walkability_map.html"):
        """
        Create interactive walkability map with WalkScore heatmap.
        
        Args:
            scores: Dict mapping residential_id -> WalkScore
            solution: Optional allocation solution to overlay
            output_file: Output HTML file
        """
        print(f"Creating walkability map...")
        
        m = self.create_base_map()
        
        # Add WalkScore heatmap
        heat_data = []
        
        for residential_id, score in scores.items():
            # Get coordinates
            with self.db.get_session() as session:
                query = """
                    SELECT latitude, longitude FROM residential_locations 
                    WHERE node_id = :node_id
                """
                result = session.execute(text(query), {'node_id': residential_id})
                row = result.fetchone()
                
                if row:
                    lat, lon = row
                    # Weight by score (higher score = more intense)
                    heat_data.append([lat, lon, score/100.0])
        
        # Add heatmap layer
        plugins.HeatMap(
            heat_data,
            min_opacity=0.4,
            max_val=1.0,
            radius=15,
            blur=20,
            gradient={
                0.0: 'red',
                0.5: 'yellow',
                1.0: 'green'
            }
        ).add_to(m)
        
        # Add existing amenities
        self._add_existing_amenities(m)
        
        # Add allocated amenities if solution provided
        if solution:
            self._add_allocated_amenities(m, solution)
        
        # Add legend
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; right: 50px; width: 200px; height: 150px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:14px; padding: 10px">
        <p><strong>WalkScore Legend</strong></p>
        <p><span style="color:green;">●</span> High (75-100)</p>
        <p><span style="color:yellow;">●</span> Medium (40-75)</p>
        <p><span style="color:red;">●</span> Low (0-40)</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Save map
        m.save(output_file)
        print(f"  ✓ Map saved to {output_file}")
        
        return m
    
    def _add_existing_amenities(self, m):
        """Add existing amenities to map."""
        amenity_colors = {
            'grocery': 'blue',
            'restaurant': 'orange',
            'school': 'purple',
            'healthcare': 'red'
        }
        
        with self.db.get_session() as session:
            query = """
                SELECT al.latitude, al.longitude, at.type_name
                FROM amenity_locations al
                JOIN amenity_types at ON al.amenity_type_id = at.amenity_type_id
            """
            result = session.execute(text(query))
            
            for row in result:
                lat, lon, amenity_type = row
                color = amenity_colors.get(amenity_type, 'gray')
                
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=4,
                    color=color,
                    fill=True,
                    fillOpacity=0.7,
                    popup=f"Existing {amenity_type}"
                ).add_to(m)
    
    def _add_allocated_amenities(self, m, solution: Dict[str, Set[int]]):
        """Add allocated amenities to map."""
        amenity_icons = {
            'grocery': 'shopping-cart',
            'restaurant': 'cutlery',
            'school': 'book',
            'healthcare': 'plus-sign'
        }
        
        for amenity_type, node_ids in solution.items():
            for node_id in node_ids:
                with self.db.get_session() as session:
                    query = """
                        SELECT cl.latitude, cl.longitude
                        FROM candidate_locations cl
                        WHERE cl.node_id = :node_id
                    """
                    result = session.execute(text(query), {'node_id': node_id})
                    row = result.fetchone()
                    
                    if row:
                        lat, lon = row
                        icon = amenity_icons.get(amenity_type, 'star')
                        
                        folium.Marker(
                            location=[lat, lon],
                            icon=folium.Icon(color='green', icon=icon, prefix='glyphicon'),
                            popup=f"NEW {amenity_type}"
                        ).add_to(m)
    
    def plot_comparison_map(self, baseline_scores: Dict[int, float],
                           optimized_scores: Dict[int, float],
                           solution: Dict[str, Set[int]],
                           output_file: str = "comparison_map.html"):
        """
        Create side-by-side comparison of before/after.
        
        Args:
            baseline_scores: Baseline WalkScores
            optimized_scores: Optimized WalkScores
            solution: Allocation solution
            output_file: Output HTML file
        """
        print(f"Creating comparison map...")
        
        # Create dual map
        m = plugins.DualMap(
            location=[self.center_lat, self.center_lon],
            zoom_start=13,
            tiles='OpenStreetMap'
        )
        
        # Left map: Baseline
        heat_data_baseline = []
        for residential_id, score in baseline_scores.items():
            with self.db.get_session() as session:
                query = """
                    SELECT latitude, longitude FROM residential_locations 
                    WHERE node_id = :node_id
                """
                result = session.execute(text(query), {'node_id': residential_id})
                row = result.fetchone()
                
                if row:
                    lat, lon = row
                    heat_data_baseline.append([lat, lon, score/100.0])
        
        plugins.HeatMap(heat_data_baseline, name="Baseline").add_to(m.m1)
        
        # Right map: Optimized
        heat_data_optimized = []
        for residential_id, score in optimized_scores.items():
            with self.db.get_session() as session:
                query = """
                    SELECT latitude, longitude FROM residential_locations 
                    WHERE node_id = :node_id
                """
                result = session.execute(text(query), {'node_id': residential_id})
                row = result.fetchone()
                
                if row:
                    lat, lon = row
                    heat_data_optimized.append([lat, lon, score/100.0])
        
        plugins.HeatMap(heat_data_optimized, name="Optimized").add_to(m.m2)
        
        # Add allocated amenities to right map
        self._add_allocated_amenities(m.m2, solution)
        
        m.save(output_file)
        print(f"  ✓ Comparison map saved to {output_file}")
        
        return m
    
    def plot_network_graph(self, output_file: str = "network_graph.html"):
        """Plot pedestrian network graph."""
        print(f"Creating network graph...")
        
        m = self.create_base_map()
        
        # Add edges
        with self.db.get_session() as session:
            query = """
                SELECT e.source_node, e.target_node, e.length,
                       n1.latitude as lat1, n1.longitude as lon1,
                       n2.latitude as lat2, n2.longitude as lon2
                FROM network_edges e
                JOIN network_nodes n1 ON e.source_node = n1.node_id
                JOIN network_nodes n2 ON e.target_node = n2.node_id
                LIMIT 1000
            """
            result = session.execute(text(query))
            
            for row in result:
                source, target, length, lat1, lon1, lat2, lon2 = row
                
                folium.PolyLine(
                    locations=[[lat1, lon1], [lat2, lon2]],
                    color='blue',
                    weight=1,
                    opacity=0.3
                ).add_to(m)
        
        m.save(output_file)
        print(f"  ✓ Network graph saved to {output_file}")
        
        return m


class StatisticsPlotter:
    """Create statistical plots for analysis."""
    
    def __init__(self):
        """Initialize statistics plotter."""
        sns.set_style("whitegrid")
        plt.rcParams['figure.figsize'] = (12, 8)
    
    def plot_walkscore_distribution(self, scores: Dict[int, float],
                                   output_file: str = "walkscore_distribution.png"):
        """Plot WalkScore distribution histogram."""
        print(f"Creating WalkScore distribution plot...")
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        score_values = list(scores.values())
        
        # Histogram
        axes[0, 0].hist(score_values, bins=50, edgecolor='black', alpha=0.7)
        axes[0, 0].set_xlabel('WalkScore')
        axes[0, 0].set_ylabel('Frequency')
        axes[0, 0].set_title('WalkScore Distribution')
        axes[0, 0].axvline(np.mean(score_values), color='red', linestyle='--', 
                          label=f'Mean: {np.mean(score_values):.2f}')
        axes[0, 0].legend()
        
        # Box plot
        axes[0, 1].boxplot(score_values, vert=True)
        axes[0, 1].set_ylabel('WalkScore')
        axes[0, 1].set_title('WalkScore Box Plot')
        
        # CDF
        sorted_scores = np.sort(score_values)
        cdf = np.arange(1, len(sorted_scores) + 1) / len(sorted_scores)
        axes[1, 0].plot(sorted_scores, cdf)
        axes[1, 0].set_xlabel('WalkScore')
        axes[1, 0].set_ylabel('Cumulative Probability')
        axes[1, 0].set_title('Cumulative Distribution Function')
        axes[1, 0].grid(True)
        
        # Statistics table
        stats_text = f"""
        Statistics:
        Mean: {np.mean(score_values):.2f}
        Median: {np.median(score_values):.2f}
        Std: {np.std(score_values):.2f}
        Min: {np.min(score_values):.2f}
        Max: {np.max(score_values):.2f}
        Q25: {np.percentile(score_values, 25):.2f}
        Q75: {np.percentile(score_values, 75):.2f}
        
        Coverage:
        Score ≥ 50: {sum(1 for s in score_values if s >= 50)} ({100*sum(1 for s in score_values if s >= 50)/len(score_values):.1f}%)
        Score ≥ 75: {sum(1 for s in score_values if s >= 75)} ({100*sum(1 for s in score_values if s >= 75)/len(score_values):.1f}%)
        """
        axes[1, 1].text(0.1, 0.5, stats_text, fontsize=12, verticalalignment='center',
                       family='monospace')
        axes[1, 1].axis('off')
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"  ✓ Distribution plot saved to {output_file}")
        
        plt.close()
    
    def plot_comparison(self, baseline_scores: Dict[int, float],
                       optimized_scores: Dict[int, float],
                       output_file: str = "comparison.png"):
        """Plot before/after comparison."""
        print(f"Creating comparison plot...")
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        baseline_values = list(baseline_scores.values())
        optimized_values = list(optimized_scores.values())
        improvements = [optimized_scores[rid] - baseline_scores[rid] 
                       for rid in baseline_scores.keys()]
        
        # Side-by-side histogram
        axes[0, 0].hist([baseline_values, optimized_values], bins=30, 
                       label=['Baseline', 'Optimized'], alpha=0.7, edgecolor='black')
        axes[0, 0].set_xlabel('WalkScore')
        axes[0, 0].set_ylabel('Frequency')
        axes[0, 0].set_title('Before vs After')
        axes[0, 0].legend()
        
        # Improvement histogram
        axes[0, 1].hist(improvements, bins=30, edgecolor='black', alpha=0.7, color='green')
        axes[0, 1].set_xlabel('WalkScore Improvement')
        axes[0, 1].set_ylabel('Frequency')
        axes[0, 1].set_title('Improvement Distribution')
        axes[0, 1].axvline(np.mean(improvements), color='red', linestyle='--',
                          label=f'Mean: {np.mean(improvements):.2f}')
        axes[0, 1].legend()
        
        # Scatter plot
        axes[1, 0].scatter(baseline_values, optimized_values, alpha=0.3)
        axes[1, 0].plot([0, 100], [0, 100], 'r--', label='No change')
        axes[1, 0].set_xlabel('Baseline WalkScore')
        axes[1, 0].set_ylabel('Optimized WalkScore')
        axes[1, 0].set_title('Scatter Plot')
        axes[1, 0].legend()
        
        # Statistics comparison
        comparison_text = f"""
        Comparison Statistics:
        
        Baseline:
          Mean: {np.mean(baseline_values):.2f}
          Median: {np.median(baseline_values):.2f}
          Coverage ≥50: {100*sum(1 for s in baseline_values if s >= 50)/len(baseline_values):.1f}%
        
        Optimized:
          Mean: {np.mean(optimized_values):.2f}
          Median: {np.median(optimized_values):.2f}
          Coverage ≥50: {100*sum(1 for s in optimized_values if s >= 50)/len(optimized_values):.1f}%
        
        Improvement:
          Mean: {np.mean(improvements):.2f}
          Total increase: {sum(improvements):.2f}
          % improved: {100*sum(1 for i in improvements if i > 0)/len(improvements):.1f}%
        """
        axes[1, 1].text(0.1, 0.5, comparison_text, fontsize=11, verticalalignment='center',
                       family='monospace')
        axes[1, 1].axis('off')
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"  ✓ Comparison plot saved to {output_file}")
        
        plt.close()
    
    def plot_convergence(self, history: List[float],
                        output_file: str = "convergence.png"):
        """Plot optimization convergence."""
        print(f"Creating convergence plot...")
        
        plt.figure(figsize=(12, 6))
        plt.plot(history, marker='o', linewidth=2)
        plt.xlabel('Iteration')
        plt.ylabel('Objective Value (Avg WalkScore)')
        plt.title('Optimization Convergence')
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"  ✓ Convergence plot saved to {output_file}")
        
        plt.close()


if __name__ == "__main__":
    print("Visualization module")
    print("Use MapPlotter and StatisticsPlotter classes for creating visualizations")

