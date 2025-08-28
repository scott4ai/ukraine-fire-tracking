#!/usr/bin/env python3

import sqlite3
import time

def get_fire_events_for_ui(db_path='fire_data.db', start_date=None, end_date=None):
    """
    Fast query for UI simulator - returns fire events with color coding.
    This is optimized for the producer that reads every second.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    cursor = conn.cursor()
    
    if start_date and end_date:
        query = """
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
                matched_event_type,
                matched_place_name
            FROM fire_events
            WHERE datetime_utc BETWEEN ? AND ?
            ORDER BY datetime_utc
        """
        cursor.execute(query, (start_date, end_date))
    else:
        # Get all events
        query = """
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
                matched_event_type,
                matched_place_name
            FROM fire_events
            ORDER BY datetime_utc
        """
        cursor.execute(query)
    
    results = cursor.fetchall()
    conn.close()
    return results

def get_svm_training_data(db_path='fire_data.db', balanced=True):
    """
    Get training data for SVM classifier.
    If balanced=True, returns equal numbers of violent and non-violent events.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    if balanced:
        # Get balanced dataset
        query = """
            -- Get all violent events
            SELECT * FROM svm_training_data WHERE is_violent_event = 1
            UNION ALL
            -- Get random sample of non-violent events (same size as violent)
            SELECT * FROM svm_training_data 
            WHERE is_violent_event = 0
            ORDER BY RANDOM()
            LIMIT (SELECT COUNT(*) FROM svm_training_data WHERE is_violent_event = 1)
        """
    else:
        # Get all data
        query = "SELECT * FROM svm_training_data"
    
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()
    return results

def benchmark_ui_query():
    """
    Benchmark the UI query performance.
    """
    print("Benchmarking UI query performance...")
    
    # Test query for one day of data
    start_date = '2024-01-01 00:00:00'
    end_date = '2024-01-02 00:00:00'
    
    start_time = time.time()
    events = get_fire_events_for_ui(start_date=start_date, end_date=end_date)
    query_time = (time.time() - start_time) * 1000  # Convert to ms
    
    print(f"Query returned {len(events)} events in {query_time:.2f}ms")
    
    # Show sample of different color schemes
    color_counts = {}
    for event in events:
        color = event['color_scheme']
        color_counts[color] = color_counts.get(color, 0) + 1
    
    print("\nColor distribution:")
    for color, count in color_counts.items():
        print(f"  {color}: {count}")
    
    return events

def sample_color_mapping():
    """
    Show how to map colors in the UI based on confidence levels.
    """
    color_map = {
        'purple_high': {
            'hex': '#6B46C1',  # Deep purple
            'rgb': (107, 70, 193),
            'intensity': 1.0,
            'description': 'High confidence violent event'
        },
        'purple_medium': {
            'hex': '#9333EA',  # Medium purple
            'rgb': (147, 51, 234),
            'intensity': 0.7,
            'description': 'Medium confidence violent event'
        },
        'purple_low': {
            'hex': '#C084FC',  # Light purple
            'rgb': (192, 132, 252),
            'intensity': 0.4,
            'description': 'Low confidence violent event'
        },
        'default': {
            'hex': '#FF6B6B',  # Red/orange for regular fires
            'rgb': (255, 107, 107),
            'intensity': None,  # Use brightness value
            'description': 'Regular fire event'
        }
    }
    
    print("\nRecommended color mapping for UI:")
    print("="*50)
    for scheme, details in color_map.items():
        print(f"\n{scheme}:")
        print(f"  Hex: {details['hex']}")
        print(f"  RGB: {details['rgb']}")
        print(f"  Intensity: {details['intensity']}")
        print(f"  Description: {details['description']}")
    
    return color_map

if __name__ == "__main__":
    # Benchmark UI query
    benchmark_ui_query()
    
    # Show color mapping
    sample_color_mapping()
    
    # Test SVM data retrieval
    print("\n" + "="*50)
    print("SVM Training Data Summary:")
    svm_data = get_svm_training_data(balanced=False)
    print(f"Total training samples: {len(svm_data)}")
    
    violent_count = sum(1 for row in svm_data if row[11] == 1)  # is_violent_event column
    print(f"Violent events: {violent_count:,}")
    print(f"Non-violent events: {len(svm_data) - violent_count:,}")