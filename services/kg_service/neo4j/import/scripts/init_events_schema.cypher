// ============================================================
// Events Schema — Constraints & Indexes
// ============================================================

// Unique constraints
CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:Event) REQUIRE e.eventId IS UNIQUE;

CREATE CONSTRAINT event_type_name IF NOT EXISTS FOR (t:EventType) REQUIRE t.name IS UNIQUE;

CREATE CONSTRAINT venue_name IF NOT EXISTS FOR (v:Venue) REQUIRE v.name IS UNIQUE;

CREATE CONSTRAINT organizer_name IF NOT EXISTS FOR (o:Organizer) REQUIRE o.name IS UNIQUE;

// Performance indexes — Event
CREATE INDEX event_title IF NOT EXISTS FOR (e:Event) ON (e.title);

CREATE INDEX event_date_start IF NOT EXISTS FOR (e:Event) ON (e.dateStartIso);

CREATE INDEX event_date_end IF NOT EXISTS FOR (e:Event) ON (e.dateEndIso);

CREATE INDEX event_visibility IF NOT EXISTS FOR (e:Event) ON (e.visibility);

CREATE INDEX event_venue IF NOT EXISTS FOR (e:Event) ON (e.venue);

// Performance indexes — Venue
CREATE INDEX venue_city IF NOT EXISTS FOR (v:Venue) ON (v.city);
