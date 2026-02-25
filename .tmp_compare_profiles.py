import io
from contextlib import redirect_stdout
from checker import Checker
from instance import Instance
from optimisation import Optimisation

checker = Checker.from_processed_file()
instance_names = sorted(checker._INTERNAL_INSTANCES.keys())[:3]

for profile in ['fleet_strong', 'ultra_fleet']:
    feasible = 0
    vehicles = 0
    for name in instance_names:
        instance = Instance.from_string(checker.get_instance_data(name), name)
        with redirect_stdout(io.StringIO()):
            opt = Optimisation(instance, optimization_profile=profile)
            ok = checker.check_from_file(instance, team_name=None)
        feasible += int(bool(ok))
        vehicles += len(opt.vehicles)
    print(f'{profile}: feasible={feasible}/{len(instance_names)} vehicles={vehicles}')
