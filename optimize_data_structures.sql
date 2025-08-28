-- Optimize data structures for both use cases
-- Use Case 1: Fast UI lookups during simulation
-- Use Case 2: Ground truth dataset for SVM training

-- Step 1: Add match columns to fire_events table for O(1) UI lookups
ALTER TABLE fire_events ADD COLUMN is_matched BOOLEAN DEFAULT 0;
ALTER TABLE fire_events ADD COLUMN match_confidence TEXT DEFAULT NULL;
ALTER TABLE fire_events ADD COLUMN matched_event_type TEXT DEFAULT NULL;
ALTER TABLE fire_events ADD COLUMN matched_place_name TEXT DEFAULT NULL;

-- Step 2: Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_fire_events_matched ON fire_events(is_matched, match_confidence);
CREATE INDEX IF NOT EXISTS idx_fire_events_datetime_matched ON fire_events(datetime_utc, is_matched);

-- Step 3: Update fire_events with match data (using best match per fire event)
UPDATE fire_events
SET is_matched = 1,
    match_confidence = (
        SELECT match_confidence 
        FROM matched_events m 
        WHERE m.fire_datetime = fire_events.datetime_utc 
        AND m.fire_latitude = fire_events.latitude 
        AND m.fire_longitude = fire_events.longitude
        ORDER BY 
            CASE match_confidence 
                WHEN 'high' THEN 1 
                WHEN 'medium' THEN 2 
                WHEN 'low' THEN 3 
            END,
            distance_km ASC
        LIMIT 1
    ),
    matched_event_type = (
        SELECT viina_event_type 
        FROM matched_events m 
        WHERE m.fire_datetime = fire_events.datetime_utc 
        AND m.fire_latitude = fire_events.latitude 
        AND m.fire_longitude = fire_events.longitude
        ORDER BY 
            CASE match_confidence 
                WHEN 'high' THEN 1 
                WHEN 'medium' THEN 2 
                WHEN 'low' THEN 3 
            END,
            distance_km ASC
        LIMIT 1
    ),
    matched_place_name = (
        SELECT viina_place_name 
        FROM matched_events m 
        WHERE m.fire_datetime = fire_events.datetime_utc 
        AND m.fire_latitude = fire_events.latitude 
        AND m.fire_longitude = fire_events.longitude
        ORDER BY 
            CASE match_confidence 
                WHEN 'high' THEN 1 
                WHEN 'medium' THEN 2 
                WHEN 'low' THEN 3 
            END,
            distance_km ASC
        LIMIT 1
    )
WHERE EXISTS (
    SELECT 1 FROM matched_events m 
    WHERE m.fire_datetime = fire_events.datetime_utc 
    AND m.fire_latitude = fire_events.latitude 
    AND m.fire_longitude = fire_events.longitude
);

-- Step 4: Create materialized view for SVM training dataset
-- This denormalizes all the data needed for training
CREATE TABLE IF NOT EXISTS svm_training_data AS
SELECT 
    -- Fire event features
    f.datetime_utc,
    f.latitude,
    f.longitude,
    f.brightness,
    f.bright_t31,
    f.frp,
    f.scan,
    f.track,
    f.confidence as fire_confidence,
    f.daynight,
    f.satellite,
    -- Match information
    CASE WHEN m.id IS NOT NULL THEN 1 ELSE 0 END as is_violent_event,
    m.match_confidence,
    m.distance_km,
    m.time_diff_hours,
    -- VIINA incident features (NULL if no match)
    m.viina_event_type,
    m.viina_place_name,
    -- Derived features for ML
    strftime('%H', f.datetime_utc) as hour_of_day,
    strftime('%w', f.datetime_utc) as day_of_week,
    strftime('%m', f.datetime_utc) as month,
    -- Spatial features
    CAST(f.latitude * 10 AS INTEGER) / 10.0 as lat_grid,
    CAST(f.longitude * 10 AS INTEGER) / 10.0 as lon_grid
FROM fire_events f
LEFT JOIN matched_events m ON 
    m.fire_datetime = f.datetime_utc 
    AND m.fire_latitude = f.latitude 
    AND m.fire_longitude = f.longitude
    AND m.distance_km = (
        SELECT MIN(distance_km) 
        FROM matched_events m2 
        WHERE m2.fire_datetime = f.datetime_utc 
        AND m2.fire_latitude = f.latitude 
        AND m2.fire_longitude = f.longitude
    );

-- Create indexes on training data
CREATE INDEX idx_svm_training_violent ON svm_training_data(is_violent_event);
CREATE INDEX idx_svm_training_confidence ON svm_training_data(match_confidence);

-- Step 5: Create fast query view for UI simulator
CREATE VIEW IF NOT EXISTS fire_events_ui AS
SELECT 
    datetime_utc,
    latitude,
    longitude,
    brightness,
    bright_t31,
    CASE 
        WHEN match_confidence = 'high' THEN 'purple_high'
        WHEN match_confidence = 'medium' THEN 'purple_medium'
        WHEN match_confidence = 'low' THEN 'purple_low'
        ELSE 'default'
    END as color_scheme,
    is_matched,
    match_confidence,
    matched_event_type,
    matched_place_name
FROM fire_events;

-- Verify the updates
SELECT 
    'Total fire events' as metric, 
    COUNT(*) as count 
FROM fire_events
UNION ALL
SELECT 
    'Matched fire events', 
    COUNT(*) 
FROM fire_events 
WHERE is_matched = 1
UNION ALL
SELECT 
    'High confidence matches', 
    COUNT(*) 
FROM fire_events 
WHERE match_confidence = 'high'
UNION ALL
SELECT 
    'Medium confidence matches', 
    COUNT(*) 
FROM fire_events 
WHERE match_confidence = 'medium'
UNION ALL
SELECT 
    'Low confidence matches', 
    COUNT(*) 
FROM fire_events 
WHERE match_confidence = 'low';