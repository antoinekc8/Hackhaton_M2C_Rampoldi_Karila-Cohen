import os

import pandas as pd

class Data:
    def __init__(self, file_path: str):
        """
        Initialises the Data class.
        """
        self.file_path = file_path
        self.data_demand = None
        self.parse_data()

    def clean_data(self):
        """
        Cleans the data as you judge fit.
        """
        pass

    def parse_data(self):
        """
        Read the data file.
        """
        pass


    def create_data_demand(self, timestamp_duration: str = '1h'):
        """
        Creates the data_demand dataframe.
        The idea is to aggregate the number of trips or to average the travelling time
        by a time step (here by a time step of timestamp_duration)
        and compute the OD matrix.
        The resulting data frame should be a data frame of columns containing at least the following columns:
        [Trip Start Timestamp], [Pickup Census Tract], [Dropoff Census Tract], [Number of Trips],
        [Travelling Time Average], ...
        """

        pass






