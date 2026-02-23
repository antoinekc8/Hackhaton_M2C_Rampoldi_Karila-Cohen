from instance import Instance
import numpy as np

class Optimisation:

    def __init__(self, instance):

        """
            A constructor for the Optimisation class
        """

        self.instance = instance
        self.vehicles = []
        self.departure_times = []
        self.run()
        self.write_to_file()

    def run(self):
        """
        Proposes an optimisation approach the solve the time-dependent Dial-A-Ride problem.
        """
        pass

    def write_to_file(self):
        """
            Writes a solution to a .txt file in order to be evaluated.
            You can find an example of how a solution should be written in the "solutions" file.
        """
        pass