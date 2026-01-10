-- Walkability Optimization Database Schema
-- PostgreSQL database schema for storing pedestrian network, locations, and optimization results

-- Enable PostGIS extension for geographic data
CREATE EXTENSION IF NOT EXISTS postgis;

-- Nodes table: Central table for all graph nodes
-- Includes residential locations (N), candidate locations (M), and existing amenities (L)
CREATE TABLE nodes (
    node_id BIGSERIAL PRIMARY KEY,
    osm_id BIGINT UNIQUE,
    node_type VARCHAR(20) NOT NULL CHECK (node_type IN ('residential', 'candidate', 'amenity', 'network')),
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    geom GEOMETRY(POINT, 4326),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create spatial index for nodes
CREATE INDEX idx_nodes_geom ON nodes USING GIST(geom);
CREATE INDEX idx_nodes_type ON nodes(node_type);
CREATE INDEX idx_nodes_osm_id ON nodes(osm_id);

-- Edges table: Pedestrian network edges (walkable paths)
CREATE TABLE edges (
    edge_id BIGSERIAL PRIMARY KEY,
    from_node_id BIGINT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    to_node_id BIGINT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    length_meters DECIMAL(10, 2) NOT NULL,
    edge_type VARCHAR(50), -- sidewalk, crosswalk, pedestrian_path, etc.
    osm_way_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(from_node_id, to_node_id)
);

-- Create indexes for edges
CREATE INDEX idx_edges_from ON edges(from_node_id);
CREATE INDEX idx_edges_to ON edges(to_node_id);
CREATE INDEX idx_edges_way ON edges(osm_way_id);

-- Residential locations table: Subset of nodes (N)
-- NOTE: Multiple residential locations can map to the same network node (snap point)
-- Each residential building is unique, but they may share pathfinding nodes
CREATE TABLE residential_locations (
    residential_id BIGSERIAL PRIMARY KEY,
    node_id BIGINT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    snapped_node_id BIGINT REFERENCES nodes(node_id) ON DELETE SET NULL,  -- Network node for pathfinding
    osm_building_id BIGINT UNIQUE,  -- Original OSM building ID for uniqueness
    original_latitude DECIMAL(10, 8),  -- Original building centroid lat
    original_longitude DECIMAL(11, 8), -- Original building centroid lon
    address TEXT,
    building_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_residential_node ON residential_locations(node_id);
CREATE INDEX idx_residential_snapped_node ON residential_locations(snapped_node_id);

-- Candidate locations table: Potential allocation sites (M)
-- e.g., parking lots, empty lots, underused spaces
CREATE TABLE candidate_locations (
    candidate_id BIGSERIAL PRIMARY KEY,
    node_id BIGINT NOT NULL UNIQUE REFERENCES nodes(node_id) ON DELETE CASCADE,
    snapped_node_id BIGINT REFERENCES nodes(node_id) ON DELETE SET NULL,  -- Network node for pathfinding
    original_latitude DECIMAL(10, 8),  -- Original candidate lat
    original_longitude DECIMAL(11, 8), -- Original candidate lon
    capacity INTEGER NOT NULL DEFAULT 1, -- Maximum number of amenities that can be allocated
    location_type VARCHAR(50), -- parking_lot, empty_lot, etc.
    area_sqm DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_candidate_node ON candidate_locations(node_id);
CREATE INDEX idx_candidate_snapped_node ON candidate_locations(snapped_node_id);

-- Amenity types table: Types of amenities and their weights
CREATE TABLE amenity_types (
    amenity_type_id SERIAL PRIMARY KEY,
    type_name VARCHAR(50) NOT NULL UNIQUE, -- grocery, restaurant, school
    type_category VARCHAR(20) NOT NULL CHECK (type_category IN ('plain', 'depth')), -- Aplain or Adepth
    weight DECIMAL(5, 3) NOT NULL, -- wa: weight for this amenity type
    depth_count INTEGER DEFAULT 1, -- For Adepth: number of choices to consider (e.g., r=10 for restaurants)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default amenity types based on paper
INSERT INTO amenity_types (type_name, type_category, weight, depth_count) VALUES
    ('grocery', 'plain', 1.0, 1),      -- Highest weight, most frequent destination
    ('school', 'plain', 0.8, 1),
    ('restaurant', 'depth', 0.6, 10);  -- Depth of choice: top 10 nearest

-- Depth weights table: Weights for depth of choice (for Adepth amenities)
CREATE TABLE depth_weights (
    depth_weight_id SERIAL PRIMARY KEY,
    amenity_type_id INTEGER NOT NULL REFERENCES amenity_types(amenity_type_id) ON DELETE CASCADE,
    choice_rank INTEGER NOT NULL, -- p-th nearest choice (1, 2, ..., r)
    weight DECIMAL(5, 3) NOT NULL, -- wap: weight for p-th choice
    UNIQUE(amenity_type_id, choice_rank)
);

-- Insert default depth weights (example: restaurant)
-- These should be set based on WalkScore methodology
INSERT INTO depth_weights (amenity_type_id, choice_rank, weight)
SELECT amenity_type_id, generate_series(1, 10), 
       CASE 
           WHEN generate_series = 1 THEN 0.4
           WHEN generate_series = 2 THEN 0.2
           WHEN generate_series = 3 THEN 0.15
           WHEN generate_series = 4 THEN 0.1
           ELSE 0.15 / (generate_series - 3)
       END
FROM amenity_types WHERE type_name = 'restaurant';

-- Existing amenities table: Current amenities in the network (L)
-- NOTE: Multiple amenities can map to the same network node (snap point)
CREATE TABLE existing_amenities (
    amenity_id BIGSERIAL PRIMARY KEY,
    node_id BIGINT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    snapped_node_id BIGINT REFERENCES nodes(node_id) ON DELETE SET NULL,  -- Network node for pathfinding
    amenity_type_id INTEGER NOT NULL REFERENCES amenity_types(amenity_type_id),
    name TEXT,
    osm_id BIGINT,
    original_latitude DECIMAL(10, 8),  -- Original amenity lat
    original_longitude DECIMAL(11, 8), -- Original amenity lon
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(osm_id, amenity_type_id)  -- Changed: unique by OSM ID, not node_id
);

CREATE INDEX idx_existing_amenity_node ON existing_amenities(node_id);
CREATE INDEX idx_existing_amenity_snapped_node ON existing_amenities(snapped_node_id);
CREATE INDEX idx_existing_amenity_type ON existing_amenities(amenity_type_id);

-- Shortest paths table: Pre-computed shortest path distances
-- Stores distances between residential locations and candidate/existing locations
CREATE TABLE shortest_paths (
    path_id BIGSERIAL PRIMARY KEY,
    from_node_id BIGINT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    to_node_id BIGINT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    distance_meters DECIMAL(10, 2) NOT NULL,
    path_length INTEGER, -- Number of edges in path
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(from_node_id, to_node_id)
);

CREATE INDEX idx_shortest_paths_from ON shortest_paths(from_node_id);
CREATE INDEX idx_shortest_paths_to ON shortest_paths(to_node_id);
CREATE INDEX idx_shortest_paths_distance ON shortest_paths(distance_meters);

-- Walkability scores table: Computed WalkScores for residential locations
CREATE TABLE walkability_scores (
    score_id BIGSERIAL PRIMARY KEY,
    residential_id BIGINT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    scenario VARCHAR(50) NOT NULL, -- 'baseline', 'optimized_milp', 'optimized_greedy', etc.
    weighted_distance DECIMAL(10, 2) NOT NULL, -- li: weighted walking distance
    walkscore DECIMAL(5, 2) NOT NULL CHECK (walkscore >= 0 AND walkscore <= 100), -- fi: WalkScore
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(residential_id, scenario)
);

CREATE INDEX idx_walkscore_residential ON walkability_scores(residential_id);
CREATE INDEX idx_walkscore_scenario ON walkability_scores(scenario);

-- Optimization results table: Stores allocation decisions
CREATE TABLE optimization_results (
    result_id BIGSERIAL PRIMARY KEY,
    scenario VARCHAR(50) NOT NULL, -- 'milp_k3', 'greedy_k3', etc.
    amenity_type_id INTEGER NOT NULL REFERENCES amenity_types(amenity_type_id),
    candidate_id BIGINT NOT NULL REFERENCES candidate_locations(candidate_id),
    allocation_count INTEGER NOT NULL DEFAULT 1, -- yja: number of amenities allocated
    objective_value DECIMAL(10, 4), -- Average WalkScore achieved
    solver VARCHAR(20), -- 'milp', 'greedy', 'cp'
    solve_time_seconds DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_optimization_scenario ON optimization_results(scenario);
CREATE INDEX idx_optimization_type ON optimization_results(amenity_type_id);

-- Distance assignments table: Which residential locations are assigned to which amenities
-- For Aplain: single assignment per residential per amenity type
CREATE TABLE distance_assignments (
    assignment_id BIGSERIAL PRIMARY KEY,
    residential_id BIGINT NOT NULL REFERENCES nodes(node_id) ON DELETE CASCADE,
    amenity_type_id INTEGER NOT NULL REFERENCES amenity_types(amenity_type_id),
    amenity_node_id BIGINT NOT NULL REFERENCES nodes(node_id), -- Can be existing or allocated
    distance_meters DECIMAL(10, 2) NOT NULL,
    scenario VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(residential_id, amenity_type_id, scenario)
);

CREATE INDEX idx_assignments_residential ON distance_assignments(residential_id);
CREATE INDEX idx_assignments_scenario ON distance_assignments(scenario);

-- Depth assignments table: For Adepth amenities (multiple choices per residential)
CREATE TABLE depth_assignments (
    depth_assignment_id BIGSERIAL PRIMARY KEY,
    residential_id BIGINT NOT NULL REFERENCES residential_locations(residential_id) ON DELETE CASCADE,
    amenity_type_id INTEGER NOT NULL REFERENCES amenity_types(amenity_type_id),
    choice_rank INTEGER NOT NULL, -- p-th nearest choice
    amenity_node_id BIGINT NOT NULL REFERENCES nodes(node_id),
    distance_meters DECIMAL(10, 2) NOT NULL,
    scenario VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(residential_id, amenity_type_id, choice_rank, scenario)
);

CREATE INDEX idx_depth_assignments_residential ON depth_assignments(residential_id);
CREATE INDEX idx_depth_assignments_scenario ON depth_assignments(scenario);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for nodes table
CREATE TRIGGER update_nodes_updated_at BEFORE UPDATE ON nodes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Views for easier querying
CREATE VIEW residential_nodes AS
SELECT n.*, r.residential_id, r.address, r.building_type
FROM nodes n
JOIN residential_locations r ON n.node_id = r.node_id;

CREATE VIEW candidate_nodes AS
SELECT n.*, c.candidate_id, c.capacity, c.location_type, c.area_sqm
FROM nodes n
JOIN candidate_locations c ON n.node_id = c.node_id;

CREATE VIEW existing_amenity_nodes AS
SELECT n.*, e.amenity_id, e.amenity_type_id, at.type_name, at.type_category, e.name
FROM nodes n
JOIN existing_amenities e ON n.node_id = e.node_id
JOIN amenity_types at ON e.amenity_type_id = at.amenity_type_id;

