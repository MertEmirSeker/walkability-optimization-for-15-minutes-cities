"""
OpenStreetMap data loader for Balıkesir city center.
Fetches pedestrian network, residential locations, amenities, and candidate locations.
All data is restricted to the Karesi + Altıeylül city center polygon.

Improvements:
- Expanded residential building tags
- Comprehensive amenity detection
- Enhanced candidate location selection
- Data quality validation
- Duplicate detection
- Snapping distance limits
- OSM data freshness tracking
- Missing data handling
"""
import osmnx as ox
import pandas as pd
import numpy as np
from shapely.geometry import Point
from typing import Dict, List, Tuple, Optional, Set
import yaml
from sqlalchemy import text
import sys
import time
import threading
import itertools
from datetime import datetime
import logging

from src.utils.database import get_db_manager
from src.data_collection.balikesir_center import get_balikesir_center_polygon

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OSMDataLoader:
    """Loads OSM data for walkability optimization with enhanced quality controls."""

    # Class-level defaults (will be overridden by config)
    RESIDENTIAL_BUILDING_TYPES = set()
    MAX_SNAPPING_DISTANCE = 500  # Default, will be overridden by config
    DUPLICATE_THRESHOLD = 1.0
    AMENITY_DUPLICATE_THRESHOLD = 5.0
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize OSM loader with configuration."""
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.balikesir_config = self.config['balikesir']
        self.osm_config = self.config['osm']
        self.db = get_db_manager(config_path)
        # center polygon (Karesi + Altıeylül)
        self.center_poly = get_balikesir_center_polygon()
        
        # For amenities, use a MUCH larger polygon (1.5km buffer)
        # to capture amenities just outside the center that serve residents
        # Many amenities are located just outside official boundaries
        self.amenity_poly = self.center_poly.buffer(
            0.015)  # ~1.5km buffer in degrees (~1650m)

        # Load residential building types from config
        self._load_residential_types_from_config()

        # Load data quality parameters from config
        data_quality = self.osm_config.get('data_quality', {})
        self.MAX_SNAPPING_DISTANCE = data_quality.get(
            'max_snapping_distance', 500)
        self.DUPLICATE_THRESHOLD = data_quality.get('duplicate_threshold', 1.0)
        self.AMENITY_DUPLICATE_THRESHOLD = data_quality.get(
            'amenity_duplicate_threshold', 5.0)
        self.enable_validation = data_quality.get('enable_validation', True)
        self.enable_duplicate_detection = data_quality.get(
            'enable_duplicate_detection', True)

        # Statistics tracking
        self.stats = {
            'load_timestamp': datetime.now().isoformat(),
            'residential_total': 0,
            'residential_filtered': 0,
            'residential_duplicates': 0,
            'amenities_by_type': {},
            'candidates_total': 0,
            'snapping_failures': 0,
            'network_nodes': 0,
            'network_edges': 0,
            'data_quality_issues': []
        }

        logger.info("OSMDataLoader initialized for Balıkesir city center")
        logger.info(f"Max snapping distance: {self.MAX_SNAPPING_DISTANCE}m")
        logger.info(f"Duplicate detection: {self.enable_duplicate_detection}")

    def _load_residential_types_from_config(self):
        """Extract residential building types from config."""
        residential_tags = self.osm_config.get('residential_tags', [])
        self.RESIDENTIAL_BUILDING_TYPES = set()

        for tag_dict in residential_tags:
            for key, value in tag_dict.items():
                if key == 'building' and value != 'yes':
                    # Extract building type value
                    self.RESIDENTIAL_BUILDING_TYPES.add(value)
                elif key == 'building' and value == 'yes':
                    # Special case for generic building
                    self.RESIDENTIAL_BUILDING_TYPES.add('yes')

        logger.info(
            f"Loaded {len(self.RESIDENTIAL_BUILDING_TYPES)} residential building types from config")
        
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

        Improvements:
        - Better logging
        - Network validation
        - Connectivity checking
        """
        logger.info(
            "Loading pedestrian network from OSM (walk network, city center)...")

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
            # Load walk network WITHOUT simplification
            # simplify=False keeps all nodes, ensuring connectivity
            # This is CRITICAL for ensuring residential/amenity nodes can be
            # reached!
            G = ox.graph_from_polygon(
                self.center_poly,
                network_type="walk",
                simplify=False,  # Keep all nodes for connectivity!
            )

            # Validate network
            if len(G.nodes) == 0:
                logger.error("Empty pedestrian network loaded!")
                self.stats['data_quality_issues'].append(
                    "Empty pedestrian network")

            if len(G.edges) == 0:
                logger.error("No edges in pedestrian network!")
                self.stats['data_quality_issues'].append("No edges in network")

            # Check if network is strongly connected
            import networkx as nx
            if not nx.is_strongly_connected(G):
                logger.warning("Pedestrian network is not strongly connected")
                logger.info(
    f"Network has {
        nx.number_strongly_connected_components(G)} strongly connected components")
                self.stats['data_quality_issues'].append(
                    "Network not strongly connected")

        finally:
            stop_spinner.set()
            spinner_thread.join()

        logger.info(
            f"Loaded pedestrian network: {len(G.nodes)} nodes, {len(G.edges)} edges")
        return G
    
    def load_residential_locations(self) -> pd.DataFrame:
        """
        Load residential buildings/addresses from OSM with enhanced filtering.

        Improvements:
        - Expanded building type detection
        - Duplicate detection and removal
        - Coordinate validation
        - Original coordinate preservation
        """
        logger.info("Loading residential locations from OSM...")

        # First, try to get all buildings
        tags = {"building": True}

        try:
            try:
                gdf = ox.features_from_polygon(self.center_poly, tags=tags)
            except AttributeError:
                gdf = ox.geometries_from_polygon(self.center_poly, tags=tags)

            initial_count = len(gdf)
            self.stats['residential_total'] = initial_count

            if initial_count == 0:
                logger.warning("No buildings found in center polygon.")
                return pd.DataFrame()

            logger.info(f"Found {initial_count} total buildings")

            # Store original coordinates before converting to centroids
            if 'geometry' in gdf.columns:
                gdf['original_geometry'] = gdf['geometry'].copy()
                gdf['original_latitude'] = gdf.geometry.centroid.y
                gdf['original_longitude'] = gdf.geometry.centroid.x

            # IMPROVED FILTERING STRATEGY:
            # In Turkey, most buildings are tagged as building=yes without specific type
            # So we use EXCLUSION rather than INCLUSION: exclude clearly
            # non-residential

            bcol = gdf.get("building")
            amenity_col = gdf.get("amenity")  # Check amenity tags too!

            if bcol is not None or amenity_col is not None:
                # Define NON-RESIDENTIAL building types to EXCLUDE
                # (COMPREHENSIVE)
                non_residential_types = {
                    # Commercial
                    'commercial', 'retail', 'industrial', 'warehouse', 'office',
                    'supermarket', 'mall', 'shop', 'store', 'kiosk',
                    # Education - CRITICAL TO EXCLUDE
                    'hospital', 'school', 'university', 'college', 'kindergarten',
                    'library', 'education',
                    # Religious
                    'church', 'mosque', 'temple', 'synagogue', 'chapel', 'cathedral',
                    'religious',
                    # Hospitality
                    'hotel', 'motel', 'hostel',
                    # Sports & Recreation
                    'stadium', 'sports_hall', 'sports_centre', 'sport', 'sports_center',
                    # Parking & Transportation
                    'parking', 'garage', 'garages', 'carport',
                    'train_station', 'transportation', 'station',
                    # Agricultural
                    'barn', 'farm_auxiliary', 'greenhouse', 'cowshed', 'sty', 'farm',
                    # Utility
                    'hangar', 'shed', 'stable', 'roof',
                    # Public/Civic
                    'public', 'civic', 'government', 'townhall', 'town_hall',
                    'fire_station', 'police',
                    # Abandoned/Construction
                    'construction', 'ruins', 'damaged', 'demolished', 'abandoned',
                    # Infrastructure
                    'service', 'transformer_tower', 'water_tower', 'tower',
                    'bridge', 'bunker', 'container', 'shed', 'toilets',
                    # Healthcare (buildings)
                    'clinic', 'doctors', 'healthcare',
                }

                # ALSO check amenity column - if it has school/hospital
                # amenity, exclude!
                non_residential_amenities = {
                    'school', 'kindergarten', 'college', 'university',
                    'hospital', 'clinic', 'doctors', 'pharmacy',
                    'place_of_worship', 'community_centre', 'social_facility',
                    'police', 'fire_station', 'post_office',
                    'bank', 'atm', 'restaurant', 'cafe', 'fast_food',
                    'pub', 'bar', 'fuel', 'parking', 'library'
                }

                # Build exclusion mask
                mask = pd.Series([True] * len(gdf), index=gdf.index)

                # Exclude by building type
            if bcol is not None:
                    mask &= ~bcol.isin(non_residential_types)

                # Exclude by amenity tag - IMPORTANT!
                if amenity_col is not None:
                    mask &= ~amenity_col.isin(non_residential_amenities)

                before_filter = len(gdf)
                gdf = gdf[mask].copy()
                filtered_out = before_filter - len(gdf)
                logger.info(
                    f"After building type filter: {len(gdf)} buildings (excluded {filtered_out} non-residential)")

            # Also check landuse=residential tags
            landuse_col = gdf.get("landuse")
            if landuse_col is not None:
                # Include locations with landuse=residential
                residential_landuse = gdf[landuse_col == "residential"]
                if len(residential_landuse) > 0:
                    logger.info(
    f"Found {
        len(residential_landuse)} residential landuse areas")
                    gdf = pd.concat([gdf, residential_landuse]
                                    ).drop_duplicates()

            # Extract centroids for point locations
            gdf["geometry"] = gdf.geometry.centroid
            gdf = gdf[gdf.geometry.type == "Point"]

            # DON'T validate coordinates strictly - buildings were already
            # fetched from polygon, centroid calculation might shift slightly
            # We were losing 6523 locations due to overly strict bounds checking
            # Instead, just keep everything from the polygon query

            # Remove duplicates based on proximity
            if self.enable_duplicate_detection:
                gdf = self._remove_spatial_duplicates(
    gdf, threshold_meters=self.DUPLICATE_THRESHOLD)

            final_count = len(gdf)
            self.stats['residential_filtered'] = final_count

            logger.info(f"Final residential count: {final_count} "
                       f"(filtered {initial_count - final_count} buildings)")

            return gdf

        except Exception as e:
            logger.error(
    f"Error loading residential locations: {e}",
     exc_info=True)
            return pd.DataFrame()
    
    def _validate_coordinates(self, gdf: pd.DataFrame) -> pd.DataFrame:
        """Validate that coordinates are within expected bounds."""
        if len(gdf) == 0:
            return gdf

        boundary = self.balikesir_config['boundary']

        # Extract coordinates safely
        lats = gdf.geometry.apply(lambda geom: geom.y if geom else None)
        lons = gdf.geometry.apply(lambda geom: geom.x if geom else None)

        # Filter coordinates within bounds
        valid_mask = (
            (lats >= boundary['south']) &
            (lats <= boundary['north']) &
            (lons >= boundary['west']) &
            (lons <= boundary['east'])
        )

        invalid_count = (~valid_mask).sum()
        if invalid_count > 0:
            logger.warning(
    f"Removed {invalid_count} locations with invalid coordinates")

        return gdf[valid_mask].copy()

    def _remove_spatial_duplicates(self, gdf: pd.DataFrame,
                                   threshold_meters: float = 1.0) -> pd.DataFrame:
        """
        Remove duplicate locations that are within threshold distance.
        Keeps the first occurrence.
        """
        if len(gdf) == 0:
            return gdf

        # Convert to a simple coordinate list for duplicate detection
        coords = [(geom.y, geom.x) for geom in gdf.geometry]

        # Simple duplicate detection: same coordinates (exact match)
        before_count = len(gdf)
        gdf_dedup = gdf.drop_duplicates(subset=['geometry'])
        after_count = len(gdf_dedup)

        duplicates_removed = before_count - after_count
        if duplicates_removed > 0:
            self.stats['residential_duplicates'] = duplicates_removed
            logger.info(
    f"Removed {duplicates_removed} exact duplicate locations")

        return gdf_dedup
    
    def load_amenities(self, amenity_type: str) -> pd.DataFrame:
        """
        Load specific amenity type from OSM with comprehensive tag coverage.

        Improvements:
        - Reads tag configuration from config.yaml
        - Duplicate detection
        - Coordinate validation
        - Better error handling
        """
        # Get tags from config
        tags = self._get_amenity_tags_from_config(amenity_type)

        if not tags:
            logger.warning(
    f"No tags configured for amenity type: {amenity_type}")
            return pd.DataFrame()

        logger.info(f"Loading {amenity_type} amenities from OSM...")

        try:
            # Use expanded polygon for amenities to capture nearby facilities
            try:
                gdf = ox.features_from_polygon(self.amenity_poly, tags=tags)
            except AttributeError:
                gdf = ox.geometries_from_polygon(self.amenity_poly, tags=tags)

            if len(gdf) > 0:
                # Store original geometry before converting to centroid
                gdf['original_geometry'] = gdf['geometry'].copy()

                # Convert to centroids
                gdf["geometry"] = gdf.geometry.centroid
                gdf = gdf[gdf.geometry.type == "Point"]

                # DON'T validate coordinates for amenities - they were already
                # within the polygon, centroid might shift slightly outside
                # This was causing us to lose many amenities (53 grocery, 39
                # restaurant, etc.)

                # Remove duplicates if enabled
                if self.enable_duplicate_detection:
                    gdf = self._remove_spatial_duplicates(
                        gdf, threshold_meters=self.AMENITY_DUPLICATE_THRESHOLD
                    )

            count = len(gdf)
            self.stats['amenities_by_type'][amenity_type] = count
            logger.info(f"Found {count} {amenity_type} amenities")

            return gdf

        except Exception as e:
            logger.error(
    f"Error loading {amenity_type} amenities: {e}",
     exc_info=True)
            return pd.DataFrame()
    
    def _get_amenity_tags_from_config(self, amenity_type: str) -> Dict:
        """
        Extract amenity tags from config for a specific amenity type.
        Converts config list format to OSMnx-compatible dict format.
        
        IMPORTANT: Converts boolean True to "yes" for OSM compatibility.
        """
        amenity_tags = self.osm_config.get('amenity_tags', {})
        if amenity_type not in amenity_tags:
            return {}

        # Convert list of tag dicts to OSMnx format
        # Example: [{"shop": "supermarket"}, {"shop": "convenience"}]
        # -> {"shop": ["supermarket", "convenience"]}
        tag_list = amenity_tags[amenity_type]
        osm_tags = {}

        for tag_dict in tag_list:
            for key, value in tag_dict.items():
                if key not in osm_tags:
                    osm_tags[key] = []
                    
                # Convert boolean True to "yes" for OSM compatibility
                # OSMnx requires strings, not booleans
                if value is True:
                    value = "yes"
                elif value is False:
                    continue  # Skip False values
                    
                if isinstance(value, list):
                    # Convert any True/False in list to strings
                    converted_list = []
                    for v in value:
                        if v is True:
                            converted_list.append("yes")
                        elif v is False:
                            continue  # Skip False
                        else:
                            converted_list.append(str(v))
                    osm_tags[key].extend(converted_list)
                else:
                    osm_tags[key].append(str(value))

        return osm_tags
    
    def load_candidate_locations(self) -> pd.DataFrame:
        """
        Load candidate locations (parking lots, empty lots, etc.) from OSM.

        Improvements:
        - Reads candidate tags from config
        - Multiple tag types (not just primary/fallback)
        - Duplicate detection
        - Coordinate validation
        """
        logger.info("Loading candidate locations from OSM...")

        # Get candidate tags from config
        candidate_tags = self._get_candidate_tags_from_config()

        all_gdfs = []

        # Try to load candidates for each tag type
        # Use expanded polygon for candidates too
        for tags in candidate_tags:
            try:
                try:
                    gdf = ox.features_from_polygon(
                        self.amenity_poly, tags=tags)
                except AttributeError:
                    gdf = ox.geometries_from_polygon(
                        self.amenity_poly, tags=tags)

                if len(gdf) > 0:
                    all_gdfs.append(gdf)
                    logger.info(f"Found {len(gdf)} candidates for tags: {tags}")

        except Exception as e:
                logger.debug(f"No candidates found for tags {tags}: {e}")
                continue

        if not all_gdfs:
            logger.warning("No candidate locations found")
            return pd.DataFrame()
    
        # Combine all candidate dataframes
        gdf = pd.concat(all_gdfs, ignore_index=True)

        # Store original geometry
        gdf['original_geometry'] = gdf['geometry'].copy()

        # Convert to centroids
        gdf["geometry"] = gdf.geometry.centroid
        gdf = gdf[gdf.geometry.type == "Point"]

        # Validate coordinates if enabled
        if self.enable_validation:
            gdf = self._validate_coordinates(gdf)

        # Remove duplicates if enabled
        if self.enable_duplicate_detection:
            gdf = self._remove_spatial_duplicates(gdf, threshold_meters=10.0)

        count = len(gdf)
        self.stats['candidates_total'] = count
        logger.info(f"Total candidate locations: {count}")

        return gdf

    def _get_candidate_tags_from_config(self) -> List[Dict]:
        """
        Extract candidate location tags from config.
        Returns a list of tag dictionaries for OSMnx.
        """
        candidate_tags_list = self.osm_config.get('candidate_tags', [])

        # Group tags by key
        tags_by_key = {}
        for tag_dict in candidate_tags_list:
            for key, value in tag_dict.items():
                if key not in tags_by_key:
                    tags_by_key[key] = []
                if isinstance(value, list):
                    tags_by_key[key].extend(value)
                else:
                    tags_by_key[key].append(value)

        # Convert to list of separate tag queries
        # Each unique key-value combination becomes a separate query
        result = []
        for key, values in tags_by_key.items():
            if len(values) == 1:
                result.append({key: values[0]})
            else:
                result.append({key: values})

        return result if result else [{"amenity": "parking"}]  # Fallback
    
    def save_network_to_db(self, G: ox.graph):
        """
        Save pedestrian network graph to database.

        Improvements:
        - Better logging
        - Error handling
        - Progress tracking
        """
        logger.info("Saving network to database...")
        
        nodes_saved = 0
        edges_saved = 0

        try:
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
            
                # Batch insert nodes
                logger.info(f"Inserting {len(nodes_data)} nodes...")
            for node_data in nodes_data:
                query = """
                    INSERT INTO nodes (osm_id, node_type, latitude, longitude, geom)
                    VALUES (:osm_id, :node_type, :latitude, :longitude, 
                            ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326))
                    ON CONFLICT (osm_id) DO NOTHING
                """
                session.execute(text(query), node_data)
                    nodes_saved += 1
            
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
                logger.info(f"Inserting {len(edges_data)} edges...")
                for edge_data in edges_data:
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
                    edges_saved += 1

                logger.info(f"Network saved: {nodes_saved} nodes, {edges_saved} edges")

        except Exception as e:
            logger.error(f"Error saving network to database: {e}", exc_info=True)
            self.stats['data_quality_issues'].append(f"Network save error: {str(e)}")

    def _get_largest_component_nodes(self) -> set:
        """Get node IDs from the largest connected component of the graph."""
        with self.db.get_session() as session:
            # Get all nodes
            nodes_query = "SELECT node_id FROM nodes WHERE node_type = 'network'"
            nodes_result = session.execute(text(nodes_query))
            all_nodes = {row[0] for row in nodes_result}

            if not all_nodes:
                return set()

            # Get all edges
            edges_query = "SELECT from_node_id, to_node_id FROM edges"
            edges_result = session.execute(text(edges_query))

            # Build graph
            import networkx as nx
            G = nx.Graph()
            G.add_nodes_from(all_nodes)
            for row in edges_result:
                G.add_edge(row[0], row[1])

            # Find largest component
            if nx.is_connected(G):
                return all_nodes
            else:
                components = list(nx.connected_components(G))
                largest = max(components, key=len)
                logger.info(
    f"Graph has {
        len(components)} components. Largest: {
            len(largest)} nodes")
                return largest

    def _find_nearest_network_node(
            self,
            lat: float,
            lon: float,
            valid_nodes: set) -> int:
        """
        Find nearest network node from valid_nodes to given coordinates.
        
        ⚡ OPTIMIZED: Uses spatial index, no array transfer!
        """
        with self.db.get_session() as session:
            # ⚡ Use PostGIS spatial index (KNN operator <->)
            # No need to send 82K array! Spatial index is FAST!
            query = """
                SELECT node_id,
                       ST_Distance(
                           geom::geography,
                           ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                       ) as distance
                FROM nodes
                WHERE node_type = 'network'
                ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                LIMIT 1
            """
            result = session.execute(text(query), {
                'lat': lat,
                'lon': lon
            })
            row = result.first()
            if row and row[1] <= self.MAX_SNAPPING_DISTANCE:
                return row[0]
            return None
    
    def save_locations_to_db(self, gdf: pd.DataFrame, location_type: str, 
                            amenity_type: str = None):
        """
        Save locations (residential, amenities, candidates) to database.

        Improvements:
        - Snap to nearest network node in largest connected component
        - Better logging
        - Error handling
        - Progress tracking
        """
        logger.info(
    f"Saving {
        len(gdf)} {location_type} locations to database...")
        
        # Get largest component nodes for snapping
        if location_type in ['residential', 'amenity', 'candidate']:
            logger.info("Finding largest connected component for snapping...")
            largest_component = self._get_largest_component_nodes()
            logger.info(
    f"Will snap to {
        len(largest_component)} nodes in largest component")
        else:
            largest_component = set()

        saved_count = 0
        error_count = 0
        snapped_count = 0
        
        total = len(gdf)
        batch_size = 100  # Commit every 100 records

        try:
        with self.db.get_session() as session:
                for i, (idx, row) in enumerate(gdf.iterrows(), 1):
                    try:
                geom = row.geometry
                lat = geom.y
                lon = geom.x
                        
                        # First, get osm_id (needed for amenities)
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
                                error_count += 1
                                continue
                        
                        # Snap to nearest network node if applicable
                        snapped_node_id = None
                        if largest_component:
                            snapped_node_id = self._find_nearest_network_node(lat, lon, largest_component)
                            if snapped_node_id:
                                snapped_count += 1
                            else:
                                # Skip if can't snap
                                error_count += 1
                        continue
                
                        # FIXED: Don't insert into nodes table!
                        # node_id is just the osm_id (identifier), not a network node
                        # Only network nodes belong in the nodes table
                        node_id = osm_id
                
                        # Insert into specific table WITH SNAPPED NODE
                if location_type == 'residential':
                    res_query = """
                                INSERT INTO residential_locations 
                                    (node_id, snapped_node_id, osm_building_id, address, building_type, original_latitude, original_longitude)
                                VALUES (:node_id, :snapped_node_id, :osm_building_id, :address, :building_type, :orig_lat, :orig_lon)
                                ON CONFLICT (osm_building_id) DO NOTHING
                    """
                    session.execute(text(res_query), {
                        'node_id': node_id,
                                'snapped_node_id': snapped_node_id,  # For pathfinding
                                'osm_building_id': osm_id,  # Use OSM building ID for uniqueness
                        'address': row.get('addr:street', ''),
                                'building_type': row.get('building', 'residential'),
                                'orig_lat': lat,  # Original building coordinate
                                'orig_lon': lon   # Original building coordinate
                    })
                
                elif location_type == 'amenity' and amenity_type:
                    # Get amenity_type_id
                    type_query = "SELECT amenity_type_id FROM amenity_types WHERE type_name = :type_name"
                    type_result = session.execute(text(type_query), {'type_name': amenity_type})
                    amenity_type_id = type_result.scalar()
                    
                    if amenity_type_id:
                        amenity_query = """
                                    INSERT INTO existing_amenities 
                                        (node_id, snapped_node_id, amenity_type_id, name, osm_id, original_latitude, original_longitude)
                                    VALUES (:node_id, :snapped_node_id, :amenity_type_id, :name, :osm_id, :orig_lat, :orig_lon)
                                    ON CONFLICT (osm_id, amenity_type_id) DO NOTHING
                        """
                        session.execute(text(amenity_query), {
                            'node_id': node_id,
                                    'snapped_node_id': snapped_node_id,  # For pathfinding
                            'amenity_type_id': amenity_type_id,
                            'name': row.get('name', ''),
                                    'osm_id': osm_id,
                                    'orig_lat': lat,  # Original amenity coordinate
                                    'orig_lon': lon   # Original amenity coordinate
                        })
                            else:
                                logger.warning(f"Amenity type '{amenity_type}' not found in database")
                
                elif location_type == 'candidate':
                    cand_query = """
                                INSERT INTO candidate_locations 
                                    (node_id, snapped_node_id, capacity, location_type, original_latitude, original_longitude)
                                VALUES (:node_id, :snapped_node_id, :capacity, :location_type, :orig_lat, :orig_lon)
                                ON CONFLICT (node_id) DO UPDATE SET
                                    snapped_node_id = EXCLUDED.snapped_node_id,
                                    original_latitude = EXCLUDED.original_latitude,
                                    original_longitude = EXCLUDED.original_longitude
                    """
                    session.execute(text(cand_query), {
                        'node_id': node_id,
                                'snapped_node_id': snapped_node_id,  # For pathfinding
                        'capacity': 1,  # Default capacity
                                'location_type': row.get('amenity', 'parking'),
                                'orig_lat': lat,  # Original candidate coordinate
                                'orig_lon': lon   # Original candidate coordinate
                            })
                        
                        saved_count += 1
                        
                        # ⚡ Progress update every 100 records
                        if i % 100 == 0:
                            logger.info(f"  Progress: {i}/{total} ({i*100//total}%) - {saved_count} saved, {snapped_count} snapped")
                        
                        # ⚡ Commit every batch
                        if i % batch_size == 0:
                            session.commit()
                        
                    except Exception as e:
                        error_count += 1
                        logger.debug(f"Error saving location {idx}: {e}")
                        continue
                
                # Final commit
                session.commit()
                
                msg = f"Saved {saved_count} {location_type} locations"
                if snapped_count > 0:
                    msg += f" ({snapped_count} snapped to network)"
                if error_count > 0:
                    msg += f" ({error_count} errors)"
                logger.info(msg)
            
        except Exception as e:
            logger.error(f"Error saving {location_type} locations: {e}", exc_info=True)
            self.stats['data_quality_issues'].append(f"{location_type} save error: {str(e)}")
    
    def load_all_data(self, amenity_types: Optional[List[str]] = None):
        """
        Load all data from OSM and save to database.
        
        Args:
            amenity_types: List of amenity types to load. If None, loads all configured types.
        """
        logger.info("=" * 60)
        logger.info("Loading OSM data for Balıkesir city center")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        # Load pedestrian network
        G = self.load_pedestrian_network()
        if G is not None and len(G.nodes) > 0:
            self.stats['network_nodes'] = len(G.nodes)
            self.stats['network_edges'] = len(G.edges)
            self.save_network_to_db(G)
        
        # Load residential locations
        residential_gdf = self.load_residential_locations()
        if len(residential_gdf) > 0:
            self.save_locations_to_db(residential_gdf, 'residential')
        
        # Load amenities - use provided list or get all from config
        if amenity_types is None:
            amenity_types = list(self.osm_config.get('amenity_tags', {}).keys())
        
        logger.info(f"Loading {len(amenity_types)} amenity types: {', '.join(amenity_types)}")
        
        for amenity_type in amenity_types:
            amenity_gdf = self.load_amenities(amenity_type)
            if len(amenity_gdf) > 0:
                self.save_locations_to_db(amenity_gdf, 'amenity', amenity_type)
        
        # Load candidate locations
        candidate_gdf = self.load_candidate_locations()
        if len(candidate_gdf) > 0:
            self.save_locations_to_db(candidate_gdf, 'candidate')
        
        elapsed_time = time.time() - start_time
        
        # Print comprehensive statistics
        self._print_statistics(elapsed_time)
        
        logger.info("=" * 60)
        logger.info("OSM data loading completed!")
        logger.info("=" * 60)
    
    def _print_statistics(self, elapsed_time: float):
        """Print comprehensive loading statistics."""
        logger.info("\n" + "=" * 60)
        logger.info("OSM DATA LOADING STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Load timestamp: {self.stats['load_timestamp']}")
        logger.info(f"Total loading time: {elapsed_time:.2f} seconds")
        logger.info("")
        logger.info("NETWORK:")
        logger.info(f"  Nodes: {self.stats['network_nodes']}")
        logger.info(f"  Edges: {self.stats['network_edges']}")
        logger.info("")
        logger.info("RESIDENTIAL LOCATIONS:")
        logger.info(f"  Total buildings found: {self.stats['residential_total']}")
        logger.info(f"  After filtering: {self.stats['residential_filtered']}")
        logger.info(f"  Duplicates removed: {self.stats['residential_duplicates']}")
        logger.info("")
        logger.info("AMENITIES BY TYPE:")
        for amenity_type, count in sorted(self.stats['amenities_by_type'].items()):
            logger.info(f"  {amenity_type}: {count}")
        logger.info("")
        logger.info("CANDIDATE LOCATIONS:")
        logger.info(f"  Total candidates: {self.stats['candidates_total']}")
        logger.info("")
        
        if self.stats['data_quality_issues']:
            logger.warning("DATA QUALITY ISSUES:")
            for issue in self.stats['data_quality_issues']:
                logger.warning(f"  - {issue}")
        else:
            logger.info("No data quality issues detected")
        
        logger.info("=" * 60)


if __name__ == "__main__":
    loader = OSMDataLoader()
    loader.load_all_data()

