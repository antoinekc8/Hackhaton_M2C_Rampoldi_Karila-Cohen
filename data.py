import os

import pandas as pd

class Data:
    def __init__(self, file_path: str):
        """
        Initialises the Data class.
        """
        self.file_path = file_path
        self.data_demand = None
        self.raw_data = None
        self.parse_data()
        self.clean_data()

    def clean_data(self):
        """
        Cleans the data as you judge fit.
        Removes rows with missing values in necessary columns and duplicates.
        """
        necessary_columns = [
            'Trip Start Timestamp', 'Trip End Timestamp', 'Trip Seconds', 'Trip Miles',
            'Pickup Census Tract', 'Dropoff Census Tract', 'Pickup Centroid Location',
            'Dropoff Centroid  Location'
        ]
        # Remove rows with missing values in necessary columns
        self.raw_data = self.raw_data.dropna(subset=necessary_columns)
        # Remove duplicate rows
        self.raw_data = self.raw_data.drop_duplicates()
        print(f"Data cleaned: {len(self.raw_data)} rows remaining")

    def parse_data(self):
        """
        Read the data file.
        """
        self.raw_data = pd.read_csv(self.file_path)
        print(f"Data loaded: {len(self.raw_data)} rows")


    def create_data_demand(self, timestamp_duration: str = '1h'):
        """
        Creates the data_demand dataframe.
        The idea is to aggregate the number of trips or to average the travelling time
        by a time step (here by a time step of timestamp_duration)
        and compute the OD matrix.
        The resulting data frame should be a data frame of columns containing at least the following columns:
        [Trip Start Timestamp], [Pickup Census Tract], [Dropoff Census Tract], [Number of Trips],
        [Travelling Time Average], [Trip Distance Average], ...
        """
        model_data = self.raw_data.copy()
        model_data['Trip Start Timestamp'] = pd.to_datetime(model_data['Trip Start Timestamp'])
        model_data['Hour Timestamp'] = model_data['Trip Start Timestamp'].dt.floor(timestamp_duration)
        
        # Aggregate averages
        od_hourly = (
            model_data
            .groupby(['Hour Timestamp', 'Pickup Census Tract', 'Dropoff Census Tract'], as_index=False)
            .agg({
                'Trip Seconds': 'mean',
                'Trip Miles': 'mean'
            })
        )
        
        # Count trips per OD-hour
        trip_counts = (
            model_data
            .groupby(['Hour Timestamp', 'Pickup Census Tract', 'Dropoff Census Tract'])
            .size()
            .rename('Number of Trips')
            .reset_index()
        )
        
        # Merge count + averages
        self.data_demand = od_hourly.merge(
            trip_counts,
            on=['Hour Timestamp', 'Pickup Census Tract', 'Dropoff Census Tract'],
            how='left'
        ).rename(columns={
            'Trip Seconds': 'Travelling Time Average',
            'Trip Miles': 'Trip Distance Average'
        })
        
        # Rename Hour Timestamp to Trip Start Timestamp for consistency
        self.data_demand = self.data_demand.rename(columns={'Hour Timestamp': 'Trip Start Timestamp'})
        
        print(f"Data demand created: {len(self.data_demand)} OD-hour pairs")
        return self.data_demand






