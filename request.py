import pandas as pd

class Request:
    def __init__(self, origin: int, destination: int, departure_time: int):
        """
        Initialises the Request class.
        origin: the origin of the request
        destination: the destination of the request
        departure_time: the date of departure

        ****IMPORTANT NOTE***
            The origin and destination should not be the indices of the tracts of the data.
            It should be an integer between 0 and the number of unique zones in your instance.
        """

        self.origin = origin
        self.destination = destination
        self.departure_time = departure_time


