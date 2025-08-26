# Ukraine Fire Tracking System

An airgapped wildfire visualization and analysis platform that replays historical satellite fire detection data from NASA FIRMS. Serves as a training and planning tool for emergency response teams and policy makers.

## Features

- **Real-time Simulation**: Replay 22 months of historical fire data in 10 minutes to 48 seconds
- **Interactive Mapping**: User-adjustable zoom levels with mouse drag navigation  
- **Flexible Playback**: Speed range from 6 hours/second to 2 weeks/second
- **Date Range Selection**: Pick any time period within the dataset
- **Marker Animation**: Exponential fade effects with confidence-based coloring
- **Offline Operation**: Complete airgapped functionality after initial setup
- **Emergency Training**: Designed for fire response coordination practice

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Load Fire Data
```bash
# Process JSON fire data into SQLite database
python database_loader.py
```

### 3. Download Map Tiles (Requires Internet)
```bash
# Download offline map tiles for zoom levels 6, 7, 8
python download_tiles.py
```

### 4. Run Application
```bash
# Start the web server
python app.py
```

Navigate to `http://localhost:5000` in your browser.

## Data Source

**NASA FIRMS** (Fire Information for Resource Management System)
- VIIRS and MODIS satellite instruments
- Sample dataset: 302,830 fire detections 
- Full dataset: ~3,000,000 records
- Coverage: Ukraine and Western Russia (44°N-56°N, 22°E-50°E)
- Time period: August 2023 - May 2025

## System Architecture

### Producer-Consumer Pattern
- **Producer Thread**: Reads from SQLite database in chronological batches
- **Consumer Thread**: Processes queue and emits to browser via WebSocket
- **Thread-Safe Queue**: Handles backpressure and dynamic sizing

### Database Schema
```sql
CREATE TABLE fire_events (
    id INTEGER PRIMARY KEY,
    datetime_utc DATETIME NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    brightness REAL NOT NULL,
    bright_t31 REAL NOT NULL,
    frp REAL DEFAULT 0.0,           -- Fire Radiative Power (MW)
    confidence TEXT DEFAULT 'low',  -- low/medium/high
    scan REAL DEFAULT 1.0,
    track REAL DEFAULT 1.0,
    satellite TEXT NOT NULL,
    instrument TEXT NOT NULL,
    daynight TEXT DEFAULT 'U',      -- D(ay)/N(ight)/U(nknown)
    type INTEGER DEFAULT 0,
    version TEXT DEFAULT '1.0'
);
```

## User Interface

### Control Panel
- **Date Pickers**: Start date (default: today-2yrs), End date (default: today)
- **Speed Slider**: 6 hrs/sec to 2 weeks/sec
- **Playback Controls**: Play/Pause/Stop with status display
- **Statistics**: Active fires, total processed, current status

### Map Features  
- **Zoom Levels**: User-adjustable 6-8
- **Navigation**: Mouse drag panning
- **Fire Markers**: 
  - Colors: Yellow (low), Orange (medium), Red (high confidence)
  - Size: Based on Fire Radiative Power (FRP)
  - Animation: Exponential fade over 2X playback interval
- **Time Overlay**: Shows "Mmm YYYY" format during playback

### About Sidebar
- Application synopsis and usage instructions
- Data source information and credits
- Keyboard shortcut: ESC to close

## Configuration

Edit `config.py` to customize:
- Geographic boundaries
- Playback speeds  
- Queue sizes
- Fade animations
- UI text content

## File Structure

```
fire_tracker/
├── app.py                 # Flask app with producer-consumer threads
├── config.py             # System configuration parameters
├── database_loader.py    # ETL script for JSON to SQLite
├── download_tiles.py     # Tile download utility
├── requirements.txt      # Python dependencies
├── fire_data.db         # SQLite database (generated)
├── map_tiles/           # Downloaded map tiles
│   ├── 6/              # Zoom level 6 tiles
│   ├── 7/              # Zoom level 7 tiles  
│   └── 8/              # Zoom level 8 tiles
├── templates/
│   └── index.html       # Main UI with controls
├── data/                # Source JSON files
│   ├── fire_archive_J1V-C2_*.json
│   ├── fire_archive_M-C61_*.json
│   └── fire_archive_SV-C2_*.json
└── docs/               # Documentation
    ├── synopsis.md
    └── plan.md
```

## Troubleshooting

### Database Issues
- Ensure `data/` directory contains JSON files before running `database_loader.py`
- Check database exists: `ls -la fire_data.db`
- Verify records: `sqlite3 fire_data.db "SELECT COUNT(*) FROM fire_events;"`

### Map Tiles Not Loading
- Run `download_tiles.py` with internet connection
- Check tiles exist: `ls -la map_tiles/8/`
- Verify tile server responds: `curl http://localhost:5000/tiles/8/128/87.png`

### Performance Issues
- Reduce playback speed if browser lags
- Check browser console for JavaScript errors
- Monitor system resources during high-speed playback

### WebSocket Connection Problems
- Check firewall allows port 5000
- Try different browser
- Check server logs for connection errors

## Development

### Adding New Features
1. Update configuration in `config.py`
2. Modify backend logic in `app.py`  
3. Update frontend in `templates/index.html`
4. Test with sample data before full dataset

### Performance Tuning
- Adjust batch sizes in `config.get_batch_size()`
- Modify queue sizes in `config.get_queue_size()`
- Optimize database queries for specific date ranges
- Profile marker rendering at high speeds

## Use Cases

**Emergency Response Training**
- Practice fire response coordination using historical patterns
- Identify high-risk periods and regions for resource planning
- Train dispatchers on multi-fire event management
- Simulate cross-border coordination scenarios

**Research & Analysis**  
- Study fire spread patterns over time
- Correlate with weather and seasonal data
- Analyze satellite detection effectiveness
- Support policy discussions with historical evidence

## License

Educational and research use. Fire data courtesy of NASA FIRMS.

## Credits

**Data Source**: NASA FIRMS (Fire Information for Resource Management System)  
**Map Data**: © OpenStreetMap contributors  
**Satellites**: VIIRS (JPSS-1, Suomi NPP) and MODIS (Terra, Aqua)