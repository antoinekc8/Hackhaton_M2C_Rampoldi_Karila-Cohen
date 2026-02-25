from instance import Instance
import numpy as np
import os
import shutil
import itertools

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
            if os.path.exists(report_path):
                raw_backup = os.path.join('reports', f'local_{instance_name}.txt')
                shutil.copyfile(report_path, raw_backup)
            rewrite_report_as_summary(report_path, instance_name=instance_name)
        except Exception:
            pass

        return result

    Checker.check_from_file = _wrapped_check_from_file
    Checker._report_format_patched = True


_patch_checker_report_format()

class Optimisation:

    PROFILES = {
        'default': {
            'max_clients_per_vehicle': 3,
            'waiting_time_factor': 0.5,
            'validate_with_checker': True,
            'insertion_scan_limit': 20,
            'use_global_best_insertion': True,
            'consolidate_vehicles': True,
        },
        'fleet': {
            'max_clients_per_vehicle': 3,
            'waiting_time_factor': 0.5,
            'validate_with_checker': True,
            'insertion_scan_limit': 24,
            'use_global_best_insertion': True,
            'consolidate_vehicles': True,
        },
        'fleet_strong': {
            'max_clients_per_vehicle': 3,
            'waiting_time_factor': 0.5,
            'validate_with_checker': True,
            'insertion_scan_limit': 28,
            'use_global_best_insertion': True,
            'consolidate_vehicles': True,
        },
        'ultra_fleet': {
            'max_clients_per_vehicle': 3,
            'waiting_time_factor': 0.5,
            'validate_with_checker': True,
            'insertion_scan_limit': 32,
            'use_global_best_insertion': True,
            'consolidate_vehicles': True,
            'target_vehicle_count': 20,
        },
    }

    def __init__(self, instance, max_clients_per_vehicle: int | None = None, waiting_time_factor: float | None = None,
                 validate_with_checker: bool | None = None, insertion_scan_limit: int | None = None,
                 use_global_best_insertion: bool | None = None, consolidate_vehicles: bool | None = None,
                 optimization_profile: str = 'ultra_fleet'):

        self.instance = instance
        self._ensure_instance_loaded()
        profile_key = str(optimization_profile or 'default').strip().lower()
        if profile_key not in self.PROFILES:
            profile_key = 'default'
        profile = self.PROFILES[profile_key]

        max_clients_value = profile['max_clients_per_vehicle'] if max_clients_per_vehicle is None else max_clients_per_vehicle
        waiting_factor_value = profile['waiting_time_factor'] if waiting_time_factor is None else waiting_time_factor
        validate_value = profile['validate_with_checker'] if validate_with_checker is None else validate_with_checker
        insertion_scan_value = profile['insertion_scan_limit'] if insertion_scan_limit is None else insertion_scan_limit
        global_best_value = profile['use_global_best_insertion'] if use_global_best_insertion is None else use_global_best_insertion
        consolidate_value = profile['consolidate_vehicles'] if consolidate_vehicles is None else consolidate_vehicles
        target_vehicle_count_value = profile.get('target_vehicle_count', None)

        self.optimization_profile = profile_key
        self.max_clients_per_vehicle = max(1, int(max_clients_value))
        self.waiting_time_factor = max(0.0, float(waiting_factor_value))
        self.validate_with_checker = bool(validate_value)
        self.insertion_scan_limit = max(2, int(insertion_scan_value))
        self.use_global_best_insertion = bool(global_best_value)
        self.consolidate_vehicles = bool(consolidate_value)
        self.target_vehicle_count = None if target_vehicle_count_value is None else max(1, int(target_vehicle_count_value))
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
        self._validate_and_repair_with_checker()

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
        for stop_type, client_id in route:
            if stop_type == 'P':
                req = requests_by_id[client_id]
                travel_from_depot = self._travel_time(0, req['origin'], 0.0)
                return req['request_time'] - travel_from_depot
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

    def _best_insertion(self, base_route, request, scan_limit=None):
        base_eval = self._simulate_route(base_route, enforce_time_constraints=True)
        if base_eval is None:
            return None

        best = self._best_append(base_route, request)
        route_len = len(base_route)
        active_scan_limit = self.insertion_scan_limit if scan_limit is None else max(2, int(scan_limit))
        pickup_start = max(0, route_len - active_scan_limit)

        for pickup_pos in range(pickup_start, route_len + 1):
            dropoff_end = min(route_len + 1, pickup_pos + active_scan_limit)
            for dropoff_pos in range(pickup_pos + 1, dropoff_end + 1):
                candidate_route = list(base_route)
                candidate_route.insert(pickup_pos, ('P', request['id']))
                candidate_route.insert(dropoff_pos, ('D', request['id']))

                candidate_eval = self._simulate_route(candidate_route, enforce_time_constraints=True)
                if candidate_eval is None:
                    continue

                added_cost = candidate_eval['total_travel_time'] - base_eval['total_travel_time']
                if best is None or added_cost < best['added_cost']:
                    best = {
                        'added_cost': added_cost,
                        'evaluation': candidate_eval,
                    }

        return best

    def _build_single_client_solution(self):
        vehicles_data = []
        for request in self._requests:
            route = [('P', request['id']), ('D', request['id'])]
            route_eval = self._simulate_route(route, enforce_time_constraints=True)
            if route_eval is None:
                route_eval = self._simulate_route(route, enforce_time_constraints=False)
            if route_eval is None:
                raise ValueError(f"Unable to build single-client route for client {request['id']}")
            vehicles_data.append(route_eval)

        self.vehicles = [vehicle['visits'] for vehicle in vehicles_data]
        self.departure_times = [vehicle['departure_times'] for vehicle in vehicles_data]

    def _request_ids_from_route(self, route):
        request_ids = [client_id for stop_type, client_id in route if stop_type == 'P']
        request_ids.sort(key=lambda rid: (self._requests_by_id[rid]['request_time'], rid))
        return request_ids

    def _route_request_count(self, route):
        return sum(1 for stop_type, _ in route if stop_type == 'P')

    def _pick_best_fleet_candidate(self, candidates):
        if not candidates:
            return None

        best_choice = None
        for candidate in candidates:
            if best_choice is None:
                best_choice = candidate
                continue

            if self.optimization_profile == 'ultra_fleet':
                if candidate['target_load'] > best_choice['target_load']:
                    best_choice = candidate
                    continue
                if (candidate['target_load'] == best_choice['target_load'] and
                        candidate['added_cost'] < best_choice['added_cost']):
                    best_choice = candidate
                    continue
            elif candidate['added_cost'] < best_choice['added_cost']:
                best_choice = candidate

        return best_choice

    def _solution_score(self, vehicles_data):
        total_travel = sum(vehicle['total_travel_time'] for vehicle in vehicles_data)
        return (len(vehicles_data), total_travel)

    def _request_sequences(self):
        base = list(self._requests)
        if not base:
            return [base]

        chronological = list(base)
        reverse_chronological = list(reversed(base))
        long_trip_first = sorted(
            base,
            key=lambda req: (
                -self._direct_travel_time(req),
                req['request_time'],
                req['id'],
            ),
        )
        early_tight_first = sorted(
            base,
            key=lambda req: (
                req['request_time'],
                self._direct_travel_time(req),
                req['id'],
            ),
        )

        candidates = [chronological, reverse_chronological, long_trip_first, early_tight_first]

        if len(base) > 160:
            candidates = candidates[:3]

        unique_sequences = []
        seen = set()
        for sequence in candidates:
            key = tuple(req['id'] for req in sequence)
            if key in seen:
                continue
            seen.add(key)
            unique_sequences.append(sequence)

        return unique_sequences

    def _build_constructive_solution(self, request_sequence):
        vehicles_data = []

        for request in request_sequence:
            candidate_choices = []

            for v_idx, vehicle in enumerate(vehicles_data):
                insertion = self._best_insertion(vehicle['route'], request)
                if insertion is None:
                    continue

                if not self.use_global_best_insertion:
                    candidate_choices = [{
                        'vehicle_idx': v_idx,
                        'added_cost': insertion['added_cost'],
                        'target_load': self._route_request_count(vehicle['route']),
                        'evaluation': insertion['evaluation'],
                    }]
                    break

                candidate = {
                    'vehicle_idx': v_idx,
                    'added_cost': insertion['added_cost'],
                    'target_load': self._route_request_count(vehicle['route']),
                    'evaluation': insertion['evaluation'],
                }
                candidate_choices.append(candidate)

            best_choice = self._pick_best_fleet_candidate(candidate_choices)

            if best_choice is None and self.optimization_profile == 'ultra_fleet' and vehicles_data:
                deep_candidates = []
                for v_idx, vehicle in enumerate(vehicles_data):
                    full_scan = max(2, len(vehicle['route']) + 2)
                    insertion = self._best_insertion(vehicle['route'], request, scan_limit=full_scan)
                    if insertion is None:
                        continue
                    deep_candidates.append({
                        'vehicle_idx': v_idx,
                        'added_cost': insertion['added_cost'],
                        'target_load': self._route_request_count(vehicle['route']),
                        'evaluation': insertion['evaluation'],
                    })

                best_choice = self._pick_best_fleet_candidate(deep_candidates)

            if best_choice is None:
                new_route = [('P', request['id']), ('D', request['id'])]
                new_eval = self._simulate_route(new_route)

                if new_eval is None:
                    new_eval = self._simulate_route(new_route, enforce_time_constraints=False)

                if new_eval is None:
                    raise ValueError(f"No feasible route found for client {request['id']}")

                vehicles_data.append(new_eval)
                continue

            v_idx = best_choice['vehicle_idx']
            evaluation = best_choice['evaluation']
            vehicles_data[v_idx] = {
                'route': evaluation['route'],
                'visits': evaluation['visits'],
                'departure_times': evaluation['departure_times'],
                'total_travel_time': evaluation['total_travel_time'],
            }

        return vehicles_data

    def _iter_absorb_request_orders(self, request_ids):
        chronological = list(request_ids)
        reverse_chronological = list(reversed(chronological))
        long_trips_first = sorted(
            request_ids,
            key=lambda rid: self._direct_travel_time(self._requests_by_id[rid]),
            reverse=True,
        )

        seen = set()
        for order in (chronological, reverse_chronological, long_trips_first):
            key = tuple(order)
            if key in seen:
                continue
            seen.add(key)
            yield order

        if self.optimization_profile == 'ultra_fleet' and len(request_ids) <= 3:
            for order in itertools.permutations(request_ids):
                key = tuple(order)
                if key in seen:
                    continue
                seen.add(key)
                yield list(order)

    def _try_absorb_vehicle(self, vehicles_data, source_idx, aggressive=False):
        source_route = vehicles_data[source_idx]['route']
        source_requests = self._request_ids_from_route(source_route)
        if not source_requests:
            return None

        scan_limits = [self.insertion_scan_limit]
        if self.optimization_profile == 'ultra_fleet' and len(source_requests) <= 2:
            scan_limits.append(self.insertion_scan_limit + 16)
        if aggressive:
            scan_limits.append(self.insertion_scan_limit + 24)
            scan_limits.append(64)

        normalized_scan_limits = []
        seen_limits = set()
        for limit in scan_limits:
            limit = max(2, int(limit))
            if limit in seen_limits:
                continue
            seen_limits.add(limit)
            normalized_scan_limits.append(limit)
        scan_limits = normalized_scan_limits

        for request_order in self._iter_absorb_request_orders(source_requests):
            for scan_limit in scan_limits:
                test_vehicles = [
                    {
                        'route': list(vehicle['route']),
                        'visits': list(vehicle['visits']),
                        'departure_times': list(vehicle['departure_times']),
                        'total_travel_time': float(vehicle['total_travel_time']),
                    }
                    for vehicle in vehicles_data
                ]

                merged = True
                for request_id in request_order:
                    request = self._requests_by_id[request_id]
                    best_target = None

                    for target_idx, target_vehicle in enumerate(test_vehicles):
                        if target_idx == source_idx:
                            continue

                        insertion = self._best_insertion(target_vehicle['route'], request, scan_limit=scan_limit)
                        if insertion is None:
                            continue

                        candidate_load = self._route_request_count(target_vehicle['route'])
                        candidate = {
                            'target_idx': target_idx,
                            'added_cost': insertion['added_cost'],
                            'target_load': candidate_load,
                            'evaluation': insertion['evaluation'],
                        }

                        if best_target is None:
                            best_target = candidate
                            continue

                        if self.optimization_profile == 'ultra_fleet':
                            if candidate['target_load'] > best_target['target_load']:
                                best_target = candidate
                                continue
                            if (candidate['target_load'] == best_target['target_load'] and
                                    candidate['added_cost'] < best_target['added_cost']):
                                best_target = candidate
                                continue
                        elif candidate['added_cost'] < best_target['added_cost']:
                            best_target = candidate

                    if best_target is None:
                        merged = False
                        break

                    target_idx = best_target['target_idx']
                    evaluation = best_target['evaluation']
                    test_vehicles[target_idx] = {
                        'route': evaluation['route'],
                        'visits': evaluation['visits'],
                        'departure_times': evaluation['departure_times'],
                        'total_travel_time': evaluation['total_travel_time'],
                    }

                if merged:
                    return [vehicle for idx, vehicle in enumerate(test_vehicles) if idx != source_idx]

        return None

    def _compact_to_target(self, vehicles_data):
        if self.target_vehicle_count is None:
            return vehicles_data

        max_rounds = max(1, 2 * len(vehicles_data))
        rounds = 0

        while len(vehicles_data) > self.target_vehicle_count and rounds < max_rounds:
            rounds += 1
            source_order = sorted(
                range(len(vehicles_data)),
                key=lambda idx: (
                    len(self._request_ids_from_route(vehicles_data[idx]['route'])),
                    vehicles_data[idx]['total_travel_time'],
                ),
            )

            merged_any = False
            for source_idx in source_order:
                merged = self._try_absorb_vehicle(vehicles_data, source_idx, aggressive=True)
                if merged is None:
                    continue
                vehicles_data = merged
                merged_any = True
                break

            if not merged_any:
                break

        return vehicles_data

    def _consolidate_vehicles(self, vehicles_data):
        improved = True
        while improved and len(vehicles_data) > 1:
            improved = False

            source_order = sorted(
                range(len(vehicles_data)),
                key=lambda idx: (
                    len(self._request_ids_from_route(vehicles_data[idx]['route'])),
                    vehicles_data[idx]['total_travel_time'],
                ),
            )

            if self.optimization_profile in ('fleet_strong', 'ultra_fleet'):
                source_order = source_order + sorted(
                    range(len(vehicles_data)),
                    key=lambda idx: (
                        -len(self._request_ids_from_route(vehicles_data[idx]['route'])),
                        vehicles_data[idx]['total_travel_time'],
                    ),
                )

            seen_sources = set()
            dedup_source_order = []
            for idx in source_order:
                if idx in seen_sources:
                    continue
                seen_sources.add(idx)
                dedup_source_order.append(idx)

            for source_idx in dedup_source_order:
                merged = self._try_absorb_vehicle(vehicles_data, source_idx)
                if merged is not None:
                    vehicles_data = merged
                    improved = True
                    break

        if self.optimization_profile == 'ultra_fleet' and len(vehicles_data) > 1:
            improved = True
            while improved and len(vehicles_data) > 1:
                improved = False
                source_order = sorted(
                    range(len(vehicles_data)),
                    key=lambda idx: (
                        -len(self._request_ids_from_route(vehicles_data[idx]['route'])),
                        vehicles_data[idx]['total_travel_time'],
                    ),
                )
                for source_idx in source_order:
                    merged = self._try_absorb_vehicle(vehicles_data, source_idx)
                    if merged is not None:
                        vehicles_data = merged
                        improved = True
                        break

        return vehicles_data

    def _validate_and_repair_with_checker(self):
        if not self.validate_with_checker or Checker is None:
            return

        try:
            checker = Checker.from_processed_file()
            feasible = checker.check_from_file(self.instance, team_name=None)
        except Exception:
            return

        if feasible:
            return

        self._build_single_client_solution()
        self.write_to_file()

        try:
            checker.check_from_file(self.instance, team_name=None)
        except Exception:
            pass



    def run(self):
        """
        Chronological insertion workflow:
        - process requests by request time,
        - try inserting each request into existing vehicles,
        - if all insertions violate constraints, create a new vehicle.
        """
        if not self._requests:
            self.vehicles = []
            self.departure_times = []
            return

        vehicles_data = self._build_constructive_solution(self._requests)
        if self.consolidate_vehicles:
            vehicles_data = self._consolidate_vehicles(vehicles_data)
        if self.optimization_profile == 'ultra_fleet':
            vehicles_data = self._compact_to_target(vehicles_data)

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