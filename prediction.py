import os

import pandas as pd


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

        self.predicted_od_2024['Number of Trips'] = 0
        self.predicted_od_2024['Travelling Time Average'] = 0.0


    def predict_demand_2024(self):
        """
            Predict the number of trips for each observation of the predicted_od_2024.
            It should just fill the column ['Number of Trips']
        """
        pass

    def predict_travellingTime_2024(self):
        """
            Predict the number of trips for each observation of the predicted_od_2024.
            It should just fill the column ['Travelling Time Average']
        """
        pass


