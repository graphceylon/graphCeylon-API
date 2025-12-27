// ============================================================================
// Initialize Tourism News Schema
// This script creates constraints and indexes for NewsArticle nodes
// ============================================================================

// ============================================================================
// STEP 1: Create Constraints
// ============================================================================

CREATE CONSTRAINT news_id IF NOT EXISTS FOR (n:NewsArticle) REQUIRE n.id IS UNIQUE;

// ============================================================================
// STEP 2: Create Indexes for Performance
// ============================================================================

CREATE INDEX news_title IF NOT EXISTS FOR (n:NewsArticle) ON (n.title);

CREATE INDEX news_date IF NOT EXISTS FOR (n:NewsArticle) ON (n.date);

CREATE INDEX news_year IF NOT EXISTS FOR (n:NewsArticle) ON (n.year);

CREATE INDEX news_month IF NOT EXISTS FOR (n:NewsArticle) ON (n.month);

CREATE INDEX news_category IF NOT EXISTS FOR (n:NewsArticle) ON (n.category);

CREATE INDEX news_created IF NOT EXISTS FOR (n:NewsArticle) ON (n.created_at);
