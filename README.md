# Ukraine Fire Tracking System

An airgapped wildfire visualization and analysis platform that replays historical satellite fire detection data from NASA FIRMS. Serves as a training and planning tool for emergency response teams and policy makers.

## Features

- **Real-time Simulation**: Replay 22 months of historical fire data in 10 minutes to 48 seconds
- **Interactive Mapping**: User-adjustable zoom levels with mouse drag navigation  
- **Flexible Playback**: Speed range from 6 hours/second to 2 weeks/second
- **Date Range Selection**: Pick any time period within the dataset
- **Marker Animation**: Exponential fade effects with confidence-based coloring
- **Violence Detection**: Purple markers highlight conflict-related fires using ML classification
- **Ground Truth Analysis**: 22,343 fire events matched with VIINA violent incident reports
- **SVM Classifier**: Machine learning model predicts violence probability from thermal signatures
- **Offline Operation**: Complete airgapped functionality after initial setup
- **Emergency Training**: Designed for fire response coordination practice

## Installation & Setup

### 1. Clone Repository
```bash
git clone https://github.com/scott4ai/ukraine-fire-tracking.git
cd ukraine-fire-tracking
```

### 2. Set Up Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Load Fire Data
```bash
# Process JSON fire data into SQLite database
python database_loader.py

# Import VIINA incident data (optional - for violence detection)
python import_viina_data.py

# Create ground truth matches between fires and violent incidents (optional)
python ml_violence_classifier/data_analysis/match_fire_viina_data.py
```

### 5. Download Map Tiles (Requires Internet)
```bash
# Download offline map tiles for zoom levels 6, 7, 8
python download_tiles.py
```

### 6. Run Application
```bash
# Start the web server
python app.py
```

Navigate to `http://localhost:5001` in your browser.

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
  - Regular fires: Yellow (low), Orange (medium), Orange-red (high confidence)
  - Violent events: Light purple (low), Medium purple (medium), Deep purple (high confidence)
  - Size: Based on Fire Radiative Power (FRP)
  - Animation: Exponential fade over 2X playback interval
  - Popup Info: Thermal data, location, event type (for violent events)
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
ukraine-fire-tracking/
├── app.py                          # Flask app with producer-consumer threads
├── config.py                       # System configuration parameters
├── database_loader.py              # ETL script for JSON to SQLite
├── download_tiles.py               # Tile download utility
├── import_viina_data.py            # VIINA incident data importer
├── create_viina_table.sql          # Database schema for incidents
├── optimize_data_structures.sql    # Database optimization
├── requirements.txt                # Python dependencies
├── fire_data.db                   # SQLite database (generated)
├── ml_violence_classifier/        # Machine learning system
│   ├── scripts/                   # Training and prediction
│   │   ├── train_violence_classifier.py
│   │   ├── train_violence_classifier_fast.py
│   │   └── predict_violence.py
│   ├── models/                    # Trained ML models
│   │   └── violence_classifier_model.pkl
│   ├── data_analysis/             # Analysis tools
│   │   ├── analyze_dataset_overlap.py
│   │   ├── match_fire_viina_data.py
│   │   └── query_examples.py
│   ├── README.md                  # ML system documentation
│   └── requirements.txt           # ML dependencies
├── viina_data/                    # VIINA incident CSV files
│   └── viina_incidents_*.csv
├── map_tiles/                     # Downloaded map tiles
│   ├── 6/, 7/, 8/                # Zoom level tiles
├── templates/
│   └── index.html                 # Main UI with controls
├── data/                          # Source JSON files
│   ├── fire_archive_*.json
└── docs/                         # Documentation
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

## Violence Classification System

The system includes an advanced ML pipeline for identifying conflict-related fires:

### Ground Truth Dataset
- **22,343 matched events**: Fire detections correlated with VIINA violent incident reports
- **Spatiotemporal matching**: 5km distance, ±12 hour time window
- **Match confidence levels**: High/medium/low based on proximity

### SVM Classifier
- **ROC AUC**: 0.8445 (good discriminative ability)
- **Accuracy**: 77.05%
- **Features**: 14 thermal, temporal, and spatial characteristics
- **Training data**: 302,830 samples (balanced violent/non-violent)

### Usage
```bash
# Train the classifier
cd ml_violence_classifier/scripts
python3 train_violence_classifier_fast.py

# Predict violence probability for new fire events
python3 predict_violence.py --test
echo '{"latitude": 49.5, "longitude": 36.3, "brightness": 320.5, ...}' | python3 predict_violence.py -
```

See `ml_violence_classifier/README.md` for detailed documentation.

## Use Cases

**Emergency Response Training**
- Practice fire response coordination using historical patterns
- Distinguish between natural fires and conflict-related incidents
- Identify high-risk periods and regions for resource planning
- Train dispatchers on multi-fire event management
- Simulate cross-border coordination scenarios

**Research & Analysis**  
- Study fire spread patterns over time
- Analyze correlation between thermal signatures and violent events
- Correlate with weather and seasonal data
- Analyze satellite detection effectiveness
- Support policy discussions with historical evidence

**Intelligence & Security**
- Automated screening of fire detections for potential conflict indicators
- Pattern analysis of violent event locations and timing
- Ground truth validation for conflict monitoring systems

## License

Educational and research use. Fire data courtesy of NASA FIRMS.

## Credits

**Data Source**: NASA FIRMS (Fire Information for Resource Management System)  
**Map Data**: © OpenStreetMap contributors  
**Satellites**: VIIRS (JPSS-1, Suomi NPP) and MODIS (Terra, Aqua)