import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import time


class Prediction:

    def __init__(self, data_demand: pd.DataFrame):
        """
            Initialises the Prediction class.
            data_demand: a dataframe for predicting the demand and travelling time
            predicted_od_2024: a dataframe that represents the OD and travelling time predictions.

            **** IMPORTANT NOTE ****
            The predicted_od_2024 is already loaded with the already defined observation of 2024 that you need to predict.
        """
        self.data_demand = data_demand
        self.predicted_od_2024 = pd.read_csv('data/observations_to_predict.csv', sep=';')
        # Don't convert to datetime here - keep as string for checker compatibility

        self.predicted_od_2024['Number of Trips'] = 0
        self.predicted_od_2024['Travelling Time Average'] = 0.0
        
        # Models and feature columns
        self.flows_model = None
        self.time_model = None
        self.feature_cols = None
        self.pickup_mapping = None
        self.dropoff_mapping = None

        # Automatically run predictions
        if self.data_demand is not None:
            self.predict_demand_2024()
            self.predict_travellingTime_2024()


    def predict_demand_2024(self):
        """
            Train Random Forest models and predict flows and travel times for 2024 observations.
            Fills the columns ['Number of Trips'] and ['Travelling Time Average']
        """
        print("="*70)
        print("STEP 1: Creating OD-hourly demand data...")
        print("="*70)
        od_hourly = self.data_demand
        print(f"✓ Created {len(od_hourly)} OD-hour pairs\n")

        # --- Feature engineering ---
        print("="*70)
        print("STEP 2: Feature engineering...")
        print("="*70)
        
        od_hourly['Trip Start Timestamp'] = pd.to_datetime(od_hourly['Trip Start Timestamp'])
        od_hourly['hour'] = od_hourly['Trip Start Timestamp'].dt.hour
        od_hourly['dayofweek'] = od_hourly['Trip Start Timestamp'].dt.dayofweek
        od_hourly['month'] = od_hourly['Trip Start Timestamp'].dt.month
        od_hourly['is_weekend'] = (od_hourly['dayofweek'] >= 5).astype(int)

        # Category encoding for zones
        pickup_categories = sorted(od_hourly['Pickup Census Tract'].unique())
        dropoff_categories = sorted(od_hourly['Dropoff Census Tract'].unique())

        self.pickup_mapping = {zone: idx for idx, zone in enumerate(pickup_categories)}
        self.dropoff_mapping = {zone: idx for idx, zone in enumerate(dropoff_categories)}

        od_hourly['pickup_code'] = od_hourly['Pickup Census Tract'].map(self.pickup_mapping)
        od_hourly['dropoff_code'] = od_hourly['Dropoff Census Tract'].map(self.dropoff_mapping)

        self.feature_cols = ['pickup_code', 'dropoff_code', 'hour', 'dayofweek', 'month', 'is_weekend']
        X = od_hourly[self.feature_cols]

        y_flows = od_hourly['Number of Trips']
        # Use minutes for travel time to align with evaluation units
        y_travel_time = od_hourly['Travelling Time Average'] / 60.0

        print(f"Features: {self.feature_cols}")
        print(f"Unique pickup zones: {len(pickup_categories)}")
        print(f"Unique dropoff zones: {len(dropoff_categories)}")
        print(f"Time: training data prepared\n")

        # --- Train/test split ---
        print("="*70)
        print("STEP 3: Train/test split...")
        print("="*70)
        X_train, X_test, y_flows_train, y_flows_test = train_test_split(
            X, y_flows, test_size=0.2, random_state=42
        )
        y_time_train = y_travel_time.loc[X_train.index]
        y_time_test = y_travel_time.loc[X_test.index]

        print(f"Training set: {len(X_train)} samples")
        print(f"Test set: {len(X_test)} samples\n")

        # --- Train models ---
        print("="*70)
        print("STEP 4: Training Random Forest models...")
        print("="*70)
        
        print("\n[1/2] Training FLOWS model (trip prediction)...")
        model_start = time.time()
        self.flows_model = RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1, verbose=0)
        self.flows_model.fit(X_train, y_flows_train)
        print(f"Flows model trained ({time.time() - model_start:.2f}s)")

        print("\n[2/2] Training TRAVEL TIME model (with congestion)...")
        model_start = time.time()
        self.time_model = RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1, verbose=0)
        self.time_model.fit(X_train, y_time_train)
        print(f"Travel time model trained ({time.time() - model_start:.2f}s)\n")

        # --- Evaluate models ---
        print("="*70)
        print("STEP 5: Model Evaluation")
        print("="*70)

        flows_pred_test = self.flows_model.predict(X_test)
        time_pred_test = self.time_model.predict(X_test)

        flows_mse = mean_squared_error(y_flows_test, flows_pred_test)
        flows_mae = mean_absolute_error(y_flows_test, flows_pred_test)
        flows_r2 = r2_score(y_flows_test, flows_pred_test)

        time_mse = mean_squared_error(y_time_test, time_pred_test)
        time_mae = mean_absolute_error(y_time_test, time_pred_test)
        time_r2 = r2_score(y_time_test, time_pred_test)

        print("\nFLOWS (Trip Count) Performance:")
        print(f"   MSE: {flows_mse:.4f} | MAE: {flows_mae:.4f} | R²: {flows_r2:.4f}")

        print("\nTRAVEL TIME (with Congestion) Performance:")
        print(f"   MSE: {time_mse:.4f} | MAE: {time_mae:.4f} | R²: {time_r2:.4f}\n")

    def predict_travellingTime_2024(self):
        """
            Make predictions for all 2024 observations using trained models.
            Fills the columns ['Number of Trips'] and ['Travelling Time Average']
        """
        print("="*70)
        print("STEP 6: Loading observations for 2024 predictions...")
        print("="*70)
        print(f"Loaded {len(self.predicted_od_2024)} OD pairs to predict\n")

        # Convert timestamp to datetime for processing
        timestamp_col = pd.to_datetime(self.predicted_od_2024['Trip Start Timestamp'])

        # Convert Census Tracts to integers
        self.predicted_od_2024['Pickup Census Tract'] = self.predicted_od_2024['Pickup Census Tract'].astype(int)
        self.predicted_od_2024['Dropoff Census Tract'] = self.predicted_od_2024['Dropoff Census Tract'].astype(int)

        # Encode with training categories
        self.predicted_od_2024['pickup_code'] = self.predicted_od_2024['Pickup Census Tract'].map(self.pickup_mapping).fillna(-1).astype(int)
        self.predicted_od_2024['dropoff_code'] = self.predicted_od_2024['Dropoff Census Tract'].map(self.dropoff_mapping).fillna(-1).astype(int)

        self.predicted_od_2024['hour'] = timestamp_col.dt.hour
        self.predicted_od_2024['dayofweek'] = timestamp_col.dt.dayofweek
        self.predicted_od_2024['month'] = timestamp_col.dt.month
        self.predicted_od_2024['is_weekend'] = (self.predicted_od_2024['dayofweek'] >= 5).astype(int)

        X_new = self.predicted_od_2024[self.feature_cols]

        # --- Make predictions ---
        print("="*70)
        print("STEP 7: Making predictions for all OD pairs...")
        print("="*70)

        print("\n[1/2] Predicting FLOWS...")
        pred_flows_raw = self.flows_model.predict(X_new)
        pred_flows = np.clip(pred_flows_raw, 0, None)
        self.predicted_od_2024['Number of Trips'] = np.rint(pred_flows).astype(int)
        print(f"Flows predicted | Mean: {np.mean(self.predicted_od_2024['Number of Trips']):.2f} trips/hour")

        print("\n[2/2] Predicting TRAVEL TIMES (accounting for congestion)...")
        pred_time_raw = self.time_model.predict(X_new)
        pred_time = np.clip(pred_time_raw, 0, None)
        self.predicted_od_2024['Travelling Time Average'] = pred_time
        print(f"Travel times predicted | Mean: {np.mean(self.predicted_od_2024['Travelling Time Average']):.2f} minutes")
        print(f"                       | Min: {np.min(self.predicted_od_2024['Travelling Time Average']):.2f} | Max: {np.max(self.predicted_od_2024['Travelling Time Average']):.2f}\n")

        # Clean up temporary columns
        self.predicted_od_2024.drop(columns=['pickup_code', 'dropoff_code', 'hour', 'dayofweek', 'month', 'is_weekend'], inplace=True)

        # --- Save predictions ---
        print("="*70)
        print("STEP 8: Saving predictions...")
        print("="*70)
        output_path = 'data/predicted_observations.csv'
        output_cols = ['Trip Start Timestamp', 'Pickup Census Tract', 'Dropoff Census Tract', 
                       'Number of Trips', 'Travelling Time Average']
        
        # Save with semicolon separator to match input format
        self.predicted_od_2024[output_cols].to_csv(output_path, index=False, sep=';')

        print(f"Predictions saved to {output_path}")
        print(f"Total predictions: {len(self.predicted_od_2024)}")
        print(f"Time period: {timestamp_col.min()} to {timestamp_col.max()}")
        print("="*70)


