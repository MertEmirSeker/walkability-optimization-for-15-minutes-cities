"""
OpenStreetMap data loader for Balıkesir city center.
Fetches pedestrian network, residential locations, amenities, and candidate locations.
All data is restricted to the Karesi + Altıeylül city center polygon.
"""
import osmnx as ox
import pandas as pd
import numpy as np
from shapely.geometry import Point
from typing import Dict, List, Tuple
import yaml
from sqlalchemy import text
import sys
import time
import threading
import itertools

from src.utils.database import get_db_manager
from src.data_collection.balikesir_center import get_balikesir_center_polygon


class OSMDataLoader:
    """Loads OSM data for walkability optimization."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize OSM loader with configuration."""
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.balikesir_config = self.config['balikesir']
        self.osm_config = self.config['osm']
        self.db = get_db_manager(config_path)
        # center polygon (Karesi + Altıeylül)
        self.center_poly = get_balikesir_center_polygon()
        
    def get_boundary(self) -> Tuple[float, float, float, float]:
        """Get Balıkesir city center boundary coordinates (for visualization only)."""
        boundary = self.balikesir_config['boundary']
        return (
            boundary['north'],
            boundary['south'],
            boundary['east'],
            boundary['west'],
        )
    
    def load_pedestrian_network(self) -> ox.graph:
        """
        Load pedestrian network for Balıkesir city center polygon.
        """
        print("Loading pedestrian network from OSM (graph_from_polygon, city center)...")

        stop_spinner = threading.Event()

        def _spinner():
            for ch in itertools.cycle("|/-\\"):
                if stop_spinner.is_set():
                    break
                sys.stdout.write(f"\rDownloading pedestrian network {ch}")
                sys.stdout.flush()
                time.sleep(0.3)
            sys.stdout.write("\r" + " " * 60 + "\r")
            sys.stdout.flush()

        spinner_thread = threading.Thread(target=_spinner, daemon=True)
        spinner_thread.start()

        try:
            G = ox.graph_from_polygon(
                self.center_poly,
                network_type="walk",
                simplify=True,
            )
        finally:
            stop_spinner.set()
            spinner_thread.join()

        print(f"Loaded pedestrian network with {len(G.nodes)} nodes and {len(G.edges)} edges")
        return G
    
    def load_residential_locations(self) -> pd.DataFrame:
        """Load residential buildings/addresses from OSM."""
        print("Loading residential locations from OSM...")
        # Residential buildings restricted to center polygon
        # Başta building=True ile tüm binaları alıp sonra konut olmayanları eleyeceğiz.
        tags = {"building": True}

        try:
            try:
                gdf = ox.features_from_polygon(self.center_poly, tags=tags)
            except AttributeError:
                gdf = ox.geometries_from_polygon(self.center_poly, tags=tags)

            if len(gdf) == 0:
                print("No buildings found in center polygon.")
                return gdf

            # Sadece konut olabilecek building tipleri kalsın
            allowed_buildings = {
                "residential",
                "house",
                "apartments",
                "detached",
                "semidetached_house",
                "terrace",
                "yes",
            }

            bcol = gdf.get("building")
            if bcol is not None:
                gdf = gdf[(bcol.isna()) | (bcol.isin(allowed_buildings))].copy()

            # Extract centroids for point locations
            gdf["geometry"] = gdf.geometry.centroid
            gdf = gdf[gdf.geometry.type == "Point"]

            print(f"Found {len(gdf)} residential locations")
            return gdf

        except Exception as e:
            print(f"Error loading residential locations: {e}")
            return pd.DataFrame()
    
    def load_amenities(self, amenity_type: str) -> pd.DataFrame:
        """Load specific amenity type from OSM."""
        # Define tags explicitly per amenity type (avoid complex config parsing)
        if amenity_type == "grocery":
            tags = {"shop": ["supermarket", "convenience", "grocery"]}
        elif amenity_type == "restaurant":
            tags = {"amenity": ["restaurant", "fast_food", "cafe"]}
        elif amenity_type == "school":
            tags = {"amenity": ["school", "kindergarten"]}
        else:
            tags = {}

        print(f"Loading {amenity_type} amenities from OSM...")

        try:
            try:
                gdf = ox.features_from_polygon(self.center_poly, tags=tags)
            except AttributeError:
                gdf = ox.geometries_from_polygon(self.center_poly, tags=tags)

            if len(gdf) > 0:
                gdf["geometry"] = gdf.geometry.centroid
                gdf = gdf[gdf.geometry.type == "Point"]

            print(f"Found {len(gdf)} {amenity_type} amenities")
            return gdf

        except Exception as e:
            print(f"Error loading {amenity_type} amenities: {e}")
            return pd.DataFrame()
    
    def load_candidate_locations(self) -> pd.DataFrame:
        """Load candidate locations (parking lots, empty lots) from OSM."""
        print("Loading candidate locations from OSM...")

        # Primary: parking amenities; fallback: commercial/retail landuse
        tags_primary = {"amenity": "parking"}
        tags_fallback = {"landuse": ["commercial", "retail"]}

        try:
            try:
                gdf = ox.features_from_polygon(self.center_poly, tags=tags_primary)
            except AttributeError:
                gdf = ox.geometries_from_polygon(self.center_poly, tags=tags_primary)

            if len(gdf) == 0:
                print("No parking lots found, using commercial areas as candidates...")
                try:
                    gdf = ox.features_from_polygon(self.center_poly, tags=tags_fallback)
                except AttributeError:
                    gdf = ox.geometries_from_polygon(self.center_poly, tags=tags_fallback)

            gdf["geometry"] = gdf.geometry.centroid
            gdf = gdf[gdf.geometry.type == "Point"]

            print(f"Found {len(gdf)} candidate locations")
            return gdf

        except Exception as e:
            print(f"Error loading candidate locations: {e}")
            return pd.DataFrame()
    
    def save_network_to_db(self, G: ox.graph):
        """Save pedestrian network graph to database."""
        print("Saving network to database...")
        
        with self.db.get_session() as session:
            # Insert nodes
            nodes_data = []
            for node_id, data in G.nodes(data=True):
                lat = data.get('y', 0)
                lon = data.get('x', 0)
                
                nodes_data.append({
                    'osm_id': node_id,
                    'node_type': 'network',
                    'latitude': lat,
                    'longitude': lon
                })
            
            # Batch insert nodes (no artificial limit)
            for node_data in nodes_data:
                query = """
                    INSERT INTO nodes (osm_id, node_type, latitude, longitude, geom)
                    VALUES (:osm_id, :node_type, :latitude, :longitude, 
                            ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326))
                    ON CONFLICT (osm_id) DO NOTHING
                """
                session.execute(text(query), node_data)
            
            # Insert edges
            edges_data = []
            for u, v, data in G.edges(data=True):
                # Ensure plain float (avoid np.float64 showing up in SQL)
                raw_length = data.get('length', 0) or 0.0
                length = float(raw_length)
                edges_data.append({
                    'from_osm_id': u,
                    'to_osm_id': v,
                    'length_meters': length
                })
            
            # Batch insert edges
            for edge_data in edges_data:  # tiny enough area, no need to slice
                query = """
                    INSERT INTO edges (from_node_id, to_node_id, length_meters)
                    SELECT 
                        (SELECT node_id FROM nodes WHERE osm_id = :from_osm_id),
                        (SELECT node_id FROM nodes WHERE osm_id = :to_osm_id),
                        :length_meters
                    WHERE EXISTS (SELECT 1 FROM nodes WHERE osm_id = :from_osm_id)
                      AND EXISTS (SELECT 1 FROM nodes WHERE osm_id = :to_osm_id)
                    ON CONFLICT (from_node_id, to_node_id) DO NOTHING
                """
                session.execute(text(query), edge_data)
        
        print("Network saved to database")
    
    def save_locations_to_db(self, gdf: pd.DataFrame, location_type: str, 
                            amenity_type: str = None):
        """Save locations (residential, amenities, candidates) to database."""
        print(f"Saving {location_type} locations to database...")
        
        with self.db.get_session() as session:
            for idx, row in gdf.iterrows():
                geom = row.geometry
                lat = geom.y
                lon = geom.x
                # Normalize OSM id to plain integer
                osm_raw = row.get("osmid", None)
                osm_id = None
                if osm_raw is not None and not pd.isna(osm_raw):
                    osm_id = osm_raw
                else:
                    osm_id = idx

                # Handle cases like ('node', 123456) or [123456]
                if isinstance(osm_id, (list, tuple)):
                    first = osm_id[0]
                    if isinstance(first, (list, tuple)) and len(first) > 1:
                        osm_id = first[1]
                    else:
                        osm_id = first

                try:
                    osm_id = int(osm_id)
                except Exception:
                    # Fallback to numeric index if conversion fails
                    try:
                        osm_id = int(idx[1]) if isinstance(idx, (list, tuple)) and len(idx) > 1 else int(idx)
                    except Exception:
                        continue
                
                # Insert node
                node_query = """
                    INSERT INTO nodes (osm_id, node_type, latitude, longitude, geom)
                    VALUES (:osm_id, :node_type, :latitude, :longitude,
                            ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326))
                    ON CONFLICT (osm_id) DO UPDATE SET
                        latitude = EXCLUDED.latitude,
                        longitude = EXCLUDED.longitude
                    RETURNING node_id
                """
                result = session.execute(text(node_query), {
                    'osm_id': osm_id,
                    'node_type': location_type,
                    'latitude': lat,
                    'longitude': lon
                })
                node_id = result.scalar()
                
                # Insert into specific table
                if location_type == 'residential':
                    res_query = """
                        INSERT INTO residential_locations (node_id, address, building_type)
                        VALUES (:node_id, :address, :building_type)
                        ON CONFLICT (node_id) DO NOTHING
                    """
                    session.execute(text(res_query), {
                        'node_id': node_id,
                        'address': row.get('addr:street', ''),
                        'building_type': row.get('building', 'residential')
                    })
                
                elif location_type == 'amenity' and amenity_type:
                    # Get amenity_type_id
                    type_query = "SELECT amenity_type_id FROM amenity_types WHERE type_name = :type_name"
                    type_result = session.execute(text(type_query), {'type_name': amenity_type})
                    amenity_type_id = type_result.scalar()
                    
                    if amenity_type_id:
                        amenity_query = """
                            INSERT INTO existing_amenities (node_id, amenity_type_id, name, osm_id)
                            VALUES (:node_id, :amenity_type_id, :name, :osm_id)
                            ON CONFLICT (node_id, amenity_type_id) DO NOTHING
                        """
                        session.execute(text(amenity_query), {
                            'node_id': node_id,
                            'amenity_type_id': amenity_type_id,
                            'name': row.get('name', ''),
                            'osm_id': osm_id
                        })
                
                elif location_type == 'candidate':
                    cand_query = """
                        INSERT INTO candidate_locations (node_id, capacity, location_type)
                        VALUES (:node_id, :capacity, :location_type)
                        ON CONFLICT (node_id) DO NOTHING
                    """
                    session.execute(text(cand_query), {
                        'node_id': node_id,
                        'capacity': 1,  # Default capacity
                        'location_type': row.get('amenity', 'parking')
                    })
        
        print(f"Saved {len(gdf)} {location_type} locations")
    
    def load_all_data(self):
        """Load all data from OSM and save to database."""
        print("=" * 60)
        print("Loading OSM data for Balıkesir city center")
        print("=" * 60)
        
        # Load pedestrian network
        G = self.load_pedestrian_network()
        if G is not None and len(G.nodes) > 0:
            self.save_network_to_db(G)
        
        # Load residential locations
        residential_gdf = self.load_residential_locations()
        if len(residential_gdf) > 0:
            self.save_locations_to_db(residential_gdf, 'residential')
        
        # Load amenities
        for amenity_type in ['grocery', 'restaurant', 'school']:
            amenity_gdf = self.load_amenities(amenity_type)
            if len(amenity_gdf) > 0:
                self.save_locations_to_db(amenity_gdf, 'amenity', amenity_type)
        
        # Load candidate locations
        candidate_gdf = self.load_candidate_locations()
        if len(candidate_gdf) > 0:
            self.save_locations_to_db(candidate_gdf, 'candidate')
        
        print("=" * 60)
        print("OSM data loading completed!")
        print("=" * 60)


if __name__ == "__main__":
    loader = OSMDataLoader()
    loader.load_all_data()

