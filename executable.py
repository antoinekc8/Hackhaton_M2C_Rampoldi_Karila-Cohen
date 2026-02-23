import os
from data import Data
from checker import Checker
from prediction import Prediction
from instance import Instance
from optimisation import Optimisation

if __name__ == '__main__':

    TEAM_NAME = ""

    # Historical data
    print("### READING THE DATA ###")
    data: Data = Data('data/Data_2019-2023')
    print(30 * "-")
    print("### Predicting the OD and travelling time matrices ###")
    predictor: Prediction = Prediction(data.data_demand)

    # Initialises the checker
    checker = Checker.from_processed_file()

    # Evaluates the prediction
    if 'Number of Trips' in predictor.predicted_od_2024 and 'Travelling Time Average' in predictor.predicted_od_2024:
        checker.evaluate_prediction_report(predictor.predicted_od_2024)

    # List of instances to evaluate
    instance_names = sorted(checker._INTERNAL_INSTANCES.keys())

    for f_name in instance_names:
        print(f'### Checking instance {f_name} ###')

        # Pull the text from the binary
        instance_content = checker.get_instance_data(f_name)

        # Create the instance from the string
        instance: Instance = Instance.from_string(instance_content, f_name)

        # Runs the solver
        optimisation: Optimisation = Optimisation(instance)

        # Evaluation of the solution
        checker.check_from_file(instance, team_name=TEAM_NAME)
