#!/usr/bin/env python3
"""
Fast training version of violence classifier with simplified parameter search.
"""

import sqlite3
import numpy as np
import pickle
from datetime import datetime
from sklearn import svm
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
from sklearn.utils import resample
import warnings
warnings.filterwarnings('ignore')


def extract_features(rows):
    """Extract features from database rows."""
    features = []
    labels = []
    
    for row in rows:
        # Basic thermal features
        brightness = row[3] if row[3] else 0
        bright_t31 = row[4] if row[4] else 0
        frp = row[5] if row[5] else 0
        scan = row[6] if row[6] else 1.0
        track = row[7] if row[7] else 1.0
        
        # Confidence encoding
        confidence_map = {'low': 0.33, 'medium': 0.66, 'high': 1.0}
        confidence_score = confidence_map.get(row[8], 0.33)
        
        # Day/night encoding
        daynight_map = {'D': 1.0, 'N': 0.0, 'U': 0.5}
        daynight_score = daynight_map.get(row[9], 0.5)
        
        # Temporal features
        hour = int(row[17]) if row[17] else 12
        day_of_week = int(row[18]) if row[18] else 3
        month = int(row[19]) if row[19] else 6
        
        # Spatial grid features
        lat_grid = float(row[20]) if row[20] else 48.0
        lon_grid = float(row[21]) if row[21] else 35.0
        
        # Derived features
        thermal_intensity = brightness - bright_t31
        
        # Cyclical time encoding
        hour_sin = np.sin(2 * np.pi * hour / 24)
        hour_cos = np.cos(2 * np.pi * hour / 24)
        month_sin = np.sin(2 * np.pi * month / 12)
        month_cos = np.cos(2 * np.pi * month / 12)
        
        feature_vector = [
            brightness, bright_t31, frp, scan, track,
            confidence_score, daynight_score, thermal_intensity,
            hour_sin, hour_cos, month_sin, month_cos,
            lat_grid, lon_grid
        ]
        
        features.append(feature_vector)
        labels.append(row[11])  # is_violent_event
    
    return np.array(features), np.array(labels)


def main():
    print("="*60)
    print("FAST VIOLENCE CLASSIFIER TRAINING")
    print("="*60)
    
    # Load data
    print("Loading data...")
    conn = sqlite3.connect('fire_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM svm_training_data")
    rows = cursor.fetchall()
    conn.close()
    
    print(f"Loaded {len(rows)} samples")
    
    # Extract features
    print("Extracting features...")
    X, y = extract_features(rows)
    
    # Balance dataset (undersample)
    print("Balancing dataset...")
    X_violent = X[y == 1]
    X_non_violent = X[y == 0]
    y_violent = y[y == 1]
    y_non_violent = y[y == 0]
    
    n_samples = len(y_violent)
    X_non_violent_balanced = resample(X_non_violent, n_samples=n_samples, random_state=42)
    y_non_violent_balanced = resample(y_non_violent, n_samples=n_samples, random_state=42)
    
    X_balanced = np.vstack([X_violent, X_non_violent_balanced])
    y_balanced = np.hstack([y_violent, y_non_violent_balanced])
    
    print(f"Balanced: {np.sum(y_balanced == 1)} violent, {np.sum(y_balanced == 0)} non-violent")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X_balanced, y_balanced, test_size=0.2, random_state=42, stratify=y_balanced
    )
    
    # Scale features
    print("Scaling features...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train SVM with good default parameters
    print("Training SVM classifier...")
    model = svm.SVC(
        C=10, 
        gamma='scale', 
        kernel='rbf', 
        probability=True, 
        random_state=42
    )
    
    model.fit(X_train_scaled, y_train)
    
    # Evaluate
    print("\n" + "="*60)
    print("EVALUATION RESULTS")
    print("="*60)
    
    y_pred = model.predict(X_test_scaled)
    y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
    
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=['Non-violent', 'Violent']))
    
    print("\nConfusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print("              Predicted")
    print("              Non-V   Violent")
    print(f"Actual Non-V  {cm[0,0]:5d}   {cm[0,1]:5d}")
    print(f"       Violent {cm[1,0]:5d}   {cm[1,1]:5d}")
    
    roc_auc = roc_auc_score(y_test, y_pred_proba)
    print(f"\nROC AUC Score: {roc_auc:.4f}")
    
    accuracy = model.score(X_test_scaled, y_test)
    print(f"Accuracy: {accuracy:.4f}")
    
    # Save model
    print("\nSaving model...")
    feature_names = [
        'brightness', 'bright_t31', 'frp', 'scan', 'track',
        'confidence_score', 'daynight_score', 'thermal_intensity',
        'hour_sin', 'hour_cos', 'month_sin', 'month_cos',
        'lat_grid', 'lon_grid'
    ]
    
    model_data = {
        'model': model,
        'scaler': scaler,
        'feature_names': feature_names,
        'roc_auc': roc_auc,
        'accuracy': accuracy,
        'training_date': datetime.now().isoformat()
    }
    
    with open('violence_classifier_model.pkl', 'wb') as f:
        pickle.dump(model_data, f)
    
    print("Model saved to violence_classifier_model.pkl")
    print(f"Final ROC AUC: {roc_auc:.4f}")


if __name__ == "__main__":
    main()