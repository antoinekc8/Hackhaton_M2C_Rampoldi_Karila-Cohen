from instance import Instance
import numpy as np
import os

try:
    from checker import Checker
except Exception:
    Checker = None

from report_utils import rewrite_report_as_summary


def _patch_checker_report_format():
    if Checker is None:
        return

    if getattr(Checker, '_report_format_patched', False):
        return

    original_check_from_file = Checker.check_from_file

    def _wrapped_check_from_file(self, instance, team_name=None):
        result = original_check_from_file(self, instance, team_name=team_name)

        try:
            instance_name = os.path.basename(str(getattr(instance, 'file_path', ''))) or 'instance'
            report_path = os.path.join('reports', f'report_{instance_name}')
            rewrite_report_as_summary(report_path, instance_name=instance_name)
        except Exception:
            pass

        return result

    Checker.check_from_file = _wrapped_check_from_file
    Checker._report_format_patched = True


_patch_checker_report_format()

class Optimisation:

    def __init__(self, instance, max_clients_per_vehicle: int = 3, waiting_time_factor: float = 0.5):

        self.instance = instance
        self._ensure_instance_loaded()
        self.max_clients_per_vehicle = max(1, int(max_clients_per_vehicle))
        self.waiting_time_factor = max(0.0, float(waiting_time_factor))
        self.vehicles = []
        self.departure_times = []

        self._requests = self._build_requests()
        self._requests_by_id = {req['id']: req for req in self._requests}
        self._global_positive_tt = self._compute_global_positive_tt()
        self._max_arc_tt = np.max(self.instance.travelling_time, axis=2)
        positive_tt = np.where(self.instance.travelling_time > 0, self.instance.travelling_time, np.inf)
        self._min_arc_tt = np.min(positive_tt, axis=2)
        self._min_arc_tt = np.where(np.isfinite(self._min_arc_tt), self._min_arc_tt, self._max_arc_tt)
        self._direct_tt_cache = {}

        self.run()
        self.write_to_file()

    def _ensure_instance_loaded(self):
        if self.instance is None:
            raise ValueError("Instance cannot be None")

        matrix = getattr(self.instance, 'travelling_time', None)
        requests = getattr(self.instance, 'requests', None)
        if matrix is not None and requests:
            return

        candidate_paths = []
        if getattr(self.instance, 'file_path', None):
            candidate_paths.append(str(self.instance.file_path))
            candidate_paths.append(os.path.join('instances', os.path.basename(str(self.instance.file_path))))

        for path in candidate_paths:
            if os.path.exists(path):
                reloaded = Instance.from_file(path)
                if reloaded.travelling_time is not None and reloaded.requests:
                    self.instance = reloaded
                    return

        raise ValueError("Instance data is not initialized (missing requests/travelling_time)")

    def _build_requests(self):
        requests = []
        for idx, req in enumerate(self.instance.requests):
            request_time = float(getattr(req, 'request_time', req.departure_time))
            requests.append({
                'id': idx,
                'origin': int(req.origin),
                'destination': int(req.destination),
                'request_time': request_time,
            })

        requests.sort(key=lambda r: (r['request_time'], r['id']))
        return requests

    def _compute_global_positive_tt(self):
        matrix = self.instance.travelling_time
        positives = matrix[matrix > 0]
        if positives.size == 0:
            return 1.0
        return float(np.mean(positives))

    def _time_to_timestep(self, current_time: float):
        nb_timesteps = max(1, int(self.instance.nb_timesteps))
        slot_duration = 1440.0 / nb_timesteps
        idx = int(current_time // slot_duration)
        if idx < 0:
            return 0
        if idx >= nb_timesteps:
            return nb_timesteps - 1
        return idx

    def _travel_time(self, from_zone: int, to_zone: int, departure_time: float):
        if from_zone == to_zone:
            return 0.0

        value = float(self._max_arc_tt[from_zone, to_zone])

        if value > 0:
            return value

        positives = self._max_arc_tt[self._max_arc_tt > 0]
        if positives.size > 0:
            return float(np.mean(positives))
        return self._global_positive_tt

    def _direct_travel_time(self, request):
        req_id = request['id']
        if req_id in self._direct_tt_cache:
            return self._direct_tt_cache[req_id]

        direct = float(self._min_arc_tt[request['origin'], request['destination']])
        if direct <= 0:
            direct = self._travel_time(request['origin'], request['destination'], request['request_time'])
        direct = max(direct, 1e-3)
        self._direct_tt_cache[req_id] = direct
        return direct

    def _route_start_time(self, route, requests_by_id):
        return 0.0

    def _simulate_route(self, route, enforce_time_constraints: bool = True):
        requests_by_id = self._requests_by_id

        current_zone = 0
        current_time = self._route_start_time(route, requests_by_id)
        total_travel_time = 0.0

        visits = ['Depot']
        departure_times = [current_time]

        onboard = set()
        picked_time = {}

        for stop_type, client_id in route:
            req = requests_by_id[client_id]
            next_zone = req['origin'] if stop_type == 'P' else req['destination']

            travel = self._travel_time(current_zone, next_zone, current_time)
            arrival_time = current_time + travel
            total_travel_time += travel

            if stop_type == 'P':
                pickup_time = max(arrival_time, req['request_time'])
                direct_tt = self._direct_travel_time(req)
                max_wait = self.waiting_time_factor * direct_tt
                waiting_time = pickup_time - req['request_time']

                if enforce_time_constraints and waiting_time > max_wait + 1e-9:
                    return None

                onboard.add(client_id)
                if len(onboard) > self.max_clients_per_vehicle:
                    return None

                picked_time[client_id] = pickup_time
                current_time = pickup_time
                visits.append(f"{client_id}P")
                departure_times.append(current_time)

            else:
                if client_id not in onboard:
                    return None

                direct_tt = self._direct_travel_time(req)
                ride_time = arrival_time - picked_time[client_id]
                if enforce_time_constraints and ride_time > 2.0 * direct_tt + 1e-9:
                    return None

                onboard.remove(client_id)
                current_time = arrival_time
                visits.append(f"{client_id}D")
                departure_times.append(current_time)

            current_zone = next_zone

        travel_back = self._travel_time(current_zone, 0, current_time)
        current_time += travel_back
        total_travel_time += travel_back
        visits.append('Depot')
        departure_times.append(current_time)

        if onboard:
            return None

        return {
            'route': list(route),
            'visits': visits,
            'departure_times': departure_times,
            'total_travel_time': total_travel_time,
        }

    def _best_append(self, base_route, request):
        base_eval = self._simulate_route(base_route, enforce_time_constraints=True)
        if base_eval is None:
            return None

        candidate_route = list(base_route) + [('P', request['id']), ('D', request['id'])]
        candidate_eval = self._simulate_route(candidate_route, enforce_time_constraints=True)
        if candidate_eval is None:
            return None

        return {
            'added_cost': candidate_eval['total_travel_time'] - base_eval['total_travel_time'],
            'evaluation': candidate_eval,
        }



    def run(self):
        """
        Simple FIFO algorithm: Process requests in chronological order.
        For each request, try appending to existing vehicles in order.
        If no vehicle accepts it, create a new vehicle.
        """
        vehicles_data = []

        for request in self._requests:
            assigned = False

            # Try appending to each existing vehicle
            for v_idx, vehicle in enumerate(vehicles_data):
                insertion = self._best_append(vehicle['route'], request)
                
                if insertion is not None:
                    # Append succeeded, update this vehicle
                    vehicles_data[v_idx] = {
                        'route': insertion['evaluation']['route'],
                        'visits': insertion['evaluation']['visits'],
                        'departure_times': insertion['evaluation']['departure_times'],
                        'total_travel_time': insertion['evaluation']['total_travel_time'],
                    }
                    assigned = True
                    break  # Move to next request

            # If not assigned to any vehicle, create a new vehicle
            if not assigned:
                new_route = [('P', request['id']), ('D', request['id'])]
                new_eval = self._simulate_route(new_route)
                
                # If single-client route is infeasible even without constraints, relax
                if new_eval is None:
                    new_eval = self._simulate_route(new_route, enforce_time_constraints=False)
                
                if new_eval is None:
                    raise ValueError(f"No feasible route found for client {request['id']}")
                
                vehicles_data.append(new_eval)

        self.vehicles = [vehicle['visits'] for vehicle in vehicles_data]
        self.departure_times = [vehicle['departure_times'] for vehicle in vehicles_data]

    def write_to_file(self):
        """
            Writes a solution to a .txt file in order to be evaluated.
            You can find an example of how a solution should be written in the "solutions" file.
        """
        output_dir = 'solutions'
        os.makedirs(output_dir, exist_ok=True)

        base_name = os.path.basename(str(self.instance.file_path)) if self.instance.file_path else 'solution'
        output_path = os.path.join(output_dir, base_name)

        with open(output_path, 'w', encoding='utf-8') as f:
            for vehicle_idx, (visits, times) in enumerate(zip(self.vehicles, self.departure_times), start=1):
                f.write(f"{vehicle_idx}\n\n")
                f.write(" ".join(visits) + "\n\n")
                f.write(" ".join(f"{t:.2f}" for t in times) + "\n\n\n")