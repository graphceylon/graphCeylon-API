// ============================================================
// Bus Schedule Schema — Transportation Domain
// ============================================================
// Creates constraints, indexes, and the BusDepot reference nodes
// for BusTerminal, BusSchedule, and BusDepot entities.
// ============================================================

// --- Uniqueness constraints ---
CREATE CONSTRAINT bus_terminal_name IF NOT EXISTS
FOR (bt:BusTerminal) REQUIRE bt.name IS UNIQUE;

CREATE CONSTRAINT bus_schedule_id IF NOT EXISTS
FOR (bs:BusSchedule) REQUIRE bs.schedule_id IS UNIQUE;

CREATE CONSTRAINT bus_depot_name IF NOT EXISTS
FOR (bd:BusDepot) REQUIRE bd.name IS UNIQUE;

// --- Indexes for frequent lookups ---
CREATE INDEX bus_terminal_province IF NOT EXISTS
FOR (bt:BusTerminal) ON (bt.province);

CREATE INDEX bus_terminal_district IF NOT EXISTS
FOR (bt:BusTerminal) ON (bt.district);

CREATE INDEX bus_schedule_date IF NOT EXISTS
FOR (bs:BusSchedule) ON (bs.schedule_date);

CREATE INDEX bus_schedule_departure IF NOT EXISTS
FOR (bs:BusSchedule) ON (bs.departure_time);

CREATE INDEX bus_schedule_origin IF NOT EXISTS
FOR (bs:BusSchedule) ON (bs.origin);

CREATE INDEX bus_schedule_destination IF NOT EXISTS
FOR (bs:BusSchedule) ON (bs.destination);

CREATE INDEX bus_depot_domain IF NOT EXISTS
FOR (bd:BusDepot) ON (bd.domain);

// --- Full-text index for bus terminal search ---
CREATE FULLTEXT INDEX bus_terminal_search IF NOT EXISTS
FOR (bt:BusTerminal) ON EACH [bt.name, bt.formatted_address, bt.vicinity];
