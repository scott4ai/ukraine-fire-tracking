#!/usr/bin/env python3
"""
Ukraine Fire Tracking System - Main Flask Application
Producer-consumer architecture with WebSocket communication.
"""

import os
import sqlite3
import json
import time
import threading
from datetime import datetime, timedelta
from queue import Queue, Empty
from typing import Dict, List, Any, Optional
import logging

from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO, emit, disconnect
import config


# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT,
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class FireDataProducer:
    """Producer thread that reads fire data from database and feeds queue."""
    
    def __init__(self, data_queue: Queue, db_path: str):
        """Initialize producer with queue and database."""
        self.data_queue = data_queue
        self.db_path = db_path
        self.is_running = False
        self.is_paused = False
        self.current_speed = config.DEFAULT_SPEED
        self.start_date = None
        self.end_date = None
        self.current_datetime = None
        self.thread = None
        self.timer = None
        
        # Statistics
        self.total_records = 0
        self.processed_records = 0
        
    def set_date_range(self, start_date: str, end_date: str):
        """Set date range for playback."""
        self.start_date = datetime.fromisoformat(start_date)
        self.end_date = datetime.fromisoformat(end_date)
        self.current_datetime = self.start_date
        logger.info(f"Producer date range set: {start_date} to {end_date}")
    
    def set_speed(self, speed_key: str):
        """Update playback speed."""
        if speed_key in config.PLAYBACK_SPEEDS:
            self.current_speed = speed_key
            logger.info(f"Producer speed changed to {speed_key} ({config.SPEED_LABELS[speed_key]})")
    
    def pause(self):
        """Pause the producer."""
        self.is_paused = True
        logger.info("Producer paused")
    
    def resume(self):
        """Resume the producer."""
        self.is_paused = False
        logger.info("Producer resumed")
    
    def stop(self):
        """Stop the producer."""
        self.is_running = False
        logger.info("Producer stopped")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get current producer statistics."""
        return {
            'total_records': self.total_records,
            'processed_records': self.processed_records,
            'current_datetime': self.current_datetime.isoformat() if self.current_datetime else None,
            'speed': self.current_speed,
            'is_running': self.is_running,
            'is_paused': self.is_paused
        }
    
    def query_interval(self, start_dt: datetime, end_dt: datetime) -> List[Dict[str, Any]]:
        """
        Query ALL fire records within a specific time interval.
        
        Args:
            start_dt: Starting datetime for interval (exclusive)
            end_dt: Ending datetime for interval (inclusive)
            
        Returns:
            List of ALL fire records in the interval
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            cursor = conn.cursor()
            
            # Query ALL records in this specific time interval - NO LIMIT!
            # Include match data for violent event visualization
            query = """
                SELECT * FROM fire_events 
                WHERE datetime_utc > ? AND datetime_utc <= ?
                ORDER BY datetime_utc
            """
            
            # Format datetime as SQLite expects: "YYYY-MM-DD HH:MM:SS"
            start_str = start_dt.strftime('%Y-%m-%d %H:%M:%S')
            end_str = end_dt.strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute(query, (start_str, end_str))
            rows = cursor.fetchall()
            
            
            # Convert to list of dictionaries
            records = []
            for row in rows:
                record = {
                    'id': row['id'],
                    'datetime_utc': row['datetime_utc'],
                    'latitude': row['latitude'],
                    'longitude': row['longitude'],
                    'brightness': row['brightness'],
                    'bright_t31': row['bright_t31'],
                    'frp': row['frp'],
                    'confidence': row['confidence'],
                    'scan': row['scan'],
                    'track': row['track'],
                    'satellite': row['satellite'],
                    'instrument': row['instrument'],
                    'daynight': row['daynight'],
                    'type': row['type'],
                    'version': row['version'],
                    'fade_duration': config.get_fade_duration(self.current_speed),
                    # Add violent event match data
                    'is_matched': row['is_matched'] if 'is_matched' in row.keys() else 0,
                    'match_confidence': row['match_confidence'] if 'match_confidence' in row.keys() else None,
                    'matched_event_type': row['matched_event_type'] if 'matched_event_type' in row.keys() else None,
                    'matched_place_name': row['matched_place_name'] if 'matched_place_name' in row.keys() else None
                }
                records.append(record)
            
            conn.close()
            return records
            
        except Exception as e:
            logger.error(f"Database query error: {e}")
            return []
    
    def run_producer(self):
        """Main producer loop - queries every 1 second."""
        logger.info("Producer thread started")
        
        if not self.start_date or not self.end_date:
            logger.error("Date range not set for producer")
            return
        
        self.is_running = True
        
        try:
            # Get total record count for statistics
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM fire_events 
                WHERE datetime_utc >= ? AND datetime_utc <= ?
            """, (self.start_date.isoformat(), self.end_date.isoformat()))
            self.total_records = cursor.fetchone()[0]
            conn.close()
            
            logger.info(f"Producer will process {self.total_records} records")
            
            self.current_datetime = self.start_date
            
            # Main loop - use precise timing independent of processing time
            last_interval_time = time.time()
            
            while self.is_running and self.current_datetime <= self.end_date:
                current_time = time.time()
                
                # Only process if at least 1 second has elapsed
                elapsed = current_time - last_interval_time
                if elapsed >= 1.0 and not self.is_paused:
                    # Get hours to advance based on current speed (e.g., 6 hours for 'slowest')
                    hours_per_second = config.PLAYBACK_SPEEDS[self.current_speed]
                    
                    # Calculate the end of this interval
                    next_datetime = self.current_datetime + timedelta(hours=hours_per_second)
                    
                    # Clamp to end date if necessary
                    if next_datetime > self.end_date:
                        next_datetime = self.end_date
                    
                    # Query ALL records in this interval (current_datetime < t <= next_datetime)
                    records = self.query_interval(self.current_datetime, next_datetime)
                    
                    # Check if we've reached the end of actual data
                    if not records and self.current_datetime < self.end_date:
                        # No more data available, check if there might be data in future intervals
                        # Query ahead to see if any data exists beyond current time
                        future_check_time = self.current_datetime + timedelta(days=30)  # Check 30 days ahead
                        if future_check_time > self.end_date:
                            future_check_time = self.end_date
                        
                        future_records = self.query_interval(self.current_datetime, future_check_time)
                        if not future_records:
                            logger.info(f"No more fire data available beyond {self.current_datetime.strftime('%Y-%m-%d')}. Ending simulation.")
                            break  # Exit the loop to trigger end_of_data signal
                    
                    # Send data to queue (even if empty, to maintain timing)
                    batch_data = {
                        'type': 'fire_batch',
                        'records': records,
                        'timestamp': next_datetime.isoformat(),
                        'speed': self.current_speed
                    }
                    
                    try:
                        self.data_queue.put(batch_data)
                        if records:
                            self.processed_records += len(records)
                    except Exception as e:
                        logger.warning(f"Failed to queue batch: {e}")
                    
                    # Advance to next interval
                    self.current_datetime = next_datetime
                    last_interval_time = current_time
                
                # Short sleep to prevent CPU spinning
                time.sleep(0.01)
            
        except Exception as e:
            logger.error(f"Producer thread error: {e}")
        finally:
            # Signal end of data
            try:
                self.data_queue.put({'type': 'end_of_data'})
            except:
                pass
            
            self.is_running = False
            logger.info("Producer thread finished")
    
    def start(self):
        """Start producer thread."""
        if not self.thread or not self.thread.is_alive():
            self.is_running = True  # Set running flag before starting thread
            self.thread = threading.Thread(target=self.run_producer)
            self.thread.daemon = True
            self.thread.start()


class FireDataConsumer:
    """Consumer thread that processes queue and emits to clients."""
    
    def __init__(self, data_queue: Queue, socketio_app):
        """Initialize consumer with queue and SocketIO app."""
        self.data_queue = data_queue
        self.socketio = socketio_app
        self.is_running = False
        self.thread = None
        
        # Active fire tracking
        self.active_fires = {}
        self.fire_statistics = {
            'total_fires': 0,
            'active_count': 0,
            'current_time': None
        }
    
    def emit_fire_update(self, batch_data: Dict[str, Any]):
        """Emit fire update to all connected clients."""
        records = batch_data['records']
        
        if records:
            # Update statistics
            self.fire_statistics['total_fires'] += len(records)
            self.fire_statistics['current_time'] = batch_data['timestamp']
            self.fire_statistics['active_count'] = len(self.active_fires)
            
            # Emit to clients
            self.socketio.emit('fire_update', {
                'fires': records,
                'timestamp': batch_data['timestamp'],
                'speed': batch_data['speed'],
                'statistics': self.fire_statistics
            })
            
            logger.debug(f"Emitted {len(records)} fire records to clients")
    
    def run_consumer(self):
        """Main consumer loop."""
        logger.info("Consumer thread started")
        self.is_running = True
        
        try:
            while self.is_running:
                try:
                    # Get data from queue (blocking)
                    logger.debug("Consumer waiting for queue data...")
                    data = self.data_queue.get(timeout=1.0)
                    logger.info(f"Consumer received: {data['type']}")
                    
                    if data['type'] == 'end_of_data':
                        logger.info("Received end of data signal")
                        self.socketio.emit('playback_ended')
                        break
                    elif data['type'] == 'fire_batch':
                        # Process and emit fire batch
                        self.emit_fire_update(data)
                    
                    # Mark task as done
                    self.data_queue.task_done()
                    
                except Empty:
                    # Timeout - continue loop
                    continue
                except Exception as e:
                    logger.error(f"Consumer error processing queue item: {e}")
                    
        except Exception as e:
            logger.error(f"Consumer thread error: {e}")
        finally:
            self.is_running = False
            logger.info("Consumer thread finished")
    
    def start(self):
        """Start consumer thread."""
        if not self.thread or not self.thread.is_alive():
            self.is_running = True  # Set running flag before starting thread
            self.thread = threading.Thread(target=self.run_consumer)
            self.thread.daemon = True
            self.thread.start()
    
    def stop(self):
        """Stop consumer thread."""
        self.is_running = False


# Initialize Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY

# Initialize SocketIO
socketio = SocketIO(
    app, 
    cors_allowed_origins=config.CORS_ORIGINS,
    ping_interval=config.WEBSOCKET_PING_INTERVAL,
    ping_timeout=config.WEBSOCKET_PING_TIMEOUT
)

# Initialize producer-consumer system
data_queue = Queue(maxsize=config.get_queue_size(config.DEFAULT_SPEED))
producer = FireDataProducer(data_queue, config.DATABASE_PATH)
consumer = FireDataConsumer(data_queue, socketio)


@app.route('/')
def index():
    """Main application page."""
    return render_template('index.html', 
                         config=config,
                         default_date_range=config.DEFAULT_DATE_RANGE)



@app.route('/tiles/<int:z>/<int:x>/<int:y>.png')
def serve_tile(z, x, y):
    """Serve map tiles from local storage."""
    try:
        tile_dir = os.path.join(config.TILE_DIRECTORY, str(z), str(x))
        filename = f'{y}.png'
        
        if os.path.exists(os.path.join(tile_dir, filename)):
            return send_from_directory(tile_dir, filename)
        else:
            logger.warning(f"Tile not found: {z}/{x}/{y}")
            return '', 404
            
    except Exception as e:
        logger.error(f"Error serving tile {z}/{x}/{y}: {e}")
        return '', 500


# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info(f"Client connected: {request.sid}")
    
    # Send initial configuration
    emit('config', {
        'zoom_levels': config.ZOOM_LEVELS,
        'default_zoom': config.DEFAULT_ZOOM,
        'map_center': config.MAP_CENTER,
        'bounding_box': config.BOUNDING_BOX,
        'playback_speeds': config.PLAYBACK_SPEEDS,
        'speed_labels': config.SPEED_LABELS,
        'default_speed': config.DEFAULT_SPEED,
        'default_date_range': config.DEFAULT_DATE_RANGE,
        'fade_duration_fn': 'exponential'
    })


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info(f"Client disconnected: {request.sid}")


@socketio.on('start_playback')
def handle_start_playback(data):
    """Handle playback start request."""
    try:
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        speed = data.get('speed', config.DEFAULT_SPEED)
        
        logger.info(f"Starting playback: {start_date} to {end_date} at {speed}")
        
        # Configure producer
        producer.set_date_range(start_date, end_date)
        producer.set_speed(speed)
        producer.is_paused = False  # Ensure producer is unpaused for new playback
        
        # Update queue size if needed
        new_queue_size = config.get_queue_size(speed)
        if data_queue.maxsize != new_queue_size:
            # Note: Can't resize existing queue, would need to recreate
            logger.info(f"Queue size should be {new_queue_size} for speed {speed}")
        
        # Start threads
        consumer.start()
        producer.start()
        
        emit('playback_started', {
            'status': 'success',
            'start_date': start_date,
            'end_date': end_date,
            'speed': speed
        })
        
    except Exception as e:
        logger.error(f"Error starting playback: {e}")
        emit('playback_error', {'error': str(e)})


@socketio.on('pause_playback')
def handle_pause_playback():
    """Handle playback pause request."""
    try:
        producer.pause()
        emit('playback_paused')
        logger.info("Playback paused")
    except Exception as e:
        logger.error(f"Error pausing playback: {e}")
        emit('playback_error', {'error': str(e)})


@socketio.on('resume_playback')
def handle_resume_playback():
    """Handle playback resume request."""
    try:
        producer.resume()
        emit('playback_resumed')
        logger.info("Playback resumed")
    except Exception as e:
        logger.error(f"Error resuming playback: {e}")
        emit('playback_error', {'error': str(e)})


@socketio.on('stop_playback')
def handle_stop_playback():
    """Handle playback stop request."""
    try:
        producer.stop()
        consumer.stop()
        
        # Clear queue
        while not data_queue.empty():
            try:
                data_queue.get_nowait()
            except:
                break
        
        emit('playback_stopped')
        logger.info("Playback stopped")
        
    except Exception as e:
        logger.error(f"Error stopping playback: {e}")
        emit('playback_error', {'error': str(e)})


@socketio.on('change_speed')
def handle_change_speed(data):
    """Handle speed change request."""
    try:
        new_speed = data.get('speed')
        
        if new_speed in config.PLAYBACK_SPEEDS:
            producer.set_speed(new_speed)
            emit('speed_changed', {'speed': new_speed})
            logger.info(f"Speed changed to {new_speed}")
        else:
            emit('playback_error', {'error': f'Invalid speed: {new_speed}'})
            
    except Exception as e:
        logger.error(f"Error changing speed: {e}")
        emit('playback_error', {'error': str(e)})


@socketio.on('get_statistics')
def handle_get_statistics():
    """Handle statistics request."""
    try:
        stats = producer.get_statistics()
        stats.update(consumer.fire_statistics)
        emit('statistics_update', stats)
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        emit('statistics_error', {'error': str(e)})


def check_database():
    """Check if database exists and is accessible."""
    if not os.path.exists(config.DATABASE_PATH):
        logger.error(f"Database not found: {config.DATABASE_PATH}")
        logger.error("Please run database_loader.py first to create the database")
        return False
    
    try:
        conn = sqlite3.connect(config.DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM fire_events")
        count = cursor.fetchone()[0]
        conn.close()
        logger.info(f"Database loaded with {count} fire events")
        return True
        
    except Exception as e:
        logger.error(f"Database error: {e}")
        return False


def main():
    """Main entry point."""
    logger.info("Starting Ukraine Fire Tracking System")
    
    # Check database
    if not check_database():
        return 1
    
    # Ensure directories exist
    config.ensure_directories()
    
    # Check for tiles
    tile_count = 0
    for zoom in config.ZOOM_LEVELS:
        zoom_dir = os.path.join(config.TILE_DIRECTORY, str(zoom))
        if os.path.exists(zoom_dir):
            for x_dir in os.listdir(zoom_dir):
                x_path = os.path.join(zoom_dir, x_dir)
                if os.path.isdir(x_path):
                    tile_count += len([f for f in os.listdir(x_path) if f.endswith('.png')])
    
    if tile_count == 0:
        logger.warning("No map tiles found. Run download_tiles.py to download tiles for offline use.")
    else:
        logger.info(f"Found {tile_count} map tiles")
    
    # Start Flask application
    logger.info(f"Starting server on {config.FLASK_HOST}:{config.FLASK_PORT}")
    
    try:
        socketio.run(
            app,
            host=config.FLASK_HOST,
            port=config.FLASK_PORT,
            debug=config.FLASK_DEBUG,
            allow_unsafe_werkzeug=True
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())