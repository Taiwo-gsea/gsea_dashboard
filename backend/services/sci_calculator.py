"""
GSEA Dashboard - SCI Calculation Engine
=========================================
Implements the Software Carbon Intensity (SCI) formula per ISO/IEC 21031:
    SCI = (E × I + M) / R

Where:
    E  = Energy consumed by the software system (kWh)
    I  = Location-based marginal carbon intensity (gCO₂eq/kWh)
    M  = Embodied carbon of hardware (gCO₂eq)
    R  = Functional unit (e.g., per user, per API call, per hour)

Reference: Green Software Foundation, SOGS 2023; ISO/IEC 21031 v1.1.0
"""

from dataclasses import dataclass, field
from typing import Optional


# ── Carbon intensity defaults by region (gCO₂eq/kWh) ──────────────────────
# Source: Electricity Maps 2024 regional averages
CARBON_INTENSITY_DEFAULTS: dict[str, float] = {
    "UK":        233.0,
    "EU_avg":    295.0,
    "US_avg":    386.0,
    "DE":        350.0,
    "FR":        56.0,    # Nuclear-heavy grid
    "NO":        26.0,    # Hydro-heavy grid
    "IN":        708.0,
    "CN":        555.0,
    "global":    442.0,   # IEA world average 2023
}

# ── Embodied carbon defaults (gCO₂eq) ─────────────────────────────────────
# Source: Guldner et al. 2024; Freitag et al. 2021
EMBODIED_CARBON_DEFAULTS: dict[str, float] = {
    "laptop":           300_000.0,    # ~300 kg over 4yr lifespan → prorated
    "desktop":          500_000.0,
    "server_rack":    2_000_000.0,
    "cloud_vm_small":    10_000.0,    # Prorated share per VM
    "cloud_vm_large":    40_000.0,
    "smartphone":        70_000.0,
}


@dataclass
class SCIComponents:
    """
    Container for all SCI input components.
    All values are validated on creation.
    """
    energy_kwh: float           # E - Energy in kilowatt-hours
    carbon_intensity: float     # I - Grid carbon intensity (gCO₂eq/kWh)
    embodied_carbon: float      # M - Embodied carbon (gCO₂eq)
    functional_unit: float      # R - Functional unit denominator (must be > 0)
    functional_unit_label: str = "request"  # Human-readable unit label

    # Optional metadata for reporting
    region: Optional[str] = None
    hardware_type: Optional[str] = None
    measurement_period_hours: Optional[float] = None
    software_component: Optional[str] = None
    deployment_env: Optional[str] = None
    notes: Optional[str] = None

    def __post_init__(self):
        """Validate all inputs after initialisation."""
        if self.energy_kwh < 0:
            raise ValueError(f"Energy (E) must be ≥ 0, got {self.energy_kwh}")
        if self.carbon_intensity < 0:
            raise ValueError(f"Carbon intensity (I) must be ≥ 0, got {self.carbon_intensity}")
        if self.embodied_carbon < 0:
            raise ValueError(f"Embodied carbon (M) must be ≥ 0, got {self.embodied_carbon}")
        if self.functional_unit <= 0:
            raise ValueError(f"Functional unit (R) must be > 0, got {self.functional_unit}")


@dataclass
class SCIResult:
    """
    Full SCI calculation result with breakdown and metadata.
    Designed for direct serialisation to JSON for the FastAPI layer.
    """
    sci_score: float                    # Final SCI score (gCO₂eq/R)
    operational_carbon: float           # E × I component (gCO₂eq)
    embodied_carbon: float              # M component (gCO₂eq)
    total_carbon: float                 # (E × I) + M (gCO₂eq)
    functional_unit: float              # R value
    functional_unit_label: str          # R unit label
    components: SCIComponents           # Original inputs

    # Normalised breakdown (percentage of total carbon)
    operational_pct: float = field(init=False)
    embodied_pct: float = field(init=False)

    def __post_init__(self):
        if self.total_carbon > 0:
            self.operational_pct = round((self.operational_carbon / self.total_carbon) * 100, 2)
            self.embodied_pct = round((self.embodied_carbon / self.total_carbon) * 100, 2)
        else:
            self.operational_pct = 0.0
            self.embodied_pct = 0.0

    def to_dict(self) -> dict:
        """Serialise to dictionary for API responses and database storage."""
        return {
            "sci_score": round(self.sci_score, 6),
            "operational_carbon_gco2eq": round(self.operational_carbon, 4),
            "embodied_carbon_gco2eq": round(self.embodied_carbon, 4),
            "total_carbon_gco2eq": round(self.total_carbon, 4),
            "functional_unit": self.functional_unit,
            "functional_unit_label": self.functional_unit_label,
            "operational_pct": self.operational_pct,
            "embodied_pct": self.embodied_pct,
            "inputs": {
                "energy_kwh": self.components.energy_kwh,
                "carbon_intensity_gco2eq_kwh": self.components.carbon_intensity,
                "embodied_carbon_gco2eq": self.components.embodied_carbon,
                "region": self.components.region,
                "hardware_type": self.components.hardware_type,
                "software_component": self.components.software_component,
                "deployment_env": self.components.deployment_env,
                "notes": self.components.notes,
            }
        }

    def get_rating(self) -> str:
        """
        Return a qualitative SCI rating band.
        These thresholds are illustrative — calibrate against real benchmarks
        from Kanso et al. 2024 and GMT results in dissertation evaluation.
        """
        if self.sci_score < 10:
            return "Excellent"
        elif self.sci_score < 50:
            return "Good"
        elif self.sci_score < 200:
            return "Acceptable"
        elif self.sci_score < 500:
            return "Poor"
        else:
            return "Critical"


class SCICalculator:
    """
    Core SCI calculation engine.

    Usage:
        calc = SCICalculator()
        components = SCIComponents(
            energy_kwh=0.5,
            carbon_intensity=233.0,
            embodied_carbon=10000.0,
            functional_unit=1000.0,
            functional_unit_label="API call"
        )
        result = calc.calculate(components)
        print(result.sci_score)  # gCO₂eq per API call
    """

    def calculate(self, components: SCIComponents) -> SCIResult:
        """
        Apply ISO/IEC 21031 SCI formula:
            SCI = (E × I + M) / R

        Args:
            components: Validated SCIComponents instance

        Returns:
            SCIResult with full breakdown
        """
        operational_carbon = components.energy_kwh * components.carbon_intensity
        total_carbon = operational_carbon + components.embodied_carbon
        sci_score = total_carbon / components.functional_unit

        return SCIResult(
            sci_score=sci_score,
            operational_carbon=operational_carbon,
            embodied_carbon=components.embodied_carbon,
            total_carbon=total_carbon,
            functional_unit=components.functional_unit,
            functional_unit_label=components.functional_unit_label,
            components=components,
        )

    def calculate_from_proxy_metrics(
        self,
        cpu_percent: float,
        memory_gb: float,
        duration_hours: float,
        region: str = "UK",
        hardware_type: str = "cloud_vm_small",
        functional_unit: float = 1.0,
        functional_unit_label: str = "hour",
        tdp_watts: float = 65.0,
    ) -> SCIResult:
        """
        Estimate SCI from proxy metrics (CPU%, memory, duration).

        This is the proxy-measurement approach when direct energy meters
        (e.g., RAPL) are unavailable — aligned with Guldner et al. 2024.

        Energy estimation formula:
            E = TDP × CPU_utilisation × duration

        Args:
            cpu_percent:        Average CPU utilisation (0–100)
            memory_gb:          Average memory in use (GB)
            duration_hours:     Measurement period in hours
            region:             Grid region key from CARBON_INTENSITY_DEFAULTS
            hardware_type:      Hardware key from EMBODIED_CARBON_DEFAULTS
            functional_unit:    R denominator value
            functional_unit_label: R unit description
            tdp_watts:          Thermal Design Power of the CPU (Watts)

        Returns:
            SCIResult with proxy-estimated values
        """
        cpu_fraction = max(0.0, min(cpu_percent / 100.0, 1.0))
        # Memory power: Guldner et al. 2024, Table 2 — DRAM power = 0.3725 W/GB
        MEMORY_POWER_W_PER_GB = 0.3725
        memory_power_w = memory_gb * MEMORY_POWER_W_PER_GB
        energy_kwh = ((tdp_watts * cpu_fraction + memory_power_w) * duration_hours) / 1000.0

        carbon_intensity = CARBON_INTENSITY_DEFAULTS.get(region, CARBON_INTENSITY_DEFAULTS["global"])
        embodied_carbon = EMBODIED_CARBON_DEFAULTS.get(hardware_type, EMBODIED_CARBON_DEFAULTS["cloud_vm_small"])

        # Prorate embodied carbon for measurement period
        HARDWARE_LIFESPAN_HOURS = 4 * 365 * 24  # GSF SCI spec v1.1.0 §4.3 — 4-year server lifespan (35,040h)
        prorated_embodied = embodied_carbon * (duration_hours / HARDWARE_LIFESPAN_HOURS)

        components = SCIComponents(
            energy_kwh=energy_kwh,
            carbon_intensity=carbon_intensity,
            embodied_carbon=prorated_embodied,
            functional_unit=functional_unit,
            functional_unit_label=functional_unit_label,
            region=region,
            hardware_type=hardware_type,
            measurement_period_hours=duration_hours,
        )

        return self.calculate(components)

    def compare_configurations(
        self,
        configs: list[SCIComponents],
        labels: list[str],
    ) -> list[dict]:
        """
        Compare SCI scores across multiple configurations.
        Used for the Comparative Baseline View feature.

        Returns list of result dicts with labels, sorted by SCI score ascending.
        """
        if len(configs) != len(labels):
            raise ValueError("configs and labels must have equal length")

        results = []
        for config, label in zip(configs, labels):
            result = self.calculate(config)
            row = result.to_dict()
            row["label"] = label
            row["rating"] = result.get_rating()
            results.append(row)

        return sorted(results, key=lambda x: x["sci_score"])


# ── Module-level convenience instance ──────────────────────────────────────
sci_calculator = SCICalculator()
