import pandas as pd
from request import Request
import numpy as np
import io
import os
from datetime import datetime
import time


class Instance:

    @staticmethod
    def _build_request(origin: int, destination: int, departure_time: float):
        req = Request(origin, destination, departure_time)
        if not hasattr(req, 'request_time'):
            req.request_time = departure_time
        return req

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
        self.travelling_time = None
        self.clients = None
        self.time_slots = None
        self.zone_to_idx = None
        self.od_2024 = None

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
            self.requests.append(self._build_request(int(origin), int(dest), dep_time))

        # Travel Time Matrix
        matrix_flat = lines[self.nb_requests + 1:]
        self.travelling_time = np.zeros((self.nb_zones, self.nb_zones, self.nb_timesteps))

        line_idx = 0
        for t in range(self.nb_timesteps):
            for i in range(self.nb_zones):
                self.travelling_time[i, :, t] = [float(val) for val in matrix_flat[line_idx].split()]
                line_idx += 1

        self._save_raw_instance_content(content)
        self.write_solution_to_txt()

    def _save_raw_instance_content(self, content: str):
        output_dir = 'instances'
        os.makedirs(output_dir, exist_ok=True)

        base_name = os.path.basename(str(self.file_path)) if self.file_path else 'instance_exported'
        if not base_name:
            base_name = 'instance_exported'

        output_path = os.path.join(output_dir, base_name)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def write_solution_to_txt(self, max_clients_per_vehicle: int = 1):
        """
        Writes a feasible solution file for the current instance.
        The solution is saved in the solutions/ folder with the same name as the instance.
        """
        if not self.requests and not self.clients:
            return

        output_dir = 'solutions'
        os.makedirs(output_dir, exist_ok=True)

        base_name = os.path.basename(self.file_path) if self.file_path else 'solution'
        solution_filename = os.path.join(output_dir, base_name)

        if self.file_path and os.path.exists(self.file_path):
            if os.path.abspath(self.file_path) == os.path.abspath(solution_filename):
                print("Skipping solution write to avoid overwriting instance file.")
                return

        clients = []
        if self.requests:
            for idx, req in enumerate(self.requests):
                clients.append({
                    'client_id': idx,
                    'pickup_zone': req.origin,
                    'dropoff_zone': req.destination
                })
        else:
            for client in self.clients:
                clients.append({
                    'client_id': int(client['client_id']),
                    'pickup_zone': int(client['pickup_zone']),
                    'dropoff_zone': int(client['dropoff_zone'])
                })

        if not clients:
            return

        if max_clients_per_vehicle < 1:
            max_clients_per_vehicle = 1

        client_lookup = {c['client_id']: c for c in clients}

        matrix = None
        if self.travelling_time is not None and self.travelling_time.size:
            matrix = self.travelling_time[:, :, 0]
            non_zero = matrix[matrix > 0]
            avg_travel = float(np.mean(non_zero)) if len(non_zero) else 1.0
        else:
            avg_travel = 1.0

        vehicles = [clients[i:i + max_clients_per_vehicle] for i in range(0, len(clients), max_clients_per_vehicle)]

        with open(solution_filename, 'w') as f:
            for v_idx, group in enumerate(vehicles, start=1):
                f.write("{0}\n".format(v_idx))

                visits = ["Depot"]
                for c in group:
                    visits.append("{0}P".format(c['client_id']))
                for c in group:
                    visits.append("{0}D".format(c['client_id']))
                visits.append("Depot")

                f.write("{0}\n".format(" ".join(visits)))

                times = []
                current_time = 0.0
                times.append(current_time)

                prev_zone = None
                for visit in visits[1:]:
                    if visit == "Depot":
                        travel = avg_travel
                        prev_zone = None
                    else:
                        client_id = int(visit[:-1])
                        is_pickup = visit.endswith('P')
                        zone = client_lookup[client_id]['pickup_zone'] if is_pickup else client_lookup[client_id]['dropoff_zone']

                        if prev_zone is None:
                            travel = avg_travel
                        elif matrix is not None:
                            travel = float(matrix[prev_zone][zone])
                            if travel <= 0:
                                travel = avg_travel
                        else:
                            travel = avg_travel

                        prev_zone = zone

                    current_time += travel
                    times.append(current_time)

                f.write("{0}\n".format(" ".join(["{0:.2f}".format(t) for t in times])))

        print("✓ Solution file written to: {0}".format(solution_filename))

    def create_requests(self):
        """
        Creates requests (clients) for the instance based on predicted flows for a given date.
        Samples clients proportionally to predicted flows and generates exactly nb_requests clients.
        """
        print("\nSTEP 2: Generating {0} synthetic clients...".format(self.nb_requests))
        
        # Get unique zones
        all_zones = sorted(set(self.od_2024['Pickup Census Tract'].unique()) | 
                           set(self.od_2024['Dropoff Census Tract'].unique()))
        self.zone_to_idx = {zone: idx for idx, zone in enumerate(all_zones)}
        self.nb_zones = len(all_zones)
        
        print("Total zones: {0}".format(self.nb_zones))
        
        # Generate clients
        self.clients = []
        client_id = 0
        total_flows = 0
        
        # Get all unique time slots
        self.time_slots = sorted(self.od_2024['Trip Start Timestamp'].unique())
        print("Time slots: {0} hours".format(len(self.time_slots)))
        
        # Calculate total flows
        for _, row in self.od_2024.iterrows():
            predicted_flow = int(row['Predicted Flows'])
            total_flows += predicted_flow
        
        # Scale flows to get exactly nb_requests clients
        scaling_factor = self.nb_requests / max(total_flows, 1)
        
        # Generate clients
        for _, row in self.od_2024.iterrows():
            num_clients_this_od = max(1, int(row['Predicted Flows'] * scaling_factor))
            
            for _ in range(num_clients_this_od):
                if client_id < self.nb_requests:
                    pickup_zone = int(row['Pickup Census Tract'])
                    dropoff_zone = int(row['Dropoff Census Tract'])
                    time_slot = row['Trip Start Timestamp']
                    
                    self.clients.append({
                        'client_id': client_id,
                        'pickup_zone': self.zone_to_idx[pickup_zone],
                        'dropoff_zone': self.zone_to_idx[dropoff_zone],
                        'time_slot': time_slot,
                        'predicted_flow': row['Predicted Flows'],
                        'travel_time': row['Predicted Travel Time (s)']
                    })
                    client_id += 1
        
        # If we have fewer than nb_requests, duplicate some
        while len(self.clients) < self.nb_requests:
            self.clients.append(self.clients[len(self.clients) % len(self.clients)])
        
        # Trim to exactly nb_requests
        self.clients = self.clients[:self.nb_requests]
        print("✓ Generated {0} synthetic clients".format(len(self.clients)))

    def create_travelling_time_matrix(self):
        """
        Creates travel time matrices for each time slot from the predicted observations.
        Fills the travelling_time 3D array (zones x zones x timesteps).
        """
        print("\nSTEP 3: Creating distance/travel time matrices...")
        
        self.travelling_time = np.zeros((self.nb_zones, self.nb_zones, len(self.time_slots)))
        
        for t_idx, hour in enumerate(self.time_slots):
            # Get predictions for this hour
            hour_data = self.od_2024[self.od_2024['Trip Start Timestamp'] == hour]
            matrix = np.zeros((self.nb_zones, self.nb_zones))
            
            # Fill in the travel times from predictions
            for _, row in hour_data.iterrows():
                from_idx = self.zone_to_idx[int(row['Pickup Census Tract'])]
                to_idx = self.zone_to_idx[int(row['Dropoff Census Tract'])]
                travel_time = row['Predicted Travel Time (s)']
                matrix[from_idx][to_idx] = travel_time
            
            # Fill remaining entries with average or default
            for i in range(self.nb_zones):
                for j in range(self.nb_zones):
                    if i == j:
                        matrix[i][j] = 0
                    elif matrix[i][j] == 0:
                        non_zero = matrix[matrix > 0]
                        if len(non_zero) > 0:
                            matrix[i][j] = np.mean(non_zero)
                        else:
                            matrix[i][j] = 600
            
            self.travelling_time[:, :, t_idx] = matrix
        
        self.nb_timesteps = len(self.time_slots)
        print("✓ Created {0} travel time matrices".format(self.nb_timesteps))

    def save_instance_to_txt(self):
        """
        Outputs the instance to a text file with the standard format.
        Creates file in instances/ directory with format:
        - Header: num_clients num_timesteps num_zones
        - Blank line
        - Clients: client_id pickup_zone dropoff_zone request_time
        - Blank line
        - Distance matrices: one matrix per timestep
        """
        print("\nSTEP 4: Writing instance file...")
        
        output_dir = 'instances'
        os.makedirs(output_dir, exist_ok=True)
        
        typical_date = self.time_slots[0]
        date_str = typical_date.strftime('%d_%m_%Y')
        instance_filename = os.path.join(output_dir, "instance_{0}_clients_{1}".format(self.nb_requests, date_str))
        self.file_path = instance_filename
        
        with open(instance_filename, 'w') as f:
            # Header
            f.write("{0} {1} {2}\n".format(len(self.clients), self.nb_timesteps, self.nb_zones))
            f.write("\n")  # Blank line after header
            
            # Clients with request_time
            for client in self.clients:
                # Convert time_slot (datetime) to minutes since midnight
                time_hours = client['time_slot'].hour
                time_minutes = client['time_slot'].minute
                request_time_minutes = time_hours * 60 + time_minutes
                f.write("{0} {1} {2} {3}\n".format(
                    client['client_id'], 
                    client['pickup_zone'], 
                    client['dropoff_zone'],
                    request_time_minutes))
            
            f.write("\n")  # Blank line before matrices
            
            # Distance matrices (no comment lines)
            for t_idx in range(self.nb_timesteps):
                matrix = self.travelling_time[:, :, t_idx]
                
                for i in range(self.nb_zones):
                    row_str = " ".join(["{0:.2f}".format(matrix[i][j]) for j in range(self.nb_zones)])
                    f.write("{0}\n".format(row_str))
                
                # Blank line between timesteps (except after the last one)
                if t_idx < self.nb_timesteps - 1:
                    f.write("\n")
        
        print("✓ Instance file written to: {0}".format(instance_filename))
        
        # Summary statistics
        avg_travel_time = np.mean([c['travel_time'] for c in self.clients])
        min_travel_time = np.min([c['travel_time'] for c in self.clients])
        max_travel_time = np.max([c['travel_time'] for c in self.clients])
        
        print("\n  Clients: {0} | Time steps: {1} | Zones: {2}".format(len(self.clients), self.nb_timesteps, self.nb_zones))
        print("  Travel time - Avg: {0:.1f}s ({1:.1f}min) | Min: {2:.1f}s | Max: {3:.1f}s".format(
            avg_travel_time, avg_travel_time/60, min_travel_time, max_travel_time))

    def parse_instance(self):
        """
        Parses the .txt file that represents an instance.
        You can find an example of an instance in the instances folder.
        """
        if not self.file_path or not os.path.exists(self.file_path):
            return
        
        with open(self.file_path, 'r') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        if not lines:
            return
        
        # Header
        header = lines[0].split()
        self.nb_requests = int(header[0])
        self.nb_timesteps = int(header[1])
        self.nb_zones = int(header[2])
        
        # Requests
        self.requests = []
        for i in range(1, self.nb_requests + 1):
            parts = lines[i].split()
            client_id = int(parts[0])
            origin = int(parts[1])
            dest = int(parts[2])
            # Check if request_time is present (4th column)
            request_time = float(parts[3]) if len(parts) > 3 else 0.0
            self.requests.append(self._build_request(origin, dest, request_time))
        
        # Travel time matrices
        self.travelling_time = np.zeros((self.nb_zones, self.nb_zones, self.nb_timesteps))
        
        line_idx = self.nb_requests + 1
        for t in range(self.nb_timesteps):
            for i in range(self.nb_zones):
                values = [float(x) for x in lines[line_idx].split()]
                self.travelling_time[i, :, t] = values
                line_idx += 1

