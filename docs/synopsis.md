# Ukraine Fire Tracking System - Project Synopsis

## Project Overview
A fully operational airgapped wildfire visualization platform that provides interactive historical analysis of satellite fire detection data from NASA FIRMS (Fire Information for Resource Management System). The system delivers real-time simulation of fire events across Ukraine and Western Russia with advanced playback controls, serving as a comprehensive training and planning tool for emergency response teams and policy analysis.

## Use Case: Emergency Response Training Platform
This simulator addresses critical public safety needs by providing:
- **Training Environment**: Emergency services can practice fire response coordination using historical data
- **Pattern Recognition**: Compressed playback reveals fire spread patterns invisible in real-time
- **Resource Planning**: Analyze historical patterns to optimize station locations and response protocols
- **Cross-Border Coordination**: Visualize fires crossing administrative boundaries for international response training

## Data Source & Processing
- **Provider**: NASA FIRMS (VIIRS and MODIS satellites)
- **Dataset Processed**: 302,830 fire detection events in operational database
- **Time Period**: 22 months of historical data (August 2023 - May 2025)
- **Geographic Coverage**: Ukraine and Western Russia (44°N-56°N, 22°E-50°E)
- **Database**: SQLite with optimized indexing and unified schema

## Key Requirements
- **Airgapped Operation**: Complete offline functionality after initial setup
- **Date Range Selection**: Two date pickers (default: today - 2 years to today)
- **Adjustable Playback**: 
  - Slowest: 6 hours of historical data per second
  - Fastest: 2 weeks of historical data per second
- **Real-time Visualization**: Dynamic updates via WebSocket without page refresh
- **Geographic Coverage**: 44°N-56°N, 22°E-50°E with user-adjustable zoom

## Technical Architecture

### Core Technologies
- **Backend**: Python with Flask and Flask-SocketIO running on port 5001
- **Frontend**: Leaflet.js with advanced interactive controls and WebSocket connections
- **Map Data**: 433 pre-downloaded OpenStreetMap tiles across zoom levels 6, 7, 8
- **Communication**: WebSocket for real-time bidirectional updates with statistics

### System Components

1. **Database Layer (SQLite)**
   - Unified schema normalizing VIIRS and MODIS data
   - 15 fields with intelligent defaults for missing values
   - Sequential ID assignment (1 to N)
   - UTC datetime conversion from date/time fields
   - Indexed by datetime and location for performance

2. **Map Tile Management**
   - 433 pre-downloaded OSM tiles across zoom levels 6, 7, 8
   - Custom zoom controls positioned bottom-right of interface
   - Smooth mouse drag panning navigation
   - Local tile serving via Flask for complete offline operation

3. **Data Processing Architecture**
   - **Producer Thread**: Simulates external data source
     - Reads from SQLite for selected date range
     - Thread-safe queue with backpressure
     - Dynamic batch sizing based on throughput
   - **Consumer Thread**: Processes queue and updates frontend
     - Cannot read incomplete batches
     - Emits via WebSocket to browser
     - Manages marker fade lifecycle

4. **Playback Engine**
   - User-selectable date range via date pickers
   - Speed range: 6 hours/second to 2 weeks/second
   - Speed changes apply on next batch
   - Dynamic queue depth optimization
   - Marker fade: X seconds visible, X seconds exponential fade
   - Pause mode: markers continue fading, no new additions

5. **Advanced User Interface**
   - Interactive Leaflet.js map with custom zoom controls
   - Sliding control panel (left side, visible by default) with intuitive spacing
   - Fire markers with confidence-based coloring and FRP-based sizing
   - Exponential fade animations with proper marker lifecycle management
   - Crossfade time indicator with smooth "Mmm YYYY" transitions
   - Real-time statistics dashboard with active fire counts
   - Mini fire activity chart showing historical patterns
   - Comprehensive playback controls with labeled speed slider
   - Date range selectors with smart defaults
   - About sidebar panel with detailed project information and usage guide

## Database Schema

```sql
CREATE TABLE fire_events (
    id INTEGER PRIMARY KEY,          -- Sequential from 1
    datetime_utc DATETIME NOT NULL,  -- UTC timestamp
    latitude REAL NOT NULL,          -- Decimal degrees
    longitude REAL NOT NULL,         -- Decimal degrees
    brightness REAL NOT NULL,        -- Brightness temperature (Kelvin)
    bright_t31 REAL NOT NULL,        -- 31 µm channel brightness
    frp REAL DEFAULT 0.0,           -- Fire Radiative Power (MW)
    confidence TEXT DEFAULT 'low',   -- low/medium/high
    scan REAL DEFAULT 1.0,           -- Scan pixel size
    track REAL DEFAULT 1.0,          -- Track pixel size
    satellite TEXT NOT NULL,         -- Satellite identifier
    instrument TEXT NOT NULL,        -- VIIRS or MODIS
    daynight TEXT DEFAULT 'U',       -- D(ay)/N(ight)/U(nknown)
    type INTEGER DEFAULT 0,          -- Detection type
    version TEXT DEFAULT '1.0'       -- Algorithm version
);
```

## Data Flow
1. **Initial Load**: ETL script processes JSON files into SQLite database
2. **Producer Thread**: Queries database in chronological order, batching by time window
3. **Queue**: Thread-safe buffer between producer and consumer
4. **Consumer Thread**: Dequeues events and emits via WebSocket
5. **Browser**: Receives events and updates map markers dynamically
6. **Playback Control**: User adjusts speed, affecting producer batch timing

## System Status
- **Status**: FULLY OPERATIONAL AND DEPLOYED
- **Repository**: Available at https://github.com/scott4ai/ukraine-fire-tracking
- **Components**: All systems integrated and tested
- **Performance**: Optimized for real-time playback with 302,830 fire events
- **Deployment**: Running on localhost:5001 with complete airgapped functionality
- **Recent Enhancements**: 
  - Added automatic simulation stop when reaching end of actual data
  - Enhanced producer-consumer thread state management

## File Structure
```
fire_tracker/
├── app.py                 # Flask app with producer-consumer threads
├── config.py             # Configuration (zoom, speeds, boundaries)
├── database_loader.py    # ETL script for JSON to SQLite
├── download_tiles.py     # Parameterized tile download utility
├── fire_data.db         # SQLite database (generated)
├── map_tiles/           # Downloaded map tiles
│   └── {zoom}/          # Configurable zoom level
├── templates/
│   └── index.html       # UI with playback controls
├── static/              # Static assets
├── data/                # Source JSON files
│   ├── fire_archive_J1V-C2_*.json
│   ├── fire_archive_M-C61_*.json
│   └── fire_archive_SV-C2_*.json
└── requirements.txt     # Python dependencies
```

## System Usage
1. **Start Application**: `python app.py`
2. **Access Interface**: Navigate to `http://localhost:5001`
3. **Select Date Range**: Use date pickers to choose analysis period
4. **Control Playback**: Adjust speed slider and use play/pause/stop controls
5. **Explore Data**: Navigate map, click markers for fire details, view statistics
6. **Training Mode**: Use for emergency response scenario training and analysis

## Technical Features Implemented
- ✅ Complete ETL processing with unified database schema
- ✅ Multi-threaded tile downloading with 433 tiles across 3 zoom levels
- ✅ Producer-consumer architecture with thread-safe queue management
- ✅ Advanced UI with sliding panels, crossfade animations, and activity charts
- ✅ Real-time fire visualization with exponential fade effects
- ✅ Comprehensive playback controls and statistics dashboard
- ✅ Full airgapped operation capability