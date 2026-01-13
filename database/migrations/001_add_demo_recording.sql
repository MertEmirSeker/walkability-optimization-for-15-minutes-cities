-- Migration: Add Demo Recording Tables
-- Purpose: Enable recording and replay of optimization runs for demo purposes
-- Date: 2026-01-13

-- Table to store iteration-by-iteration recording of optimization runs
CREATE TABLE IF NOT EXISTS optimization_iterations (
    iteration_id BIGSERIAL PRIMARY KEY,
    scenario VARCHAR(50) NOT NULL,           -- 'greedy_k3', etc.
    iteration_number INTEGER NOT NULL,       -- 1, 2, 3, ...
    amenity_type_id INTEGER NOT NULL REFERENCES amenity_types(amenity_type_id),
    candidate_id BIGINT NOT NULL REFERENCES candidate_locations(candidate_id),
    improvement DECIMAL(10, 6) NOT NULL,     -- Objective increase from this allocation
    current_objective DECIMAL(10, 4) NOT NULL, -- Current avg WalkScore after allocation
    progress_pct DECIMAL(5, 2) NOT NULL,     -- 0.0 - 100.0
    elapsed_seconds DECIMAL(10, 2) NOT NULL, -- Time since optimization start
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(scenario, iteration_number)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_iterations_scenario ON optimization_iterations(scenario);
CREATE INDEX IF NOT EXISTS idx_iterations_number ON optimization_iterations(iteration_number);

-- Metadata table for recordings
CREATE TABLE IF NOT EXISTS optimization_recordings (
    recording_id SERIAL PRIMARY KEY,
    scenario VARCHAR(50) NOT NULL UNIQUE,
    algorithm VARCHAR(20) NOT NULL,          -- 'greedy', 'milp'
    k_value INTEGER NOT NULL,                -- Number of allocations per type
    total_iterations INTEGER NOT NULL,
    final_objective DECIMAL(10, 4) NOT NULL,
    total_time_seconds DECIMAL(10, 2) NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for quick scenario lookup
CREATE INDEX IF NOT EXISTS idx_recordings_scenario ON optimization_recordings(scenario);

-- Comment the tables
COMMENT ON TABLE optimization_iterations IS 'Records each iteration of optimization runs for demo replay';
COMMENT ON TABLE optimization_recordings IS 'Metadata for recorded optimization runs';
