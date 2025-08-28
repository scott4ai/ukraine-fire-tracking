#!/usr/bin/env python3

import sqlite3
import math
from datetime import datetime, timedelta
from collections import defaultdict

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

def analyze_datasets():
    conn = sqlite3.connect('fire_data.db')
    cursor = conn.cursor()
    
    # Get date ranges and counts
    print("="*60)
    print("DATASET OVERVIEW")
    print("="*60)
    
    cursor.execute("SELECT COUNT(*), MIN(datetime_utc), MAX(datetime_utc) FROM fire_events")
    fire_count, fire_min, fire_max = cursor.fetchone()
    print(f"\nFire Events:")
    print(f"  Count: {fire_count:,}")
    print(f"  Date range: {fire_min} to {fire_max}")
    
    cursor.execute("SELECT COUNT(*), MIN(datetime), MAX(datetime) FROM viina_incidents")
    viina_count, viina_min, viina_max = cursor.fetchone()
    print(f"\nVIINA Incidents:")
    print(f"  Count: {viina_count:,}")
    print(f"  Date range: {viina_min} to {viina_max}")
    
    # Analyze event types in VIINA data
    print("\n" + "="*60)
    print("VIINA EVENT TYPES (Top 20)")
    print("="*60)
    cursor.execute("""
        SELECT event_type, COUNT(*) as cnt 
        FROM viina_incidents 
        WHERE event_type IS NOT NULL AND event_type != ''
        GROUP BY event_type 
        ORDER BY cnt DESC 
        LIMIT 20
    """)
    for row in cursor.fetchall():
        print(f"  {row[0][:50]:50} {row[1]:6,}")
    
    # Find potential matches with different thresholds
    print("\n" + "="*60)
    print("TESTING MATCH THRESHOLDS")
    print("="*60)
    
    distance_thresholds = [1, 2, 5, 10, 20]  # km
    time_thresholds = [1, 6, 12, 24, 48]  # hours
    
    # Get a sample of fire events from 2023-2024
    cursor.execute("""
        SELECT datetime_utc, latitude, longitude 
        FROM fire_events 
        WHERE datetime_utc BETWEEN '2023-01-01' AND '2024-12-31'
        ORDER BY RANDOM()
        LIMIT 1000
    """)
    fire_samples = cursor.fetchall()
    
    results = defaultdict(int)
    
    for dist_km in distance_thresholds:
        for time_hours in time_thresholds:
            matches = 0
            
            for fire_dt, fire_lat, fire_lon in fire_samples:
                # Convert string to datetime
                fire_datetime = datetime.fromisoformat(fire_dt.replace('Z', '+00:00'))
                time_window_start = fire_datetime - timedelta(hours=time_hours)
                time_window_end = fire_datetime + timedelta(hours=time_hours)
                
                # Find VIINA incidents within time window
                cursor.execute("""
                    SELECT latitude, longitude, datetime
                    FROM viina_incidents
                    WHERE datetime BETWEEN ? AND ?
                    AND latitude BETWEEN ? AND ?
                    AND longitude BETWEEN ? AND ?
                """, (
                    time_window_start.isoformat(),
                    time_window_end.isoformat(),
                    fire_lat - (dist_km/111),  # rough latitude degree to km
                    fire_lat + (dist_km/111),
                    fire_lon - (dist_km/(111*math.cos(math.radians(fire_lat)))),
                    fire_lon + (dist_km/(111*math.cos(math.radians(fire_lat))))
                ))
                
                for viina_lat, viina_lon, viina_dt in cursor.fetchall():
                    distance = haversine_distance(fire_lat, fire_lon, viina_lat, viina_lon)
                    if distance <= dist_km:
                        matches += 1
                        break  # Count only one match per fire event
            
            results[(dist_km, time_hours)] = matches
            match_pct = (matches / len(fire_samples)) * 100
            print(f"  Distance ≤{dist_km:2}km, Time ±{time_hours:2}h: {matches:4}/{len(fire_samples)} matches ({match_pct:.1f}%)")
    
    # Analyze specific event types that might correlate with fires
    print("\n" + "="*60)
    print("FIRE-RELATED VIINA EVENT TYPES")
    print("="*60)
    
    fire_related_keywords = ['fire', 'airstrike', 'artillery', 'explosion', 'shelling', 'missile', 'rocket']
    
    for keyword in fire_related_keywords:
        cursor.execute("""
            SELECT COUNT(*) 
            FROM viina_incidents 
            WHERE event_type LIKE ?
        """, (f'%{keyword}%',))
        count = cursor.fetchone()[0]
        print(f"  Events containing '{keyword}': {count:,}")
    
    # Sample some actual matches to inspect
    print("\n" + "="*60)
    print("SAMPLE MATCHED EVENTS (5km, 6h threshold)")
    print("="*60)
    
    cursor.execute("""
        SELECT 
            f.datetime_utc, f.latitude, f.longitude, f.brightness,
            v.datetime, v.latitude, v.longitude, v.place_name, v.event_type
        FROM fire_events f
        INNER JOIN viina_incidents v ON 
            julianday(v.datetime) BETWEEN julianday(f.datetime_utc) - 0.25 AND julianday(f.datetime_utc) + 0.25
        WHERE f.datetime_utc BETWEEN '2023-06-01' AND '2023-06-30'
        LIMIT 10
    """)
    
    matches = cursor.fetchall()
    match_count = 0
    
    for match in matches:
        fire_dt, fire_lat, fire_lon, brightness = match[0:4]
        viina_dt, viina_lat, viina_lon, place, event_type = match[4:9]
        
        distance = haversine_distance(fire_lat, fire_lon, viina_lat, viina_lon)
        
        if distance <= 5:  # 5km threshold
            match_count += 1
            time_diff = abs((datetime.fromisoformat(fire_dt.replace('Z', '+00:00')) - 
                           datetime.fromisoformat(viina_dt)).total_seconds() / 3600)
            
            print(f"\nMatch #{match_count}:")
            print(f"  Fire: {fire_dt}, ({fire_lat:.4f}, {fire_lon:.4f}), brightness: {brightness}")
            print(f"  VIINA: {viina_dt}, {place}, {event_type}")
            print(f"  Distance: {distance:.2f}km, Time diff: {time_diff:.1f}h")
            
            if match_count >= 5:
                break
    
    conn.close()

if __name__ == "__main__":
    analyze_datasets()