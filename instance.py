import pandas as pd
from request import Request
import numpy as np
import io

class Instance:

    def __init__(self, od_2024: pd.DataFrame = None, nb_requests: int = None, nb_timesteps: int = None,
                 month: int = None, day: int = None, file_path = None):
        """

        Initialisation of the Instance class will be done in two ways:

        1/  Directly through the constructor __init__
            You create an empty instance with just the parameters:
            number of request,
            number of time steps,
            the month of the demand,
            the day of the demand.
            You generate the instance so that it ensures the integrity of the od matrix.

        2/  Through reading a .txt file that represents an instance, by going through the method
            from_file.
        """
        self.file_path = file_path
        self.month = month
        self.day = day
        self.nb_requests = nb_requests
        self.nb_timesteps = nb_timesteps
        self.requests = []
        self.nb_zones = None # the number of different unique zones in the instance

        if self.file_path is not None:
            self.parse_instance()

        if od_2024 is not None:
            self.od_2024 = od_2024
            self.create_requests()
            self.create_travelling_time_matrix()
            self.save_instance_to_txt()

    @classmethod
    def from_file(cls, file_path: str):
        """
        A constructor that initialises the instance from a .txt file
        """
        return cls(file_path=file_path)

    @classmethod
    def from_string(cls, content: str, filename: str):
        """
        **** IMPORTANT NOTE ***
        This is a necessary method for the evaluation process. Please do not modify.
        """
        # Create a dummy path so logic doesn't break
        instance = cls(file_path=filename)
        # New parsing logic that accepts the string 'content'
        instance.parse_from_string(content)
        return instance

    def parse_from_string(self, content: str):
        """
        **** IMPORTANT NOTE ***
        This is a necessary method for the evaluation process. Please do not modify.
        You can develop your own parser for your tests in the method parse_instance() below
        """
        # io.StringIO makes the string act like a file so we can use readlines()
        f = io.StringIO(content)
        lines = [line.strip() for line in f if line.strip()]

        if not lines:
            return

        # Header
        self.nb_requests, self.nb_timesteps, self.nb_zones = map(int, lines[0].split())

        # Requests
        self.requests = []
        for i in range(1, self.nb_requests + 1):
            _, origin, dest, dep_time = map(float, lines[i].split())
            self.requests.append(Request(int(origin), int(dest), dep_time))

        # Travel Time Matrix
        matrix_flat = lines[self.nb_requests + 1:]
        self.travelling_time = np.zeros((self.nb_zones, self.nb_zones, self.nb_timesteps))

        line_idx = 0
        for t in range(self.nb_timesteps):
            for i in range(self.nb_zones):
                self.travelling_time[i, :, t] = [float(val) for val in matrix_flat[line_idx].split()]
                line_idx += 1

    def create_instance(self):
        """
        Creates an instance of a certain number of requests (nb_requests) depending on the distribution of the OD matrix
        """
        pass

    def save_instance_to_txt(self):
        """
        NON-MANDATORY:
        Outputs the instance to a text file with the same format as the example in "instances".
        """


    def parse_instance(self):
        """
        Parses the .txt file that represents an instance.
        You can find an example of an instance and its format and the file "instances".
        """

