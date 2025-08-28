#!/usr/bin/env python3
"""
Violence prediction script for new fire detection events.
Uses trained SVM classifier to predict probability of violent event.
"""

import pickle
import numpy as np
from datetime import datetime
import json
import sys


def extract_single_features(fire_data):
    """
    Extract features from a single fire detection event.
    
    Args:
        fire_data: Dictionary with fire event data
        
    Returns:
        Numpy array of features
    """
    # Basic thermal features
    brightness = fire_data.get('brightness', 0)
    bright_t31 = fire_data.get('bright_t31', 0)
    frp = fire_data.get('frp', 0)
    scan = fire_data.get('scan', 1.0)
    track = fire_data.get('track', 1.0)
    
    # Confidence encoding
    confidence_map = {'low': 0.33, 'medium': 0.66, 'high': 1.0}
    confidence_score = confidence_map.get(fire_data.get('confidence', 'low'), 0.33)
    
    # Day/night encoding
    daynight_map = {'D': 1.0, 'N': 0.0, 'U': 0.5}
    daynight_score = daynight_map.get(fire_data.get('daynight', 'U'), 0.5)
    
    # Parse datetime for temporal features
    dt_str = fire_data.get('datetime_utc', datetime.now().isoformat())
    try:
        if 'T' in dt_str:
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        else:
            dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
    except:
        dt = datetime.now()
    
    hour = dt.hour
    day_of_week = dt.weekday()
    month = dt.month
    
    # Spatial features
    lat_grid = round(fire_data.get('latitude', 48.0), 1)
    lon_grid = round(fire_data.get('longitude', 35.0), 1)
    
    # Derived features
    thermal_intensity = brightness - bright_t31
    
    # Cyclical time encoding
    hour_sin = np.sin(2 * np.pi * hour / 24)
    hour_cos = np.cos(2 * np.pi * hour / 24)
    
    month_sin = np.sin(2 * np.pi * month / 12)
    month_cos = np.cos(2 * np.pi * month / 12)
    
    # Compile feature vector (same order as training - 14 features)
    features = np.array([
        brightness,
        bright_t31,
        frp,
        scan,
        track,
        confidence_score,
        daynight_score,
        thermal_intensity,
        hour_sin,
        hour_cos,
        month_sin,
        month_cos,
        lat_grid,
        lon_grid
    ]).reshape(1, -1)
    
    return features


def load_model(model_path='../models/violence_classifier_model.pkl'):
    """
    Load the trained model and scaler.
    
    Returns:
        Dictionary with model components
    """
    try:
        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)
        return model_data
    except FileNotFoundError:
        raise FileNotFoundError(f"Model file not found: {model_path}")
    except Exception as e:
        raise Exception(f"Error loading model: {e}")


def predict_violence_probability(fire_data, model_path='../models/violence_classifier_model.pkl', verbose=False):
    """
    Predict violence probability for a single fire event.
    
    Args:
        fire_data: Dictionary with fire event data
        model_path: Path to trained model file
        verbose: Print detailed information
        
    Returns:
        Float between 0.0 and 1.0 indicating violence probability
    """
    # Load model
    if verbose:
        print("Loading trained model...")
    model_data = load_model(model_path)
    
    model = model_data['model']
    scaler = model_data['scaler']
    
    if verbose:
        print(f"Model trained: {model_data['training_date']}")
        print(f"Model ROC AUC: {model_data['roc_auc']:.4f}")
    
    # Extract features
    if verbose:
        print("Extracting features...")
    features = extract_single_features(fire_data)
    
    # Scale features
    features_scaled = scaler.transform(features)
    
    # Get prediction probability
    violence_probability = model.predict_proba(features_scaled)[0, 1]
    
    if verbose:
        print(f"Violence probability: {violence_probability:.4f}")
        
        # Show feature values
        feature_names = model_data['feature_names']
        print("\nFeature values:")
        for name, value in zip(feature_names, features[0]):
            print(f"  {name:20s}: {value:.4f}")
    
    return float(violence_probability)


def predict_batch(fire_events, model_path='../models/violence_classifier_model.pkl'):
    """
    Predict violence probabilities for multiple fire events.
    
    Args:
        fire_events: List of fire event dictionaries
        model_path: Path to trained model file
        
    Returns:
        List of probabilities
    """
    model_data = load_model(model_path)
    model = model_data['model']
    scaler = model_data['scaler']
    
    # Extract features for all events
    all_features = []
    for fire_data in fire_events:
        features = extract_single_features(fire_data)
        all_features.append(features[0])
    
    # Scale features
    features_matrix = np.array(all_features)
    features_scaled = scaler.transform(features_matrix)
    
    # Get predictions
    probabilities = model.predict_proba(features_scaled)[:, 1]
    
    return probabilities.tolist()


def main():
    """
    Command line interface for predictions.
    """
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python predict_violence.py <fire_data.json>")
        print("  python predict_violence.py --example")
        print("  python predict_violence.py --test")
        return
    
    if sys.argv[1] == '--example':
        # Show example fire data format
        example = {
            "datetime_utc": "2024-03-15T14:30:00",
            "latitude": 49.5,
            "longitude": 36.3,
            "brightness": 320.5,
            "bright_t31": 290.2,
            "frp": 15.3,
            "confidence": "high",
            "scan": 0.8,
            "track": 0.9,
            "daynight": "D"
        }
        
        print("Example fire data format:")
        print(json.dumps(example, indent=2))
        print("\nTry: echo '{}' | python predict_violence.py -".format(json.dumps(example)))
        return
    
    if sys.argv[1] == '--test':
        # Test with sample data from database
        import sqlite3
        conn = sqlite3.connect('../../fire_data.db')
        cursor = conn.cursor()
        
        # Get a few sample fire events (some violent, some not)
        cursor.execute("""
            SELECT datetime_utc, latitude, longitude, brightness, bright_t31, frp, 
                   fire_confidence, scan, track, daynight, is_violent_event
            FROM svm_training_data 
            ORDER BY RANDOM() 
            LIMIT 5
        """)
        
        samples = cursor.fetchall()
        conn.close()
        
        print("Testing with sample data from database:")
        print("="*60)
        
        for i, row in enumerate(samples, 1):
            fire_data = {
                'datetime_utc': row[0],
                'latitude': row[1],
                'longitude': row[2],
                'brightness': row[3],
                'bright_t31': row[4],
                'frp': row[5],
                'confidence': row[6],
                'scan': row[7],
                'track': row[8],
                'daynight': row[9]
            }
            
            actual_violent = bool(row[10])
            predicted_prob = predict_violence_probability(fire_data)
            
            print(f"\nSample {i}:")
            print(f"  Actual: {'Violent' if actual_violent else 'Non-violent'}")
            print(f"  Predicted violence probability: {predicted_prob:.4f}")
            print(f"  Location: ({row[1]:.2f}, {row[2]:.2f})")
            print(f"  Time: {row[0]}")
        
        return
    
    # Load fire data from file or stdin
    if sys.argv[1] == '-':
        # Read from stdin
        fire_data = json.loads(sys.stdin.read())
    else:
        # Read from file
        with open(sys.argv[1], 'r') as f:
            fire_data = json.load(f)
    
    # Handle single event or list of events
    if isinstance(fire_data, list):
        probabilities = predict_batch(fire_data)
        for i, prob in enumerate(probabilities):
            print(f"Event {i+1} violence probability: {prob:.4f}")
    else:
        prob = predict_violence_probability(fire_data, verbose=True)
        print(f"\nFinal prediction: {prob:.4f}")


if __name__ == "__main__":
    main()