#!/usr/bin/env python3

import sqlite3
import math
from datetime import datetime, timedelta
import json

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points on Earth in kilometers."""
    R = 6371  # Earth's radius in kilometers
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

def match_datasets(distance_km=5, time_hours=12, create_table=True):
    """
    Match fire events with VIINA incidents based on proximity in space and time.
    
    Parameters:
    - distance_km: Maximum distance between events (default: 5km)
    - time_hours: Time window before/after fire event (default: 12 hours)
    - create_table: Whether to create a new table with matched data
    """
    
    conn = sqlite3.connect('fire_data.db')
    cursor = conn.cursor()
    
    print(f"Matching with thresholds: ≤{distance_km}km, ±{time_hours}h")
    print("="*60)
    
    # Create matched events table if requested
    if create_table:
        cursor.execute("DROP TABLE IF EXISTS matched_events")
        cursor.execute("""
            CREATE TABLE matched_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fire_datetime DATETIME NOT NULL,
                fire_latitude REAL NOT NULL,
                fire_longitude REAL NOT NULL,
                fire_brightness REAL,
                fire_bright_t31 REAL,
                fire_frp REAL,
                fire_confidence TEXT,
                fire_satellite TEXT,
                viina_datetime DATETIME NOT NULL,
                viina_latitude REAL NOT NULL,
                viina_longitude REAL NOT NULL,
                viina_place_name TEXT,
                viina_event_type TEXT,
                viina_headline TEXT,
                distance_km REAL NOT NULL,
                time_diff_hours REAL NOT NULL,
                match_confidence TEXT
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX idx_matched_fire_datetime ON matched_events(fire_datetime)")
        cursor.execute("CREATE INDEX idx_matched_viina_datetime ON matched_events(viina_datetime)")
        cursor.execute("CREATE INDEX idx_matched_location ON matched_events(fire_latitude, fire_longitude)")
        cursor.execute("CREATE INDEX idx_matched_confidence ON matched_events(match_confidence)")
    
    # Get total fire events count for progress tracking
    cursor.execute("SELECT COUNT(*) FROM fire_events")
    total_fires = cursor.fetchone()[0]
    
    # Process in chunks to avoid memory issues
    chunk_size = 10000
    offset = 0
    total_matches = 0
    processed = 0
    
    # Track statistics
    event_type_counts = {}
    
    while offset < total_fires:
        cursor.execute("""
            SELECT id, datetime_utc, latitude, longitude, brightness, bright_t31, 
                   frp, confidence, satellite
            FROM fire_events
            ORDER BY datetime_utc
            LIMIT ? OFFSET ?
        """, (chunk_size, offset))
        
        fire_events = cursor.fetchall()
        
        if not fire_events:
            break
        
        for fire_row in fire_events:
            fire_id, fire_dt_str, fire_lat, fire_lon = fire_row[:4]
            
            # Parse datetime
            fire_datetime = datetime.fromisoformat(fire_dt_str.replace('Z', '+00:00'))
            time_window_start = fire_datetime - timedelta(hours=time_hours)
            time_window_end = fire_datetime + timedelta(hours=time_hours)
            
            # Rough bounding box for initial filtering
            lat_delta = distance_km / 111
            lon_delta = distance_km / (111 * math.cos(math.radians(fire_lat)))
            
            # Find potential VIINA matches
            cursor.execute("""
                SELECT datetime, latitude, longitude, place_name, event_type, headline
                FROM viina_incidents
                WHERE datetime BETWEEN ? AND ?
                AND latitude BETWEEN ? AND ?
                AND longitude BETWEEN ? AND ?
            """, (
                time_window_start.isoformat(),
                time_window_end.isoformat(),
                fire_lat - lat_delta,
                fire_lat + lat_delta,
                fire_lon - lon_delta,
                fire_lon + lon_delta
            ))
            
            viina_candidates = cursor.fetchall()
            
            # Check each candidate for precise distance
            for viina_row in viina_candidates:
                viina_dt_str, viina_lat, viina_lon, place, event_type, headline = viina_row
                
                # Calculate precise distance
                distance = haversine_distance(fire_lat, fire_lon, viina_lat, viina_lon)
                
                if distance <= distance_km:
                    # Calculate time difference
                    viina_datetime = datetime.fromisoformat(viina_dt_str)
                    time_diff = abs((fire_datetime - viina_datetime).total_seconds() / 3600)
                    
                    # Determine match confidence based on distance and time
                    if distance <= 1 and time_diff <= 2:
                        confidence = "high"
                    elif distance <= 2 and time_diff <= 6:
                        confidence = "medium"
                    else:
                        confidence = "low"
                    
                    # Insert matched event
                    if create_table:
                        cursor.execute("""
                            INSERT INTO matched_events (
                                fire_datetime, fire_latitude, fire_longitude,
                                fire_brightness, fire_bright_t31, fire_frp,
                                fire_confidence, fire_satellite,
                                viina_datetime, viina_latitude, viina_longitude,
                                viina_place_name, viina_event_type, viina_headline,
                                distance_km, time_diff_hours, match_confidence
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            fire_dt_str, fire_lat, fire_lon,
                            fire_row[4], fire_row[5], fire_row[6], fire_row[7], fire_row[8],
                            viina_dt_str, viina_lat, viina_lon,
                            place, event_type, headline,
                            distance, time_diff, confidence
                        ))
                    
                    # Track event types
                    if event_type:
                        event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
                    
                    total_matches += 1
                    break  # Only take first/best match for each fire
            
            processed += 1
            
        # Progress update
        pct = (processed / total_fires) * 100
        print(f"Processed {processed:,}/{total_fires:,} fire events ({pct:.1f}%), found {total_matches:,} matches", end='\r')
        
        conn.commit()
        offset += chunk_size
    
    print()  # New line after progress
    print("="*60)
    print(f"Matching complete!")
    print(f"Total fire events processed: {processed:,}")
    print(f"Total matches found: {total_matches:,}")
    print(f"Match rate: {(total_matches/processed)*100:.2f}%")
    
    if create_table:
        # Analyze match confidence distribution
        cursor.execute("""
            SELECT match_confidence, COUNT(*) 
            FROM matched_events 
            GROUP BY match_confidence
        """)
        print("\nMatch confidence distribution:")
        for conf, count in cursor.fetchall():
            print(f"  {conf}: {count:,}")
        
        # Top matched event types
        print("\nTop 10 matched VIINA event types:")
        sorted_types = sorted(event_type_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        for event_type, count in sorted_types:
            print(f"  {event_type[:50]:50} {count:,}")
    
    conn.close()
    
    return total_matches

if __name__ == "__main__":
    import sys
    
    # Allow command-line arguments
    distance = float(sys.argv[1]) if len(sys.argv) > 1 else 5
    time_window = float(sys.argv[2]) if len(sys.argv) > 2 else 12
    
    match_datasets(distance_km=distance, time_hours=time_window)