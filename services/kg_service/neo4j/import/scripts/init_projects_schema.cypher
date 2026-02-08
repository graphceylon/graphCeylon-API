// ============================================================================
// Initialize Tourism Projects Schema
// This script creates constraints and indexes for TourismProject nodes
// ============================================================================

// ============================================================================
// STEP 1: Create Constraints
// ============================================================================

CREATE CONSTRAINT project_id IF NOT EXISTS FOR (p:TourismProject) REQUIRE p.id IS UNIQUE;

// ============================================================================
// STEP 2: Create Indexes for Performance
// ============================================================================

CREATE INDEX project_title IF NOT EXISTS FOR (p:TourismProject) ON (p.title);

CREATE INDEX project_type IF NOT EXISTS FOR (p:TourismProject) ON (p.project_type);

CREATE INDEX project_created IF NOT EXISTS FOR (p:TourismProject) ON (p.created_at);
