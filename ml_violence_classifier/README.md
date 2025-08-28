# Violence Classification ML System

This directory contains the machine learning components for predicting violent events from fire detection data.

## Directory Structure

```
ml_violence_classifier/
├── README.md              # This file
├── models/                # Trained models and artifacts
│   └── violence_classifier_model.pkl  # Trained SVM model
├── scripts/               # Training and prediction scripts
│   ├── train_violence_classifier.py      # Full training with grid search
│   ├── train_violence_classifier_fast.py # Fast training with defaults
│   └── predict_violence.py               # Prediction script
└── data_analysis/         # Data analysis and matching tools
    ├── analyze_dataset_overlap.py        # Dataset overlap analysis
    ├── match_fire_viina_data.py          # Fire-VIINA matching algorithm
    └── query_examples.py                 # Database query examples
```

## Overview

The system uses an SVM classifier trained on ground truth data created by matching NASA FIRMS fire detections with VIINA violent incident reports. The model predicts the probability (0.0-1.0) that a fire detection represents a violent event.

## Quick Start

### 1. Training a Model

```bash
# Fast training (recommended for testing)
cd ml_violence_classifier/scripts
python3 train_violence_classifier_fast.py

# Full training with hyperparameter optimization (slower)
python3 train_violence_classifier.py
```

### 2. Making Predictions

**Note**: Run prediction commands from the `ml_violence_classifier/scripts/` directory.

```bash
# Navigate to scripts directory
cd ml_violence_classifier/scripts

# Test with sample data from database
python3 predict_violence.py --test

# Show example input format
python3 predict_violence.py --example

# Predict from JSON file
python3 predict_violence.py fire_data.json

# Predict from stdin
echo '{"datetime_utc": "2024-03-15T14:30:00", "latitude": 49.5, "longitude": 36.3, "brightness": 320.5, "bright_t31": 290.2, "frp": 15.3, "confidence": "high", "scan": 0.8, "track": 0.9, "daynight": "D"}' | python3 predict_violence.py -
```

## Model Performance

Current model (SVM with RBF kernel):
- **ROC AUC**: 0.8445
- **Accuracy**: 77.05%
- **Recall (violent events)**: 86%
- **Precision (violent events)**: 73%

Training data:
- Total samples: 302,830 fire events
- Violent events: 22,343 (matched with VIINA incidents)
- Non-violent events: 280,487 (unmatched fires)

## Features Used

The model uses 14 features extracted from fire detection data:

**Thermal Features:**
- brightness: Fire brightness temperature (Kelvin)
- bright_t31: Channel T31 brightness temperature
- frp: Fire Radiative Power (MW)
- thermal_intensity: Derived temperature difference

**Detection Quality:**
- confidence_score: Fire confidence (low/medium/high → 0.33/0.66/1.0)
- scan: Scan pixel size
- track: Track pixel size
- daynight_score: Day/night flag (D/N/U → 1.0/0.0/0.5)

**Temporal Features (cyclical encoding):**
- hour_sin, hour_cos: Hour of day
- month_sin, month_cos: Month of year

**Spatial Features:**
- lat_grid, lon_grid: Spatial grid coordinates (0.1° resolution)

## Ground Truth Creation

The ground truth dataset was created by:

1. **Spatiotemporal Matching**: Fire events matched to VIINA incidents within 5km and ±12 hours
2. **Match Confidence**: High/medium/low based on distance and time proximity
3. **Data Balancing**: Undersampled non-violent events to match violent event count

## Usage in Applications

The prediction script returns a probability between 0.0 and 1.0:
- **0.0-0.3**: Low probability of violence
- **0.3-0.7**: Medium probability 
- **0.7-1.0**: High probability of violence

Integrate into fire tracking systems to flag potentially conflict-related thermal detections for further investigation.

## Dependencies

- scikit-learn >= 1.7.1
- numpy >= 2.3.2
- sqlite3 (built-in)
- pickle (built-in)