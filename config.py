"""
Configuration file for Ukraine Fire Tracking System.
Contains all system parameters and settings.
"""

from datetime import datetime, timedelta
import os

# Map Configuration
ZOOM_LEVELS = [6, 7, 8]  # Download all three zoom levels
DEFAULT_ZOOM = 7  # Default zoom level for initial display (medium zoom)

# Geographic boundaries for Ukraine and Western Russia
BOUNDING_BOX = {
    'north': 56.0,  # Northern Russia
    'south': 44.0,  # Southern Ukraine
    'west': 22.0,   # Western Ukraine
    'east': 50.0    # Western Russia (includes Moscow)
}

# Center point for initial map view (Ukraine center)
MAP_CENTER = {
    'lat': 48.3794,
    'lon': 31.1656
}

# Playback Speed Configuration
# Speed in hours of historical data per second of playback
PLAYBACK_SPEEDS = {
    'slowest': 6,        # 6 hours per second (0.25 days/sec)
    'slow': 24,          # 1 day per second
    'normal': 72,        # 3 days per second
    'fast': 168,         # 1 week per second
    'fastest': 336       # 2 weeks per second (14 days/sec)
}

DEFAULT_SPEED = 'slow'  # Default playback speed (1 day/sec)

# Calculate speed multipliers for UI
SPEED_LABELS = {
    'slowest': '6 hrs/sec',
    'slow': '1 day/sec',
    'normal': '3 days/sec',
    'fast': '1 week/sec',
    'fastest': '2 weeks/sec'
}

# Database Configuration
DATABASE_PATH = 'fire_data.db'

# Date Range Configuration
def get_default_date_range():
    """Get default date range (last 2 years from today)."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730)  # 2 years
    return {
        'start': start_date.strftime('%Y-%m-%d'),
        'end': end_date.strftime('%Y-%m-%d')
    }

DEFAULT_DATE_RANGE = get_default_date_range()

# Queue Configuration (sizes for producer-consumer pattern)
# Dynamic sizing based on playback speed
def get_queue_size(speed_key):
    """Calculate queue size based on playback speed."""
    speed_hours = PLAYBACK_SPEEDS.get(speed_key, PLAYBACK_SPEEDS['normal'])
    
    # Higher speeds need larger queues
    if speed_hours <= 24:  # Slow speeds
        return 100
    elif speed_hours <= 72:  # Normal speed
        return 500
    elif speed_hours <= 168:  # Fast speed
        return 1000
    else:  # Fastest speed
        return 2000

# Batch sizes for database queries
def get_batch_size(speed_key):
    """Calculate batch size for database queries based on speed."""
    speed_hours = PLAYBACK_SPEEDS.get(speed_key, PLAYBACK_SPEEDS['normal'])
    
    # Approximate events per batch
    # Assuming ~100-200 fires per day average
    days_per_second = speed_hours / 24
    events_per_second = days_per_second * 150  # Average 150 fires/day
    
    # Batch every 0.1 seconds for smooth playback
    batch_size = int(events_per_second * 0.1)
    
    # Minimum batch size of 10, maximum of 1000
    return max(10, min(1000, batch_size))

# Marker Animation Configuration
MARKER_FADE_TYPE = 'exponential'  # Type of fade animation

def get_fade_duration(speed_key):
    """
    Calculate marker fade duration based on playback speed.
    Markers visible for X seconds, then fade for X seconds.
    X = playback interval
    """
    speed_hours = PLAYBACK_SPEEDS.get(speed_key, PLAYBACK_SPEEDS['normal'])
    
    # Calculate appropriate fade duration
    # Slower speeds = longer fade, faster speeds = shorter fade
    if speed_hours <= 24:  # Slow speeds
        return 2.0  # 2 seconds visible, 2 seconds fading
    elif speed_hours <= 72:  # Normal speed
        return 1.0  # 1 second visible, 1 second fading
    elif speed_hours <= 168:  # Fast speed
        return 0.5  # 0.5 seconds visible, 0.5 seconds fading
    else:  # Fastest speed
        return 0.25  # 0.25 seconds visible, 0.25 seconds fading

# Exponential fade function parameters
FADE_EXPONENT = 2.0  # Controls how quickly opacity decreases (higher = faster at end)

# Tile Server Configuration
TILE_SERVER_PORT = 5001
TILE_DIRECTORY = 'map_tiles'
TILE_URL_PATTERN = '/tiles/{z}/{x}/{y}.png'

# OSM Tile Server (for downloading)
OSM_TILE_SERVERS = [
    'https://a.tile.openstreetmap.org',
    'https://b.tile.openstreetmap.org',
    'https://c.tile.openstreetmap.org'
]

# Rate limiting for tile downloads
TILE_DOWNLOAD_DELAY = 0.5  # Seconds between tile downloads
MAX_DOWNLOAD_THREADS = 2  # Maximum concurrent downloads

# WebSocket Configuration
WEBSOCKET_PING_INTERVAL = 25  # Ping interval in seconds
WEBSOCKET_PING_TIMEOUT = 60  # Ping timeout in seconds

# UI Configuration
UI_UPDATE_INTERVAL = 100  # Milliseconds between UI updates
STATISTICS_UPDATE_INTERVAL = 1000  # Milliseconds between statistics updates

# About Panel Content
ABOUT_TITLE = "Ukraine Fire Tracking System"
ABOUT_SUBTITLE = "Historical Wildfire Pattern Analysis"

ABOUT_DESCRIPTION = """
This system visualizes historical wildfire data from NASA FIRMS satellites
(VIIRS and MODIS) for the Ukraine and Western Russia region.

The platform serves as a training and analysis tool for emergency response
teams, allowing them to study fire patterns and practice coordination.
"""

ABOUT_USAGE = """
<h4>How to Use:</h4>
<ol>
  <li><strong>Select Date Range:</strong> Use the date pickers to choose your analysis period</li>
  <li><strong>Adjust Speed:</strong> Use the slider to control playback speed (6 hrs/sec to 2 weeks/sec)</li>
  <li><strong>Control Playback:</strong> Use Play/Pause/Stop buttons to control simulation</li>
  <li><strong>Navigate Map:</strong> Click and drag to pan, use zoom controls to adjust view</li>
  <li><strong>View Fire Details:</strong> Click on fire markers for detailed information</li>
</ol>

<h4>Marker Colors:</h4>
<ul>
  <li><span style="color: yellow">●</span> Low confidence</li>
  <li><span style="color: orange">●</span> Medium confidence</li>
  <li><span style="color: red">●</span> High confidence</li>
</ul>

<h4>Marker Size:</h4>
Larger markers indicate higher Fire Radiative Power (FRP)
"""

ABOUT_CREDITS = """
<h4>Data Source:</h4>
NASA FIRMS (Fire Information for Resource Management System)<br>
VIIRS and MODIS satellite instruments

<h4>Time Period:</h4>
Historical data from August 2023 to May 2025
"""

# Performance Configuration
MAX_CONCURRENT_MARKERS = 5000  # Maximum markers visible at once
MARKER_CLEANUP_INTERVAL = 5000  # Milliseconds between marker cleanup cycles

# Logging Configuration
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR
LOG_FILE = 'fire_tracker.log'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Flask Configuration
FLASK_DEBUG = False  # Set to True for development
FLASK_HOST = '0.0.0.0'  # Listen on all interfaces
FLASK_PORT = 5001
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# CORS Configuration (if needed for development)
CORS_ORIGINS = '*'  # Restrict in production

# File paths
TEMPLATE_DIR = 'templates'
STATIC_DIR = 'static'

# Create necessary directories
def ensure_directories():
    """Ensure all required directories exist."""
    directories = [
        TILE_DIRECTORY,
        TEMPLATE_DIR,
        STATIC_DIR,
        os.path.join(STATIC_DIR, 'css'),
        os.path.join(STATIC_DIR, 'js')
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    
    # Create tile subdirectories for each zoom level
    for zoom in ZOOM_LEVELS:
        zoom_dir = os.path.join(TILE_DIRECTORY, str(zoom))
        os.makedirs(zoom_dir, exist_ok=True)