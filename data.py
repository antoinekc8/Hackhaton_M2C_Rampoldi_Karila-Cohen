import os
import pandas as pd

class Data:
    def __init__(self, file_path: str):
        """
        Initializes the Data class and triggers the loading and cleaning pipeline.
        """
        self.file_path = file_path
        self.data_demand = None
        self.raw_data = None
        self.parse_data()
        self.clean_data()

    def parse_data(self):
        """
        Reads the raw CSV file using the semicolon separator.
        """
        print(f"Loading data from: {self.file_path}")
        # Added: sep=';' to correctly handle your specific CSV format
        self.raw_data = pd.read_csv(self.file_path, sep=';')
        print(f"Data loaded: {len(self.raw_data)} rows")

    def clean_data(self):
        """
        Removes rows with missing values in key columns and handles data type conversion.
        """
        # Ensure column names match the CSV headers exactly
        necessary_columns = [
            'Trip Start Timestamp', 'Trip Seconds', 'Trip Miles',
            'Pickup Census Tract', 'Dropoff Census Tract'
        ]
        
        # Remove rows with null values in key columns
        self.raw_data = self.raw_data.dropna(subset=necessary_columns)
        
        # Added: Explicit conversion to integer for Census Tracts
        # This prevents floating-point precision issues during grouping/merging
        self.raw_data['Pickup Census Tract'] = self.raw_data['Pickup Census Tract'].astype(int)
        self.raw_data['Dropoff Census Tract'] = self.raw_data['Dropoff Census Tract'].astype(int)
        
        self.raw_data = self.raw_data.drop_duplicates()
        print(f"Data cleaned: {len(self.raw_data)} rows remaining")

    def create_data_demand(self, timestamp_duration: str = '1h'):
        """
        Aggregates trip data into an Origin-Destination (OD) matrix.
        Returns a DataFrame with average travel times and trip counts.
        """
        print(f"Aggregating data with duration: {timestamp_duration}")
        model_data = self.raw_data.copy()
        model_data['Trip Start Timestamp'] = pd.to_datetime(model_data['Trip Start Timestamp'])
        
        # Floor the timestamp to the specified duration (e.g., '1h' or '15min')
        model_data['Time_Slot'] = model_data['Trip Start Timestamp'].dt.floor(timestamp_duration)
        
        # OPTIMIZATION: Perform aggregation in a single pass for efficiency
        self.data_demand = (
            model_data
            .groupby(['Time_Slot', 'Pickup Census Tract', 'Dropoff Census Tract'], as_index=False)
            .agg({
                'Trip Seconds': ['mean', 'count'], # Calculate mean and count simultaneously
                'Trip Miles': 'mean'
            })
        )
        
        # Flatten MultiIndex columns and rename for consistency with executable.py
        self.data_demand.columns = [
            'Trip Start Timestamp', 'Pickup Census Tract', 'Dropoff Census Tract',
            'Travelling Time Average', 'Number of Trips', 'Trip Distance Average'
        ]
        
        print(f"Data demand created: {len(self.data_demand)} OD-time pairs")
        return self.data_demand