#!/usr/bin/env python3

import sqlite3
import csv
import os
import glob
from datetime import datetime

def import_viina_data(db_path='fire_data.db', data_dir='viina_data'):
    """
    Import VIINA incidents CSV files into SQLite database.
    """
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all CSV files
    csv_files = sorted(glob.glob(os.path.join(data_dir, '*.csv')))
    
    if not csv_files:
        print(f"No CSV files found in {data_dir}")
        return
    
    print(f"Found {len(csv_files)} CSV files to import")
    
    total_rows = 0
    
    for csv_file in csv_files:
        filename = os.path.basename(csv_file)
        print(f"\nProcessing {filename}...")
        
        rows_imported = 0
        
        try:
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    try:
                        # Insert row into database
                        # Ensure event_type is at least 'loc' since all records have location
                        event_type = row.get('event_type', '').strip()
                        if not event_type:
                            event_type = 'loc'
                        
                        cursor.execute("""
                            INSERT INTO viina_incidents 
                            (datetime, longitude, latitude, place_name, event_type, headline)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            row['datetime'],
                            float(row['lon']),
                            float(row['lat']),
                            row['place_name'],
                            event_type,
                            row.get('headline', '')
                        ))
                        rows_imported += 1
                        
                    except Exception as e:
                        print(f"  Error importing row: {e}")
                        print(f"  Row data: {row}")
                        continue
                
                conn.commit()
                print(f"  Imported {rows_imported} rows from {filename}")
                total_rows += rows_imported
                
        except Exception as e:
            print(f"  Error processing {filename}: {e}")
            conn.rollback()
            continue
    
    print(f"\n{'='*50}")
    print(f"Import complete!")
    print(f"Total rows imported: {total_rows}")
    
    # Verify data
    cursor.execute("SELECT COUNT(*) FROM viina_incidents")
    count = cursor.fetchone()[0]
    print(f"Total rows in database: {count}")
    
    # Show date range
    cursor.execute("SELECT MIN(datetime), MAX(datetime) FROM viina_incidents")
    min_date, max_date = cursor.fetchone()
    print(f"Date range: {min_date} to {max_date}")
    
    # Show sample data
    print("\nSample data (first 3 rows):")
    cursor.execute("SELECT datetime, place_name, event_type FROM viina_incidents LIMIT 3")
    for row in cursor.fetchall():
        print(f"  {row[0]} | {row[1]} | {row[2]}")
    
    conn.close()

if __name__ == "__main__":
    import_viina_data()