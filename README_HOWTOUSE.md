# Project Guide — Hackathon M2C

This document explains what the project does, how to run it, and how the optimization methodology works.

## 1) Project goal

The project solves a ride-pooling / dispatch challenge:

- predict demand and travel times for 2024,
- build vehicle routes for multiple hidden benchmark instances,
- minimize fleet usage and travel time while respecting feasibility constraints,
- evaluate solutions with the provided compiled checker.

Main entry point: `executable.py`.

---

## 2) Repository structure

- `executable.py`: global pipeline (prediction + optimization + checker evaluation).
- `data.py`: historical data loading, cleaning, OD-time aggregation.
- `prediction.py`: Random Forest demand and travel-time prediction.
- `instance.py`: instance parsing/generation and solution export helpers.
- `request.py`: request model.
- `optimisation.py`: routing heuristic and consolidation logic.
- `report_utils.py`: parses and rewrites checker reports in compact summary format.
- `test_single.py`: quick test on one internal instance.
- `data/`: historical CSV and prediction files.
- `instances/`: local text instances.
- `solutions/`: generated solution files consumed by the checker.
- `reports/`: checker output reports.

---

## 3) Methodology summary

### A. Data and prediction

1. Read and clean trip history (2019–2023).
2. Aggregate into hourly OD observations:
	- average travel time,
	- number of trips.
3. Train two Random Forest models:
	- trip count predictor,
	- travel time predictor.
4. Predict 2024 OD observations from `data/observations_to_predict.csv`.

### B. Vehicle routing heuristic

For each checker instance:

1. Requests are sorted by request time.
2. For each request, the solver tries to insert pickup/dropoff into existing routes.
3. If no feasible insertion exists, a new vehicle is created.
4. A consolidation phase tries to absorb one vehicle into others to reduce fleet size.

### C. Feasibility rules enforced in simulation

- Capacity: max 3 clients onboard per vehicle.
- Pickup waiting bound:
  waiting_time <= waiting_time_factor × direct_travel_time.
- Ride time bound:
  actual_ride_time <= 2 × direct_travel_time.
- Pickup must happen before its corresponding dropoff.
- Routes start/end at depot and must finish with no onboard passenger.

### D. Safety fallback

If checker validation fails, solver falls back to a guaranteed simple plan
(single-client route per vehicle), writes it, and checks again.

---

## 4) Optimization profiles

Defined in `optimisation.py`:

- `default`
- `fleet`
- `fleet_strong`
- `ultra_fleet` (default in current code)

Differences mainly affect insertion scan depth, merge aggressiveness,
and fleet-compaction behavior.

---

## 5) Environment setup

Important: use Python 3.11 (the checker binary is version-sensitive).

### Install dependencies

```bash
pip install pandas numpy scikit-learn requests flask
```

### Checker setup

You need the platform-compatible checker binary in the project root:

- Windows: `checker.pyd`
- Linux/macOS: `checker.so`

This repository already contains `checker.pyd` for Windows.

---

## 6) How to run

### Full benchmark loop

```bash
python executable.py
```

What it does:

1. Loads and aggregates historical data,
2. predicts 2024 OD values,
3. loads all hidden internal instances from the checker,
4. runs optimization for each instance,
5. checks each solution and writes reports.

### Single-instance quick test

```bash
python test_single.py
```

---

## 7) Inputs and outputs

### Inputs

- `data/Data_2019-2023.csv`
- `data/observations_to_predict.csv`
- hidden checker instances (loaded via checker API)

### Outputs

- `data/predicted_observations.csv`
- `solutions/<instance_name>`
- `reports/report_<instance_name>`
- optional local backup reports: `reports/local_<instance_name>.txt`

---

