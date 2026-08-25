"""
GSEA Dashboard - Sample Data Generator
========================================
Generates realistic sample CSV files for development, testing,
and dashboard demonstrations.

Produces:
  - gmt_sample.csv        — Green Metrics Tool format
  - codecarbon_sample.csv — CodeCarbon format
  - sci_history.csv       — Historical SCI scores for trend chart

Usage:
    python scripts/generate_sample_data.py
"""

import csv
import random
import math
from datetime import datetime, timedelta
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "sample"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

random.seed(42)


def _timestamp_series(start: datetime, n: int, interval_minutes: int = 5) -> list[str]:
    return [(start + timedelta(minutes=i * interval_minutes)).isoformat() for i in range(n)]


def _sine_wave(n: int, base: float, amplitude: float, periods: float = 2.0, noise: float = 0.0) -> list[float]:
    """Generate a sine-wave signal with optional Gaussian noise."""
    values = []
    for i in range(n):
        t = (i / n) * periods * 2 * math.pi
        val = base + amplitude * math.sin(t) + random.gauss(0, noise)
        values.append(round(max(0.0, val), 4))
    return values


def generate_gmt_csv(n_rows: int = 288, filename: str = "gmt_sample.csv") -> Path:
    """
    Generate a Green Metrics Tool (GMT) style CSV.
    288 rows = 24h at 5-min intervals.
    """
    start = datetime.now() - timedelta(hours=24)
    timestamps = _timestamp_series(start, n_rows, interval_minutes=5)

    cpu = _sine_wave(n_rows, base=38, amplitude=25, periods=3, noise=4)
    memory_mb = _sine_wave(n_rows, base=2048, amplitude=512, periods=1.5, noise=64)
    network_io_kb = [round(max(0, c * 8 + random.expovariate(0.05)), 2) for c in cpu]
    # Simulate energy from CPU proxy
    energy_kwh = [round((c / 100) * 65 * (5 / 60) / 1000, 8) for c in cpu]

    output_path = OUTPUT_DIR / filename
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "timestamp", "cpu_percent", "memory_mb", "network_io_kb", "energy_kwh",
            "container_name", "deployment_env"
        ])
        writer.writeheader()
        for i in range(n_rows):
            writer.writerow({
                "timestamp": timestamps[i],
                "cpu_percent": cpu[i],
                "memory_mb": memory_mb[i],
                "network_io_kb": network_io_kb[i],
                "energy_kwh": energy_kwh[i],
                "container_name": random.choice(["web-frontend", "api-server", "ml-inference"]),
                "deployment_env": "cloud",
            })

    print(f"[GMT]       {output_path} ({n_rows} rows)")
    return output_path


def generate_codecarbon_csv(n_rows: int = 50, filename: str = "codecarbon_sample.csv") -> Path:
    """
    Generate a CodeCarbon emissions CSV.
    Simulates multiple Python script runs over several days.
    """
    start = datetime.now() - timedelta(days=7)
    output_path = OUTPUT_DIR / filename

    with open(output_path, "w", newline="") as f:
        fieldnames = [
            "timestamp", "project_name", "run_id", "duration",
            "emissions", "emissions_rate", "cpu_power", "gpu_power", "ram_power",
            "cpu_energy", "gpu_energy", "ram_energy", "energy_consumed",
            "country_name", "country_iso_code", "region",
            "cloud_provider", "cloud_region", "os", "python_version",
            "cpu_count", "cpu_model", "gpu_count", "gpu_model", "ram_total_size",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for i in range(n_rows):
            ts = start + timedelta(hours=i * 3.5)
            duration = round(random.uniform(30, 3600), 2)
            cpu_power = round(random.uniform(15, 85), 2)
            gpu_power = round(random.uniform(0, 5), 2)      # Low GPU for typical ML prototype
            ram_power = round(random.uniform(2, 8), 2)
            cpu_energy = round((cpu_power * duration) / (3600 * 1000), 8)
            gpu_energy = round((gpu_power * duration) / (3600 * 1000), 8)
            ram_energy = round((ram_power * duration) / (3600 * 1000), 8)
            energy_consumed = round(cpu_energy + gpu_energy + ram_energy, 8)
            emissions = round(energy_consumed * 0.233, 10)  # UK grid

            writer.writerow({
                "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S"),
                "project_name": "gsea_dashboard",
                "run_id": f"run_{i:04d}",
                "duration": duration,
                "emissions": emissions,
                "emissions_rate": round(emissions / duration, 12) if duration > 0 else 0,
                "cpu_power": cpu_power,
                "gpu_power": gpu_power,
                "ram_power": ram_power,
                "cpu_energy": cpu_energy,
                "gpu_energy": gpu_energy,
                "ram_energy": ram_energy,
                "energy_consumed": energy_consumed,
                "country_name": "United Kingdom",
                "country_iso_code": "GBR",
                "region": "england",
                "cloud_provider": "gcp",
                "cloud_region": "europe-west2",
                "os": "Linux-5.15",
                "python_version": "3.12.0",
                "cpu_count": 4,
                "cpu_model": "Intel Xeon E5-2670",
                "gpu_count": 0,
                "gpu_model": "",
                "ram_total_size": 8.0,
            })

    print(f"[CodeCarbon] {output_path} ({n_rows} rows)")
    return output_path


def generate_sci_history_csv(n_rows: int = 60, filename: str = "sci_history.csv") -> Path:
    """
    Generate a historical SCI score CSV for trend analysis.
    Simulates improving SCI over time (as optimisations are applied) —
    this matches the dissertation narrative of demonstrating improvement.
    """
    start = datetime.now() - timedelta(days=60)
    output_path = OUTPUT_DIR / filename

    # SCI trend: starts high, gradually improves (optimisation story)
    base_sci = 25.0
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "date", "software_component", "sci_score", "energy_kwh",
            "carbon_intensity", "embodied_carbon", "functional_unit",
            "deployment_env", "region", "notes"
        ])
        writer.writeheader()

        for i in range(n_rows):
            date = start + timedelta(days=i)
            # Gradual improvement with weekly cycles and noise
            improvement = (i / n_rows) * 15.0
            weekly_cycle = 2.0 * math.sin(i * 2 * math.pi / 7)
            noise = random.gauss(0, 1.5)
            sci = round(max(2.0, base_sci - improvement + weekly_cycle + noise), 4)

            energy = round(random.uniform(0.1, 0.8), 5)
            ci = random.choice([233.0, 233.0, 56.0, 295.0])  # UK mostly

            writer.writerow({
                "date": date.strftime("%Y-%m-%d"),
                "software_component": random.choice(["api-server", "web-frontend", "ml-pipeline"]),
                "sci_score": sci,
                "energy_kwh": energy,
                "carbon_intensity": ci,
                "embodied_carbon": round(random.uniform(5000, 15000), 2),
                "functional_unit": 1000,
                "deployment_env": "cloud",
                "region": "UK" if ci == 233.0 else ("FR" if ci == 56.0 else "EU_avg"),
                "notes": f"Iteration {i+1}",
            })

    print(f"[SCI History] {output_path} ({n_rows} rows)")
    return output_path


def generate_all() -> None:
    """Generate all sample data files."""
    print(f"\nGenerating sample data in: {OUTPUT_DIR}\n")
    generate_gmt_csv()
    generate_codecarbon_csv()
    generate_sci_history_csv()
    print("\nDone. Sample data ready for dashboard demonstration.\n")


if __name__ == "__main__":
    generate_all()
