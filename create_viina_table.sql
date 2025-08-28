-- Create table for VIINA incidents data
CREATE TABLE IF NOT EXISTS viina_incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    datetime DATETIME NOT NULL,
    longitude REAL NOT NULL,
    latitude REAL NOT NULL,
    place_name TEXT NOT NULL,
    event_type TEXT,
    headline TEXT
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_viina_datetime ON viina_incidents(datetime);
CREATE INDEX IF NOT EXISTS idx_viina_location ON viina_incidents(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_viina_datetime_location ON viina_incidents(datetime, latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_viina_place ON viina_incidents(place_name);
CREATE INDEX IF NOT EXISTS idx_viina_event_type ON viina_incidents(event_type);