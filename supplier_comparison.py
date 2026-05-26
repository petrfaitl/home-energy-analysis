"""
Supplier Comparison Analysis (PV + 2 EVs)
=========================================

Compares annual electricity + gas + DC charging costs for the current PV array
with 2 EVs, with and without a 13.8 kWh battery.

Easy to update supplier rates in the SUPPLIERS list below.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from home_energy_options import build_model_data, ModelData

OUTPUT_DIR = Path("analysis_files")
OUTPUT_XLSX = OUTPUT_DIR / "supplier_comparison.xlsx"
OUTPUT_MARKDOWN = OUTPUT_DIR / "supplier_comparison_summary.md"

# =============================================================================
# CONFIGURATION
# =============================================================================
BATTERY_KWH = 13.8

EV_MILEAGE = {"Tesla": 26_000, "MG": 13_000}
HOME_CHARGE_PCTS = {"Tesla": 0.65, "MG": 0.50}
KWH_PER_KM = {"Tesla": 0.153, "MG": 0.190}
ROUND_TRIP_EFFICIENCY = 0.90

# =============================================================================
# FULL SUPPLIER DATA (all rows from your table)
# =============================================================================
SUPPLIERS = [
    # Mercury
    {
        "supplier": "Mercury",
        "tariff": "standard usage",
        "plan_name": "Mercury - standard usage",
        "peak_rate": 0.37,
        "offpeak_rate": 0.37,
        "night_rate": 0.37,
        "daily_charge": 1.380,
        "export_rate": 0.120,
        "public_dc_rate": 0.85,
        "gas": True,
        "bottle_charge_per_year": 253.6,
        "bottle_rental_per_year": 101.4,
        "dual_fuel_discount": 0.05,
        "rebate": 500,
        "low_usage_threshold_kwh": None,
        "night_hours": None,
    },
    # Octopus Power - Fixed
    {
        "supplier": "Octopus Power - Fixed",
        "tariff": "low usage",
        "plan_name": "Octopus Power - Fixed - low usage",
        "peak_rate": 0.36,
        "offpeak_rate": 0.29,
        "night_rate": 0.18,
        "daily_charge": 1.380,
        "export_rate": 0.130,
        "public_dc_rate": 0.85,
        "gas": False,
        "bottle_charge_per_year": 0,
        "bottle_rental_per_year": 0,
        "dual_fuel_discount": 0.0,
        "rebate": 0,
        "low_usage_threshold_kwh": None,
        "night_hours": (23, 7),
    },
    # Octopus Power Flexi
    {
        "supplier": "Octopus Power Flexi",
        "tariff": "standard usage",
        "plan_name": "Octopus Power Flexi - standard usage",
        "peak_rate": 0.30,
        "offpeak_rate": 0.23,
        "night_rate": 0.15,
        "daily_charge": 2.445,
        "export_rate": 0.130,
        "public_dc_rate": 0.85,
        "gas": False,
        "bottle_charge_per_year": 0,
        "bottle_rental_per_year": 0,
        "dual_fuel_discount": 0.0,
        "rebate": 0,
        "low_usage_threshold_kwh": None,
        "night_hours": (23, 7),
    },
    # Genesis Energy EV - standard
    {
        "supplier": "Genesis Energy EV",
        "tariff": "standard usage",
        "plan_name": "Genesis Energy EV - standard usage",
        "peak_rate": 0.34,
        "offpeak_rate": 0.17,
        "night_rate": 0.17,
        "daily_charge": 2.129,
        "export_rate": 0.144,
        "public_dc_rate": 0.34,
        "gas": True,
        "bottle_charge_per_year": 345.9,
        "bottle_rental_per_year": 69.00,
        "dual_fuel_discount": 0.05,
        "rebate": 0,
        "low_usage_threshold_kwh": 8000,
        "night_hours": (21, 7),
    },
    # Genesis Energy EV - low usage
    {
        "supplier": "Genesis Energy EV",
        "tariff": "low usage",
        "plan_name": "Genesis Energy EV - low usage",
        "peak_rate": 0.39,
        "offpeak_rate": 0.19,
        "night_rate": 0.19,
        "daily_charge": 1.035,
        "export_rate": 0.144,
        "public_dc_rate": 0.39,
        "gas": True,
        "bottle_charge_per_year": 345.9,
        "bottle_rental_per_year": 69.00,
        "dual_fuel_discount": 0.05,
        "rebate": 0,
        "low_usage_threshold_kwh": 8000,
        "night_hours": (21, 7),
    },
    # Electric Kiwi Move Master
    {
        "supplier": "Electric Kiwi",
        "tariff": "standard usage",
        "plan_name": "Electric Kiwi Move Master - standard usage",
        "peak_rate": 0.39,
        "offpeak_rate": 0.27,
        "night_rate": 0.20,
        "daily_charge": 1.930,
        "export_rate": 0.144,
        "public_dc_rate": 0.85,
        "gas": False,
        "bottle_charge_per_year": 0,
        "bottle_rental_per_year": 0,
        "dual_fuel_discount": 0.0,
        "rebate": 0,
        "low_usage_threshold_kwh": None,
        "night_hours": (23, 7),
    },
    # Contact Good Nights - standard
    {
        "supplier": "Contact",
        "tariff": "standard usage",
        "plan_name": "Contact Good Nights - standard usage",
        "peak_rate": 0.29,
        "offpeak_rate": 0.29,
        "night_rate": 0.00,
        "daily_charge": 2.611,
        "export_rate": 0.120,
        "public_dc_rate": 0.85,
        "gas": True,
        "bottle_charge_per_year": 0,
        "bottle_rental_per_year": 0,
        "dual_fuel_discount": 0.0,
        "rebate": 0,
        "low_usage_threshold_kwh": None,
        "night_hours": (21, 0),
    },
    # Contact Good Nights - low usage
    {
        "supplier": "Contact",
        "tariff": "low usage",
        "plan_name": "Contact Good Nights - low usage",
        "peak_rate": 0.38,
        "offpeak_rate": 0.38,
        "night_rate": 0.00,
        "daily_charge": 1.035,
        "export_rate": 0.120,
        "public_dc_rate": 0.85,
        "gas": True,
        "bottle_charge_per_year": 0,
        "bottle_rental_per_year": 0,
        "dual_fuel_discount": 0.0,
        "rebate": 0,
        "low_usage_threshold_kwh": None,
        "night_hours": (21, 0),
    },
    # Contact EV Charge - standard
    {
        "supplier": "Contact",
        "tariff": "standard usage",
        "plan_name": "Contact EV Charge - standard usage",
        "peak_rate": 0.29,
        "offpeak_rate": 0.29,
        "night_rate": 0.145,
        "daily_charge": 2.663,
        "export_rate": 0.120,
        "public_dc_rate": 0.85,
        "gas": True,
        "bottle_charge_per_year": 0,
        "bottle_rental_per_year": 0,
        "dual_fuel_discount": 0.0,
        "rebate": 0,
        "low_usage_threshold_kwh": None,
        "night_hours": (21, 7),
    },
    # Contact EV Charge - low usage
    {
        "supplier": "Contact",
        "tariff": "low usage",
        "plan_name": "Contact EV Charge - low usage",
        "peak_rate": 0.37,
        "offpeak_rate": 0.37,
        "night_rate": 0.1817,
        "daily_charge": 1.035,
        "export_rate": 0.120,
        "public_dc_rate": 0.85,
        "gas": True,
        "bottle_charge_per_year": 0,
        "bottle_rental_per_year": 0,
        "dual_fuel_discount": 0.0,
        "rebate": 0,
        "low_usage_threshold_kwh": None,
        "night_hours": (21, 7),
    },
    # Ecotricity - low usage
    {
        "supplier": "Ecotricity",
        "tariff": "low usage",
        "plan_name": "Ecotricity - low usage",
        "peak_rate": 0.43,
        "offpeak_rate": 0.2732,
        "night_rate": 0.2732,
        "daily_charge": 1.380,
        "export_rate": 0.155,
        "public_dc_rate": 0.85,
        "gas": True,
        "bottle_charge_per_year": 0,
        "bottle_rental_per_year": 0,
        "dual_fuel_discount": 0.0,
        "rebate": 0,
        "low_usage_threshold_kwh": None,
        "night_hours": (21, 7),
    },
    # Ecotricity - standard usage
    {
        "supplier": "Ecotricity",
        "tariff": "standard usage",
        "plan_name": "Ecotricity - standard usage",
        "peak_rate": 0.38,
        "offpeak_rate": 0.233,
        "night_rate": 0.233,
        "daily_charge": 2.323,
        "export_rate": 0.155,
        "public_dc_rate": 0.85,
        "gas": True,
        "bottle_charge_per_year": 0,
        "bottle_rental_per_year": 0,
        "dual_fuel_discount": 0.0,
        "rebate": 0,
        "low_usage_threshold_kwh": None,
        "night_hours": (21, 7),
    },
    # Ecotricity - wholesale
    {
        "supplier": "Ecotricity",
        "tariff": "wholesale",
        "plan_name": "Ecotricity - wholesale",
        "peak_rate": 0.42,
        "offpeak_rate": 0.2401,
        "night_rate": 0.2401,
        "daily_charge": 1.380,
        "export_rate": 0.137,
        "public_dc_rate": 0.85,
        "gas": True,
        "bottle_charge_per_year": 0,
        "bottle_rental_per_year": 0,
        "dual_fuel_discount": 0.0,
        "rebate": 210,
        "low_usage_threshold_kwh": None,
        "night_hours": (21, 7),
    },
    # Meridian - low usage
    {
        "supplier": "Meridian",
        "tariff": "low usage",
        "plan_name": "Meridian - low usage",
        "peak_rate": 0.32,
        "offpeak_rate": 0.32,
        "night_rate": 0.1715,
        "daily_charge": 0.690,
        "export_rate": 0.14,
        "public_dc_rate": 0.85,
        "gas": False,
        "bottle_charge_per_year": 0,
        "bottle_rental_per_year": 0,
        "dual_fuel_discount": 0.0,
        "rebate": 0,
        "low_usage_threshold_kwh": None,
        "night_hours": (21, 7),
    },
    # Meridian - standard usage
    {
        "supplier": "Meridian",
        "tariff": "standard usage",
        "plan_name": "Meridian - standard usage",
        "peak_rate": 0.27,
        "offpeak_rate": 0.27,
        "night_rate": 0.1179,
        "daily_charge": 1.866,
        "export_rate": 0.14,
        "public_dc_rate": 0.85,
        "gas": False,
        "bottle_charge_per_year": 0,
        "bottle_rental_per_year": 0,
        "dual_fuel_discount": 0.0,
        "rebate": 0,
        "low_usage_threshold_kwh": None,
        "night_hours": (21, 7),
    },
]

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def calculate_annual_ev_energy() -> dict:
    total_home = 0.0
    total_dc = 0.0
    for car in EV_MILEAGE:
        kwh = EV_MILEAGE[car] * KWH_PER_KM[car]
        total_home += kwh * HOME_CHARGE_PCTS[car]
        total_dc += kwh * (1 - HOME_CHARGE_PCTS[car])
    return {"home_kwh": total_home, "dc_kwh": total_dc}


def get_night_mask(model: ModelData, night_hours: tuple | None) -> np.ndarray:
    if night_hours is None:
        return np.zeros(len(model.interval), dtype=bool)
    start, end = night_hours
    hours = model.interval.index.hour
    if start < end:
        return (hours >= start) | (hours < end)
    else:
        return (hours >= start) | (hours < end)


def simulate_battery_dispatch(
    model: ModelData,
    battery_kwh: float,
    night_mask: np.ndarray,
    allow_night_grid_charge: bool = True,
) -> dict:
    """Simple battery model: solar self-consumption + night top-up."""
    if battery_kwh <= 0:
        return {
            "import": model.interval["load"].to_numpy(),
            "export": model.interval["solar"].to_numpy()
            - model.interval["load"].to_numpy(),
        }

    load = model.interval["load"].to_numpy(dtype=float)
    solar = model.interval["solar"].to_numpy(dtype=float)
    net = load - solar

    charge_eff = np.sqrt(ROUND_TRIP_EFFICIENCY)
    discharge_eff = np.sqrt(ROUND_TRIP_EFFICIENCY)
    soc = 0.0
    capacity = battery_kwh

    final_import = np.zeros_like(load)
    final_export = np.zeros_like(load)

    for i in range(len(net)):
        if net[i] < 0:  # surplus
            charge = min(-net[i], (capacity - soc) / charge_eff)
            soc += charge * charge_eff
            final_export[i] = -net[i] - charge
        else:
            discharge = 0.0
            if soc > 0 and not night_mask[i]:
                discharge = min(net[i], soc * discharge_eff)
                soc -= discharge / discharge_eff
            remaining = net[i] - discharge
            final_import[i] = max(0, remaining)

            if allow_night_grid_charge and night_mask[i] and soc < capacity * 0.8:
                needed = min(capacity * 0.8 - soc, 2.0)  # 2 kW limit
                soc += needed * charge_eff
                final_import[i] += needed

    return {"import": final_import, "export": final_export}


def calculate_supplier_cost(
    supplier: dict, model: ModelData, ev_energy: dict, with_battery: bool
) -> dict:
    interval = model.interval
    annual_factor = 365.25 / model.days

    # Base load + PV
    load = interval["load"].to_numpy(dtype=float)
    solar = interval["solar"].to_numpy(dtype=float)

    night_mask = get_night_mask(model, supplier.get("night_hours"))

    if with_battery:
        batt = simulate_battery_dispatch(model, BATTERY_KWH, night_mask)
        imp = batt["import"]
        exp = batt["export"]
    else:
        net = load - solar
        imp = np.clip(net, 0, None)
        exp = np.clip(-net, 0, None)

    # Electricity cost
    peak_rate = supplier["peak_rate"]
    offpeak_rate = supplier.get("offpeak_rate", peak_rate)
    night_rate = supplier.get("night_rate", offpeak_rate)
    export_rate = supplier["export_rate"]

    # Simple split: use night rate for EV portion during night hours
    ev_home_annual = ev_energy["home_kwh"]
    ev_dc_annual = ev_energy["dc_kwh"]

    # Rough split of import into night vs day
    night_import = float(imp[night_mask].sum() * annual_factor)
    day_import = float(imp[~night_mask].sum() * annual_factor)

    # Apply night rate to portion of EV home charging
    night_ev = ev_home_annual * 0.7  # assume 70% of home charging at night
    day_ev = ev_home_annual * 0.3

    electricity_cost = (
        (day_import - day_ev) * peak_rate
        + (night_import - night_ev) * night_rate
        + day_ev * night_rate
        + night_ev * night_rate
        - float(exp.sum() * annual_factor) * export_rate
    )

    # Daily charges
    daily_cost = (
        model.days * supplier["daily_charge"] * annual_factor / model.days * 365.25
    )

    # DC charging
    dc_cost = ev_dc_annual * supplier["public_dc_rate"]

    # Gas
    gas_cost = 0.0
    if supplier.get("gas"):
        gas_cost = supplier.get("bottle_charge_per_year", 0) + supplier.get(
            "bottle_rental_per_year", 0
        )

    subtotal = electricity_cost + daily_cost + dc_cost + gas_cost

    # Discounts and rebates
    discount = supplier.get("dual_fuel_discount", 0.0)
    if discount > 0:
        subtotal *= 1 - discount

    rebate = supplier.get("rebate", 0)
    total = subtotal - rebate

    return {
        "supplier": supplier["supplier"],
        "tariff": supplier["tariff"],
        "plan_name": supplier["plan_name"],
        "with_battery": with_battery,
        "battery_kwh": BATTERY_KWH if with_battery else 0.0,
        "annual_electricity_cost_nzd": round(electricity_cost, 2),
        "annual_daily_charge_nzd": round(daily_cost, 2),
        "annual_dc_charging_nzd": round(dc_cost, 2),
        "annual_gas_cost_nzd": round(gas_cost, 2),
        "total_annual_cost_nzd": round(total, 2),
        "export_credit_nzd": round(float(exp.sum() * annual_factor) * export_rate, 2),
    }


def run_full_comparison(model: ModelData) -> pd.DataFrame:
    ev_energy = calculate_annual_ev_energy()
    rows = []
    for supplier in SUPPLIERS:
        for with_battery in [False, True]:
            row = calculate_supplier_cost(supplier, model, ev_energy, with_battery)
            rows.append(row)
    return pd.DataFrame(rows)


def write_outputs(results: pd.DataFrame) -> None:
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        results.to_excel(writer, sheet_name="Supplier Comparison", index=False)

    # Markdown summary
    lines = [
        "# Supplier Comparison Summary (PV + 2 EVs)",
        "",
        f"Battery size: {BATTERY_KWH} kWh",
        "",
        "## Annual Costs",
        "",
    ]
    lines.append(results.round(2).to_markdown(index=False))
    lines.append("")
    lines.append(
        "**Note:** Costs include electricity, daily charges, DC charging, gas (if applicable), discounts and rebates."
    )

    OUTPUT_MARKDOWN.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    model = build_model_data()
    results = run_full_comparison(model)
    write_outputs(results)
    print(f"Wrote {OUTPUT_XLSX}")
    print(f"Wrote {OUTPUT_MARKDOWN}")
    print("\nTop 5 cheapest options:")
    print(
        results.nsmallest(5, "total_annual_cost_nzd")[
            ["plan_name", "with_battery", "total_annual_cost_nzd"]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
