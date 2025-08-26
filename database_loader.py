#!/usr/bin/env python3
"""
ETL script to load NASA FIRMS fire data from JSON files into SQLite database.
Processes VIIRS and MODIS satellite data with unified schema.
"""

import json
import sqlite3
import glob
from datetime import datetime
from dateutil import parser as date_parser
import os
import sys
from typing import Dict, List, Any, Optional

class FireDataETL:
    """ETL processor for fire detection data from NASA FIRMS."""
    
    def __init__(self, db_path: str = "fire_data.db"):
        """Initialize ETL with database path."""
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.total_records = 0
        
    def create_database(self):
        """Create SQLite database with fire_events table and indexes."""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        # Drop existing table if it exists
        self.cursor.execute("DROP TABLE IF EXISTS fire_events")
        
        # Create table with unified schema
        self.cursor.execute("""
            CREATE TABLE fire_events (
                id INTEGER PRIMARY KEY,
                datetime_utc DATETIME NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                brightness REAL NOT NULL,
                bright_t31 REAL NOT NULL,
                frp REAL DEFAULT 0.0,
                confidence TEXT DEFAULT 'low',
                scan REAL DEFAULT 1.0,
                track REAL DEFAULT 1.0,
                satellite TEXT NOT NULL,
                instrument TEXT NOT NULL,
                daynight TEXT DEFAULT 'U',
                type INTEGER DEFAULT 0,
                version TEXT DEFAULT '1.0'
            )
        """)
        
        # Create indexes for performance
        self.cursor.execute("CREATE INDEX idx_datetime ON fire_events(datetime_utc)")
        self.cursor.execute("CREATE INDEX idx_location ON fire_events(latitude, longitude)")
        self.cursor.execute("CREATE INDEX idx_datetime_location ON fire_events(datetime_utc, latitude, longitude)")
        
        self.conn.commit()
        print(f"Created database: {self.db_path}")
        
    def normalize_confidence(self, confidence: Any, instrument: str) -> str:
        """
        Normalize confidence values across VIIRS and MODIS.
        
        VIIRS: 'n' (nominal), 'l' (low), 'h' (high)
        MODIS: percentage (0-100)
        
        Returns: 'low', 'medium', or 'high'
        """
        if instrument == "VIIRS":
            # VIIRS confidence mapping
            confidence_str = str(confidence).lower()
            if confidence_str in ['n', 'l']:
                return 'low'
            elif confidence_str == 'h':
                return 'high'
            else:
                return 'low'  # Default for unknown
        else:  # MODIS
            # MODIS uses percentage
            try:
                conf_value = float(confidence)
                if conf_value <= 30:
                    return 'low'
                elif conf_value <= 70:
                    return 'medium'
                else:
                    return 'high'
            except (ValueError, TypeError):
                return 'low'  # Default for invalid values
    
    def parse_datetime(self, date_str: str, time_str: str) -> datetime:
        """
        Parse date and time strings to UTC datetime.
        
        Date format: "2023-08-01"
        Time format: "0106" (HHMM in UTC)
        """
        # Combine date and time strings
        datetime_str = f"{date_str} {time_str[:2]}:{time_str[2:4]}:00"
        
        # Parse to datetime (already in UTC)
        dt = date_parser.parse(datetime_str)
        
        return dt
    
    def get_default_value(self, field: str, data_type: type) -> Any:
        """Get default value for missing field."""
        defaults = {
            'frp': 0.0,
            'confidence': 'low',
            'scan': 1.0,
            'track': 1.0,
            'daynight': 'U',
            'type': 0,
            'version': '1.0'
        }
        
        if field in defaults:
            return defaults[field]
        elif data_type == float:
            return 0.0
        elif data_type == int:
            return 0
        elif data_type == str:
            return ''
        else:
            return None
    
    def process_record(self, record: Dict[str, Any], record_id: int) -> tuple:
        """
        Process a single fire record into database format.
        
        Returns tuple ready for database insertion.
        """
        # Extract and convert datetime
        datetime_utc = self.parse_datetime(
            record.get('acq_date', '2000-01-01'),
            record.get('acq_time', '0000')
        )
        
        # Get instrument type
        instrument = record.get('instrument', 'UNKNOWN')
        
        # Normalize confidence
        raw_confidence = record.get('confidence', 'low')
        confidence = self.normalize_confidence(raw_confidence, instrument)
        
        # Extract daynight, handling different formats
        daynight = str(record.get('daynight', 'U'))[0].upper()
        if daynight not in ['D', 'N']:
            daynight = 'U'
        
        # Build database record with defaults for missing fields
        db_record = (
            record_id,
            datetime_utc,
            float(record.get('latitude', 0.0)),
            float(record.get('longitude', 0.0)),
            float(record.get('brightness', 0.0)),
            float(record.get('bright_t31', 0.0)),
            float(record.get('frp', 0.0)),
            confidence,
            float(record.get('scan', 1.0)),
            float(record.get('track', 1.0)),
            str(record.get('satellite', 'UNKNOWN')),
            instrument,
            daynight,
            int(record.get('type', 0)),
            str(record.get('version', '1.0'))
        )
        
        return db_record
    
    def load_json_file(self, filepath: str) -> List[Dict[str, Any]]:
        """Load and parse a JSON file."""
        print(f"Loading {filepath}...")
        with open(filepath, 'r') as f:
            data = json.load(f)
        print(f"  Loaded {len(data)} records")
        return data
    
    def process_all_files(self, data_dir: str = "data"):
        """Process all JSON files in the data directory."""
        # Find all JSON files
        json_files = glob.glob(os.path.join(data_dir, "*.json"))
        
        if not json_files:
            print(f"No JSON files found in {data_dir}")
            return
        
        print(f"Found {len(json_files)} JSON files to process")
        
        # Collect all records
        all_records = []
        
        for filepath in json_files:
            records = self.load_json_file(filepath)
            all_records.extend(records)
        
        print(f"\nTotal records loaded: {len(all_records)}")
        
        # Sort by datetime for sequential processing
        print("Sorting records by datetime...")
        all_records.sort(key=lambda x: (x.get('acq_date', ''), x.get('acq_time', '')))
        
        # Process and insert records
        print("Processing and inserting records into database...")
        
        batch_size = 10000
        processed = 0
        
        for i in range(0, len(all_records), batch_size):
            batch = all_records[i:i + batch_size]
            batch_records = []
            
            for j, record in enumerate(batch):
                record_id = i + j + 1  # Sequential ID starting from 1
                try:
                    db_record = self.process_record(record, record_id)
                    batch_records.append(db_record)
                except Exception as e:
                    print(f"  Error processing record {record_id}: {e}")
                    continue
            
            # Batch insert
            if batch_records:
                self.cursor.executemany("""
                    INSERT INTO fire_events (
                        id, datetime_utc, latitude, longitude,
                        brightness, bright_t31, frp, confidence,
                        scan, track, satellite, instrument,
                        daynight, type, version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, batch_records)
                self.conn.commit()
            
            processed += len(batch_records)
            print(f"  Processed {processed}/{len(all_records)} records...")
        
        self.total_records = processed
        print(f"\nSuccessfully loaded {self.total_records} records into database")
    
    def verify_database(self):
        """Verify database integrity and display statistics."""
        print("\nDatabase Verification:")
        print("-" * 50)
        
        # Count total records
        self.cursor.execute("SELECT COUNT(*) FROM fire_events")
        count = self.cursor.fetchone()[0]
        print(f"Total records: {count}")
        
        # Date range
        self.cursor.execute("""
            SELECT MIN(datetime_utc), MAX(datetime_utc) 
            FROM fire_events
        """)
        min_date, max_date = self.cursor.fetchone()
        print(f"Date range: {min_date} to {max_date}")
        
        # Records by satellite
        self.cursor.execute("""
            SELECT satellite, COUNT(*) as cnt 
            FROM fire_events 
            GROUP BY satellite 
            ORDER BY cnt DESC
        """)
        print("\nRecords by satellite:")
        for satellite, cnt in self.cursor.fetchall():
            print(f"  {satellite}: {cnt}")
        
        # Records by instrument
        self.cursor.execute("""
            SELECT instrument, COUNT(*) as cnt 
            FROM fire_events 
            GROUP BY instrument 
            ORDER BY cnt DESC
        """)
        print("\nRecords by instrument:")
        for instrument, cnt in self.cursor.fetchall():
            print(f"  {instrument}: {cnt}")
        
        # Records by confidence
        self.cursor.execute("""
            SELECT confidence, COUNT(*) as cnt 
            FROM fire_events 
            GROUP BY confidence 
            ORDER BY cnt DESC
        """)
        print("\nRecords by confidence level:")
        for confidence, cnt in self.cursor.fetchall():
            print(f"  {confidence}: {cnt}")
        
        # Geographic bounds
        self.cursor.execute("""
            SELECT MIN(latitude), MAX(latitude), 
                   MIN(longitude), MAX(longitude) 
            FROM fire_events
        """)
        min_lat, max_lat, min_lon, max_lon = self.cursor.fetchone()
        print(f"\nGeographic bounds:")
        print(f"  Latitude: {min_lat:.2f} to {max_lat:.2f}")
        print(f"  Longitude: {min_lon:.2f} to {max_lon:.2f}")
        
        # Sample records for verification
        self.cursor.execute("""
            SELECT id, datetime_utc, latitude, longitude, confidence, frp
            FROM fire_events
            LIMIT 5
        """)
        print("\nSample records:")
        for record in self.cursor.fetchall():
            print(f"  ID {record[0]}: {record[1]} at ({record[2]:.3f}, {record[3]:.3f}), "
                  f"confidence={record[4]}, frp={record[5]:.2f}")
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            print(f"\nDatabase connection closed")
    
    def run(self):
        """Run the complete ETL process."""
        print("=" * 60)
        print("Fire Data ETL Process")
        print("=" * 60)
        
        try:
            # Create database
            self.create_database()
            
            # Process all JSON files
            self.process_all_files()
            
            # Verify results
            self.verify_database()
            
        except Exception as e:
            print(f"\nError during ETL process: {e}")
            sys.exit(1)
        finally:
            self.close()
        
        print("\n" + "=" * 60)
        print(f"ETL Process Complete!")
        print(f"Database: {self.db_path}")
        print(f"Total Records: {self.total_records}")
        print("=" * 60)


def main():
    """Main entry point."""
    # Check if data directory exists
    if not os.path.exists("data"):
        print("Error: 'data' directory not found")
        print("Please ensure the data directory contains the JSON fire data files")
        sys.exit(1)
    
    # Run ETL
    etl = FireDataETL()
    etl.run()


if __name__ == "__main__":
    main()