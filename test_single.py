from checker import Checker
from instance import Instance
from optimisation import Optimisation

# Initialize checker
checker = Checker.from_processed_file()

# Test on single instance
f_name = 'instance_100_12_2024-1-3'
print(f'Testing {f_name}...')

# Get instance data
instance_content = checker.get_instance_data(f_name)

# Create instance
instance = Instance.from_string(instance_content, f_name)

# Run optimizer
opt = Optimisation(instance)

# Check solution
result = checker.check_from_file(instance, team_name='TEST')

print(f'Result: {result}')
