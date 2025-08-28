#!/usr/bin/env python3
"""
Train SVM classifier to predict violent events from fire detection data.
Uses ground truth data from matched fire-VIINA incidents.
"""

import sqlite3
import numpy as np
import pickle
from datetime import datetime
from sklearn import svm
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, roc_curve
from sklearn.utils import resample
import warnings
warnings.filterwarnings('ignore')


def extract_features(rows):
    """
    Extract and engineer features from database rows.
    """
    features = []
    labels = []
    
    for row in rows:
        # Basic thermal features
        brightness = row[3] if row[3] else 0
        bright_t31 = row[4] if row[4] else 0
        frp = row[5] if row[5] else 0
        scan = row[6] if row[6] else 1.0
        track = row[7] if row[7] else 1.0
        
        # Confidence encoding (categorical to numeric)
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
        thermal_intensity = brightness - bright_t31  # Temperature difference
        
        # Time-based features (sine/cosine encoding for cyclical nature)
        hour_sin = np.sin(2 * np.pi * hour / 24)
        hour_cos = np.cos(2 * np.pi * hour / 24)
        
        month_sin = np.sin(2 * np.pi * month / 12)
        month_cos = np.cos(2 * np.pi * month / 12)
        
        dow_sin = np.sin(2 * np.pi * day_of_week / 7)
        dow_cos = np.cos(2 * np.pi * day_of_week / 7)
        
        # Compile feature vector
        feature_vector = [
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
            dow_sin,
            dow_cos,
            lat_grid,
            lon_grid
        ]
        
        features.append(feature_vector)
        labels.append(row[11])  # is_violent_event
    
    return np.array(features), np.array(labels)


def balance_dataset(X, y, method='undersample'):
    """
    Balance the dataset using undersampling or oversampling.
    """
    X_violent = X[y == 1]
    X_non_violent = X[y == 0]
    y_violent = y[y == 1]
    y_non_violent = y[y == 0]
    
    print(f"Original distribution: {len(y_violent)} violent, {len(y_non_violent)} non-violent")
    
    if method == 'undersample':
        # Undersample majority class
        n_samples = len(y_violent)
        X_non_violent_balanced = resample(X_non_violent, n_samples=n_samples, random_state=42)
        y_non_violent_balanced = resample(y_non_violent, n_samples=n_samples, random_state=42)
        
        X_balanced = np.vstack([X_violent, X_non_violent_balanced])
        y_balanced = np.hstack([y_violent, y_non_violent_balanced])
        
    else:  # oversample
        # Oversample minority class
        n_samples = len(y_non_violent)
        X_violent_balanced = resample(X_violent, n_samples=n_samples, random_state=42)
        y_violent_balanced = resample(y_violent, n_samples=n_samples, random_state=42)
        
        X_balanced = np.vstack([X_violent_balanced, X_non_violent])
        y_balanced = np.hstack([y_violent_balanced, y_non_violent])
    
    print(f"Balanced distribution: {np.sum(y_balanced == 1)} violent, {np.sum(y_balanced == 0)} non-violent")
    
    # Shuffle the balanced dataset
    indices = np.arange(len(X_balanced))
    np.random.shuffle(indices)
    
    return X_balanced[indices], y_balanced[indices]


def train_svm_classifier():
    """
    Main training function.
    """
    print("="*60)
    print("TRAINING VIOLENCE DETECTION CLASSIFIER")
    print("="*60)
    
    # Connect to database
    conn = sqlite3.connect('../../fire_data.db')
    cursor = conn.cursor()
    
    # Load training data
    print("\nLoading training data...")
    cursor.execute("SELECT * FROM svm_training_data")
    rows = cursor.fetchall()
    conn.close()
    
    print(f"Loaded {len(rows)} total samples")
    
    # Extract features
    print("\nExtracting features...")
    X, y = extract_features(rows)
    
    # Balance dataset
    print("\nBalancing dataset...")
    X_balanced, y_balanced = balance_dataset(X, y, method='undersample')
    
    # Split data
    print("\nSplitting data (80% train, 20% test)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X_balanced, y_balanced, test_size=0.2, random_state=42, stratify=y_balanced
    )
    
    # Scale features
    print("\nScaling features...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Grid search for best parameters
    print("\nPerforming grid search for optimal parameters...")
    param_grid = {
        'C': [0.1, 1, 10, 100],
        'gamma': ['scale', 'auto', 0.001, 0.01, 0.1],
        'kernel': ['rbf', 'poly', 'sigmoid'],
        'probability': [True]
    }
    
    svm_model = svm.SVC(random_state=42)
    grid_search = GridSearchCV(
        svm_model, 
        param_grid, 
        cv=5, 
        scoring='roc_auc',
        n_jobs=-1,
        verbose=1
    )
    
    grid_search.fit(X_train_scaled, y_train)
    
    print(f"\nBest parameters: {grid_search.best_params_}")
    print(f"Best cross-validation score: {grid_search.best_score_:.4f}")
    
    # Use best model
    best_model = grid_search.best_estimator_
    
    # Evaluate on test set
    print("\n" + "="*60)
    print("MODEL EVALUATION")
    print("="*60)
    
    y_pred = best_model.predict(X_test_scaled)
    y_pred_proba = best_model.predict_proba(X_test_scaled)[:, 1]
    
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, 
                              target_names=['Non-violent', 'Violent'],
                              digits=4))
    
    print("\nConfusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    print("              Predicted")
    print("              Non-V   Violent")
    print(f"Actual Non-V  {cm[0,0]:5d}   {cm[0,1]:5d}")
    print(f"       Violent {cm[1,0]:5d}   {cm[1,1]:5d}")
    
    # ROC AUC Score
    roc_auc = roc_auc_score(y_test, y_pred_proba)
    print(f"\nROC AUC Score: {roc_auc:.4f}")
    
    # Cross-validation scores
    print("\nCross-validation scores (5-fold):")
    cv_scores = cross_val_score(best_model, X_train_scaled, y_train, cv=5, scoring='roc_auc')
    print(f"Mean: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
    
    # Feature importance (using permutation importance approximation)
    print("\n" + "="*60)
    print("FEATURE IMPORTANCE")
    print("="*60)
    
    feature_names = [
        'brightness', 'bright_t31', 'frp', 'scan', 'track',
        'confidence_score', 'daynight_score', 'thermal_intensity',
        'hour_sin', 'hour_cos', 'month_sin', 'month_cos',
        'dow_sin', 'dow_cos', 'lat_grid', 'lon_grid'
    ]
    
    # Simple permutation importance
    baseline_score = best_model.score(X_test_scaled, y_test)
    importances = []
    
    for i in range(X_test_scaled.shape[1]):
        X_test_permuted = X_test_scaled.copy()
        np.random.shuffle(X_test_permuted[:, i])
        permuted_score = best_model.score(X_test_permuted, y_test)
        importance = baseline_score - permuted_score
        importances.append(importance)
    
    # Sort and display
    feature_importance = sorted(zip(feature_names, importances), 
                              key=lambda x: x[1], reverse=True)
    
    print("\nTop feature importances:")
    for name, importance in feature_importance[:10]:
        print(f"  {name:20s}: {importance:.4f}")
    
    # Save model and scaler
    print("\n" + "="*60)
    print("SAVING MODEL")
    print("="*60)
    
    model_data = {
        'model': best_model,
        'scaler': scaler,
        'feature_names': feature_names,
        'best_params': grid_search.best_params_,
        'roc_auc': roc_auc,
        'training_date': datetime.now().isoformat()
    }
    
    with open('../models/violence_classifier_model.pkl', 'wb') as f:
        pickle.dump(model_data, f)
    
    print("Model saved to violence_classifier_model.pkl")
    
    # Print summary
    print("\n" + "="*60)
    print("TRAINING COMPLETE")
    print("="*60)
    print(f"Final model performance:")
    print(f"  - Accuracy: {best_model.score(X_test_scaled, y_test):.4f}")
    print(f"  - ROC AUC: {roc_auc:.4f}")
    print(f"  - Precision (violent): {cm[1,1]/(cm[1,1]+cm[0,1]):.4f}")
    print(f"  - Recall (violent): {cm[1,1]/(cm[1,1]+cm[1,0]):.4f}")
    
    return model_data


if __name__ == "__main__":
    train_svm_classifier()