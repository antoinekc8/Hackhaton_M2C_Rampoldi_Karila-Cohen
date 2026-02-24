import os
import re


def _safe_search(pattern: str, text: str):
    match = re.search(pattern, text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def parse_report_metrics(text: str):
    vehicles = _safe_search(r"Total Vehicles (?:in Solution|Used):\s*([0-9]+)", text)
    vehicles_used = int(vehicles) if vehicles is not None else None

    status = _safe_search(r"VERDICT:\s*(FEASIBLE|INFEASIBLE)", text)
    if status is None:
        status = _safe_search(r"Status:\s*(FEASIBLE|INFEASIBLE)", text)
    if status is None:
        fail_found = re.search(r"\|\s*FAIL\b", text) is not None
        status = "INFEASIBLE" if fail_found else "FEASIBLE"

    total_time = _safe_search(r"(?:TOTAL TIME|Total Fleet Travel Time):\s*([0-9]+\.?[0-9]*)", text)
    if total_time is None:
        per_vehicle_times = [float(x) for x in re.findall(r"Total Travel Time:\s*([0-9]+\.?[0-9]*)", text)]
        if per_vehicle_times:
            total_time = f"{sum(per_vehicle_times):.2f}"

    total_time_value = float(total_time) if total_time is not None else None
    return {
        "status": status,
        "vehicles": vehicles_used,
        "total_time": total_time_value,
    }


def format_hackathon_summary(instance_name: str, status: str, vehicles: int, total_time: float):
    status_value = status if status is not None else "UNKNOWN"
    vehicles_value = str(vehicles) if vehicles is not None else "N/A"
    total_time_str = f"{total_time:.2f} min" if total_time is not None else "N/A"

    return (
        "============================================================\n"
        "HACKATHON EVALUATION SUMMARY\n"
        "------------------------------------------------------------\n"
        f"Instance Name:           {instance_name}\n"
        f"Status:                  {status_value}\n"
        "------------------------------------------------------------\n"
        f"Total Vehicles Used:     {vehicles_value}\n"
        f"Total Fleet Travel Time: {total_time_str}\n"
        "============================================================\n"
    )


def rewrite_report_as_summary(report_path: str, instance_name: str = None):
    if not os.path.exists(report_path):
        return False

    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()

    metrics = parse_report_metrics(content)
    name = instance_name if instance_name is not None else os.path.basename(report_path).replace("report_", "")
    summary = format_hackathon_summary(name, metrics["status"], metrics["vehicles"], metrics["total_time"])

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(summary)

    return True
