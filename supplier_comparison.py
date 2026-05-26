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

OUTPUT_DIR = Path("summaries")
OUTPUT_XLSX = OUTPUT_DIR / "supplier_comparison.xlsx"
OUTPUT_MARKDOWN = OUTPUT_DIR / "supplier_comparison_summary.md"

# =============================================================================
# CONFIGURATION
# =============================================================================
BATTERY_KWH = 8.3
BATTERY_POWER_LIMIT_KW = 5.0

EV_MILEAGE = {"Tesla": 26_000, "MG": 13_000}
HOME_CHARGE_PCTS = {"Tesla": 0.65, "MG": 0.60}
KWH_PER_KM = {"Tesla": 0.153, "MG": 0.190}
ROUND_TRIP_EFFICIENCY = 0.90

# =============================================================================
# FULL SUPPLIER DATA (all rows from your table)
# =============================================================================
SUPPLIERS = [
    # Mercury EV standard usage - updated 05/2026
    {
        "supplier": "Mercury",
        "tariff": "standard usage",
        "plan_name": "Mercury EV - standard usage",
        "peak_rate": 0.4013,
        "offpeak_rate": 0.3360,
        "night_rate": 0.3360,
        "daily_charge": 2.6335,
        "export_rate": 0.120,
        "public_dc_rate": 0.85,
        "gas": True,
        "bottle_charge_per_year": 253.6,
        "bottle_rental_per_year": 101.4,
        "dual_fuel_discount": 0.05,
        "rebate": 500,
        "low_usage_threshold_kwh": 8000,
        "night_hours": (21, 7),
    },
    # Mercury EV - low usage - updated 05/2026
    {
        "supplier": "Mercury",
        "tariff": "low usage",
        "plan_name": "Mercury EV  - low usage",
        "peak_rate": 0.4427,
        "offpeak_rate": 0.3774,
        "night_rate": 0.3774,
        "daily_charge": 1.7250,
        "export_rate": 0.120,
        "public_dc_rate": 0.85,
        "gas": True,
        "bottle_charge_per_year": 253.6,
        "bottle_rental_per_year": 101.4,
        "dual_fuel_discount": 0.05,
        "rebate": 500,
        "low_usage_threshold_kwh": 8000,
        "night_hours": (21, 7),
    },
    # Octopus Power - Peaker - updated 05/2026
    {
        "supplier": "Octopus Power - Peaker",
        "tariff": "standard usage",
        "plan_name": "Octopus Power - Peaker - standard usage",
        "peak_rate": 0.364,
        "offpeak_rate": 0.272,
        "night_rate": 0.182,
        "daily_charge": 3.337,
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
    # Octopus Power Flexi - updated 05/2026
    {
        "supplier": "Octopus Power Flexi",
        "tariff": "standard usage",
        "plan_name": "Octopus Power Flexi - standard usage",
        "peak_rate": 0.364,
        "offpeak_rate": 0.272,
        "night_rate": 0.182,
        "daily_charge": 3.337,
        "export_rate": 0.140,
        "public_dc_rate": 0.85,
        "gas": False,
        "bottle_charge_per_year": 0,
        "bottle_rental_per_year": 0,
        "dual_fuel_discount": 0.0,
        "rebate": 0,
        "low_usage_threshold_kwh": None,
        "night_hours": (23, 7),
    },
    # Octopus Power Flexi  - updated 05/2026
    {
        "supplier": "Octopus Power Flexi",
        "tariff": "low usage",
        "plan_name": "Octopus Power Flexi - low usage",
        "peak_rate": 0.453,
        "offpeak_rate": 0.361,
        "night_rate": 0.226,
        "daily_charge": 1.725,
        "export_rate": 0.140,
        "public_dc_rate": 0.85,
        "gas": False,
        "bottle_charge_per_year": 0,
        "bottle_rental_per_year": 0,
        "dual_fuel_discount": 0.0,
        "rebate": 0,
        "low_usage_threshold_kwh": None,
        "night_hours": (23, 7),
    },
    # Genesis Energy EV - standard - updated 05/2026
    {
        "supplier": "Genesis Energy EV",
        "tariff": "standard usage",
        "plan_name": "Genesis Energy EV - standard usage",
        "peak_rate": 0.3778,
        "offpeak_rate": 0.1818,
        "night_rate": 0.1818,
        "daily_charge": 2.4893,
        "export_rate": 0.144,
        "public_dc_rate": 0.3778,
        "gas": True,
        "bottle_charge_per_year": 345.9,
        "bottle_rental_per_year": 69.00,
        "dual_fuel_discount": 0.05,
        "rebate": 0,
        "low_usage_threshold_kwh": 8000,
        "night_hours": (21, 7),
    },
    # Genesis Energy EV - low usage - updated 05/2026
    {
        "supplier": "Genesis Energy EV",
        "tariff": "low usage",
        "plan_name": "Genesis Energy EV - low usage",
        "peak_rate": 0.414805,
        "offpeak_rate": 0.207345,
        "night_rate": 0.207345,
        "daily_charge": 1.67325,
        "export_rate": 0.144,
        "public_dc_rate": 0.414805,
        "gas": True,
        "bottle_charge_per_year": 345.9,
        "bottle_rental_per_year": 69.00,
        "dual_fuel_discount": 0.00,
        "rebate": 0,
        "low_usage_threshold_kwh": 8000,
        "night_hours": (21, 7),
    },
    # Electric Kiwi Move Master updated 05/2026
    {
        "supplier": "Electric Kiwi",
        "tariff": "standard usage",
        "plan_name": "Electric Kiwi Move Master - standard usage",
        "peak_rate": 0.6481,
        "offpeak_rate": 0.3888,
        "night_rate": 0.324,
        "daily_charge": 1.15,
        "export_rate": 0.23,
        "public_dc_rate": 0.85,
        "gas": False,
        "bottle_charge_per_year": 0,
        "bottle_rental_per_year": 0,
        "dual_fuel_discount": 0.0,
        "rebate": 0,
        "low_usage_threshold_kwh": None,
        "night_hours": (23, 7),
    },
    # Contact Good Nights - standard - updated 05/2026
    {
        "supplier": "Contact",
        "tariff": "standard usage",
        "plan_name": "Contact Good Nights - standard usage",
        "peak_rate": 0.3864,
        "offpeak_rate": 0.3864,
        "night_rate": 0.00,
        "daily_charge": 3.2867,
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
    # Contact Good Nights - low usage - updated 05/2026
    {
        "supplier": "Contact",
        "tariff": "low usage",
        "plan_name": "Contact Good Nights - low usage",
        "peak_rate": 0.4531,
        "offpeak_rate": 0.4531,
        "night_rate": 0.00,
        "daily_charge": 2.07,
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
    # Contact EV Charge - standard - updated 05/2026
    {
        "supplier": "Contact",
        "tariff": "standard usage",
        "plan_name": "Contact EV Charge - standard usage",
        "peak_rate": 0.3864,
        "offpeak_rate": 0.3864,
        "night_rate": 0.18975,
        "daily_charge": 3.402,
        "export_rate": 0.120,
        "public_dc_rate": 0.85,
        "gas": True,
        "bottle_charge_per_year": 0,
        "bottle_rental_per_year": 0,
        "dual_fuel_discount": 0.0,
        "rebate": 0,
        "low_usage_threshold_kwh": 8000,
        "night_hours": (21, 7),
    },
    # Contact EV Charge - low usage - updated 05/2026
    {
        "supplier": "Contact",
        "tariff": "low usage",
        "plan_name": "Contact EV Charge - low usage",
        "peak_rate": 0.4462,
        "offpeak_rate": 0.4462,
        "night_rate": 0.2231,
        "daily_charge": 2.07,
        "export_rate": 0.120,
        "public_dc_rate": 0.85,
        "gas": True,
        "bottle_charge_per_year": 0,
        "bottle_rental_per_year": 0,
        "dual_fuel_discount": 0.0,
        "rebate": 0,
        "low_usage_threshold_kwh": 8000,
        "night_hours": (21, 7),
    },
    # Ecotricity - EcoSolar low usage - updated 05/2026
    {
        "supplier": "Ecotricity",
        "tariff": "low usage",
        "plan_name": "Ecotricity - EcoSolar low usage",
        "peak_rate": 0.4502,
        "offpeak_rate": 0.2958,
        "night_rate": 0.2958,
        "daily_charge": 1.728,
        "export_rate": 0.1840,
        "public_dc_rate": 0.85,
        "gas": True,
        "bottle_charge_per_year": 0,
        "bottle_rental_per_year": 0,
        "dual_fuel_discount": 0.0,
        "rebate": 0,
        "low_usage_threshold_kwh": None,
        "night_hours": (21, 7),
    },
    # Ecotricity - Eco Solar - standard usage - updated 05/2026
    {
        "supplier": "Ecotricity",
        "tariff": "standard usage",
        "plan_name": "Ecotricity - EcoSolar standard usage",
        "peak_rate": 0.3995,
        "offpeak_rate": 0.2451,
        "night_rate": 0.2451,
        "daily_charge": 2.8865,
        "export_rate": 0.1840,
        "public_dc_rate": 0.85,
        "gas": True,
        "bottle_charge_per_year": 0,
        "bottle_rental_per_year": 0,
        "dual_fuel_discount": 0.0,
        "rebate": 0,
        "low_usage_threshold_kwh": None,
        "night_hours": (21, 7),
    },
    # Meridian - standard usage - updated 05/2026
    {
        "supplier": "Meridian",
        "tariff": "standard usage",
        "plan_name": "Meridian - standard usage",
        "peak_rate": 0.3179,
        "offpeak_rate": 0.3179,
        "night_rate": 0.155,
        "daily_charge": 2.6250,
        "export_rate": 0.12,
        "public_dc_rate": 0.85,
        "gas": False,
        "bottle_charge_per_year": 0,
        "bottle_rental_per_year": 0,
        "dual_fuel_discount": 0.0,
        "rebate": 0,
        "low_usage_threshold_kwh": 8000,
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
        return (hours >= start) & (hours < end)
    return (hours >= start) | (hours < end)


def get_import_rate_vector(supplier: dict, model: ModelData) -> np.ndarray:
    """Build an interval import-rate vector for the supplier plan."""
    peak_rate = supplier["peak_rate"]
    offpeak_rate = supplier.get("offpeak_rate", peak_rate)
    night_rate = supplier.get("night_rate", offpeak_rate)

    rates = np.where(model.is_peak, peak_rate, offpeak_rate).astype(float)
    night_mask = get_night_mask(model, supplier.get("night_hours"))
    rates[night_mask] = night_rate
    return rates


def target_date_for_interval(timestamp: pd.Timestamp) -> object:
    """Map cheap overnight charging intervals to the peak/discharge date covered."""
    if timestamp.hour < 7:
        return timestamp.date()
    return (timestamp + pd.Timedelta(days=1)).date()


def daily_soc_targets(
    model: ModelData,
    net: np.ndarray,
    target_mask: np.ndarray,
    battery_kwh: float,
    discharge_eff: float,
    charge_eff: float,
) -> dict:
    """Estimate how much off-peak grid charge is worth carrying into each day."""
    if battery_kwh <= 0:
        return {}

    round_trip = charge_eff * discharge_eff
    capacity_deliverable = battery_kwh * discharge_eff
    targets = {}

    for day in model.unique_dates:
        indices = np.where((model.date_values == day) & target_mask)[0]
        cumulative_need = 0.0
        max_initial_deliverable_needed = 0.0

        for i in indices:
            value = float(net[i])
            if value >= 0:
                cumulative_need += value
            else:
                cumulative_need += value * round_trip
                cumulative_need = max(cumulative_need, -capacity_deliverable)
            max_initial_deliverable_needed = max(
                max_initial_deliverable_needed, cumulative_need
            )

        targets[day] = min(battery_kwh, max_initial_deliverable_needed / discharge_eff)
    return targets


def simulate_battery_dispatch(
    model: ModelData,
    battery_kwh: float,
    supplier: dict,
    allow_night_grid_charge: bool = True,
) -> dict:
    """Tariff-aware battery model: solar self-consumption + cheap-period top-up."""
    load = model.interval["load"].to_numpy(dtype=float)
    solar = model.interval["solar"].to_numpy(dtype=float)
    net = load - solar

    if battery_kwh <= 0:
        return {"import": np.clip(net, 0, None), "export": np.clip(-net, 0, None)}

    rate_vector = get_import_rate_vector(supplier, model)
    export_rate = supplier["export_rate"]
    min_rate = float(rate_vector.min())
    max_rate = float(rate_vector.max())
    grid_charge_is_economic = min_rate / ROUND_TRIP_EFFICIENCY < max_rate
    cheap_mask = rate_vector <= min_rate + 1e-9
    grid_charge_mask = cheap_mask & grid_charge_is_economic

    # Solar-stored energy should avoid imports where import value exceeds export
    # opportunity cost. Grid-charged energy is reserved for intervals dear enough
    # to beat round-trip losses from the cheapest import period.
    solar_discharge_mask = rate_vector > export_rate / ROUND_TRIP_EFFICIENCY
    arbitrage_discharge_mask = rate_vector > min_rate / ROUND_TRIP_EFFICIENCY
    discharge_mask = solar_discharge_mask & (~grid_charge_mask)

    charge_eff = np.sqrt(ROUND_TRIP_EFFICIENCY)
    discharge_eff = np.sqrt(ROUND_TRIP_EFFICIENCY)
    interval_hours = (
        pd.Timedelta(model.interval.index.freq or "5min").total_seconds() / 3600
    )
    max_transfer = BATTERY_POWER_LIMIT_KW * interval_hours
    grid_targets = daily_soc_targets(
        model,
        net,
        arbitrage_discharge_mask,
        battery_kwh,
        discharge_eff,
        charge_eff,
    )

    soc = 0.0
    capacity = battery_kwh

    final_import = np.zeros_like(load)
    final_export = np.zeros_like(load)
    charged_from_solar = 0.0
    charged_from_grid = 0.0
    discharged_to_load = 0.0

    for i, value in enumerate(net):
        if value < 0:
            surplus = -float(value)
            charge = min(surplus, (capacity - soc) / charge_eff, max_transfer)
            soc += charge * charge_eff
            charged_from_solar += charge
            final_export[i] = surplus - charge
            continue

        need = float(value)
        if soc > 0 and discharge_mask[i]:
            discharge = min(need, soc * discharge_eff, max_transfer)
            if discharge > 0:
                soc -= discharge / discharge_eff
                discharged_to_load += discharge
                need -= discharge

        final_import[i] = max(0, need)

        if (
            allow_night_grid_charge
            and grid_charge_mask[i]
            and grid_charge_is_economic
            and soc < capacity
        ):
            target_day = target_date_for_interval(model.interval.index[i])
            target_soc = grid_targets.get(target_day, 0.0)
            if soc < target_soc:
                charge = min(
                    (target_soc - soc) / charge_eff,
                    (capacity - soc) / charge_eff,
                    max_transfer,
                )
                soc += charge * charge_eff
                charged_from_grid += charge
                final_import[i] += charge

    return {
        "import": final_import,
        "export": final_export,
        "battery_charged_from_solar_kwh": charged_from_solar,
        "battery_charged_from_grid_kwh": charged_from_grid,
        "battery_discharged_to_load_kwh": discharged_to_load,
    }


def calculate_supplier_cost(
    supplier: dict, model: ModelData, ev_energy: dict, with_battery: bool
) -> dict:
    interval = model.interval
    annual_factor = 365.25 / model.days

    # Base load + PV
    load = interval["load"].to_numpy(dtype=float)
    solar = interval["solar"].to_numpy(dtype=float)

    rate_vector = get_import_rate_vector(supplier, model)

    if with_battery:
        batt = simulate_battery_dispatch(model, BATTERY_KWH, supplier)
        imp = batt["import"]
        exp = batt["export"]
        battery_charged_from_solar = batt["battery_charged_from_solar_kwh"]
        battery_charged_from_grid = batt["battery_charged_from_grid_kwh"]
        battery_discharged_to_load = batt["battery_discharged_to_load_kwh"]
    else:
        net = load - solar
        imp = np.clip(net, 0, None)
        exp = np.clip(-net, 0, None)
        battery_charged_from_solar = 0.0
        battery_charged_from_grid = 0.0
        battery_discharged_to_load = 0.0

    export_rate = supplier["export_rate"]

    # Home EV charging is already part of the measured interval load. Only public
    # DC charging is added separately because roof PV cannot offset it.
    ev_dc_annual = ev_energy["dc_kwh"]

    electricity_cost = (
        float((imp * rate_vector).sum() * annual_factor)
        - float(exp.sum() * annual_factor) * export_rate
    )

    # Daily charges
    daily_cost = supplier["daily_charge"] * 365.25

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
        "annual_import_kwh": round(float(imp.sum() * annual_factor), 2),
        "annual_export_kwh": round(float(exp.sum() * annual_factor), 2),
        "annual_electricity_cost_nzd": round(electricity_cost, 2),
        "annual_daily_charge_nzd": round(daily_cost, 2),
        "annual_dc_charging_nzd": round(dc_cost, 2),
        "annual_gas_cost_nzd": round(gas_cost, 2),
        "total_annual_cost_nzd": round(total, 2),
        "export_credit_nzd": round(float(exp.sum() * annual_factor) * export_rate, 2),
        "battery_charged_from_solar_kwh": round(
            battery_charged_from_solar * annual_factor, 2
        ),
        "battery_charged_from_grid_kwh": round(
            battery_charged_from_grid * annual_factor, 2
        ),
        "battery_discharged_to_load_kwh": round(
            battery_discharged_to_load * annual_factor, 2
        ),
        "low_usage_threshold_kwh": supplier.get("low_usage_threshold_kwh"),
    }


def run_full_comparison(model: ModelData) -> pd.DataFrame:
    ev_energy = calculate_annual_ev_energy()
    rows = []
    for supplier in SUPPLIERS:
        for with_battery in [False, True]:
            row = calculate_supplier_cost(supplier, model, ev_energy, with_battery)
            rows.append(row)
    return pd.DataFrame(rows)


def plan_family(plan_name: str) -> str:
    return (
        plan_name.replace(" - standard usage", "")
        .replace(" - low usage", "")
        .replace(" - low user", "")
        .replace(" - standard user", "")
    )


def low_standard_comparison(results: pd.DataFrame) -> pd.DataFrame:
    rows = []
    working = results.copy()
    working["plan_family"] = working["plan_name"].map(plan_family)

    grouped = working[working["tariff"].isin(["low usage", "standard usage"])].groupby(
        ["plan_family", "with_battery"]
    )

    for (family, with_battery), group in grouped:
        low = group[group["tariff"] == "low usage"]
        standard = group[group["tariff"] == "standard usage"]
        if low.empty or standard.empty:
            continue

        low_row = low.sort_values("total_annual_cost_nzd").iloc[0]
        standard_row = standard.sort_values("total_annual_cost_nzd").iloc[0]
        difference = (
            low_row["total_annual_cost_nzd"] - standard_row["total_annual_cost_nzd"]
        )
        rows.append(
            {
                "plan_family": family,
                "with_battery": with_battery,
                "modeled_annual_import_kwh": low_row["annual_import_kwh"],
                "low_usage_cost_nzd": low_row["total_annual_cost_nzd"],
                "standard_usage_cost_nzd": standard_row["total_annual_cost_nzd"],
                "low_minus_standard_nzd": difference,
                "cheaper_tariff": "low usage" if difference < 0 else "standard usage",
                "listed_low_usage_threshold_kwh": low_row["low_usage_threshold_kwh"],
            }
        )
    return pd.DataFrame(rows)


def write_outputs(results: pd.DataFrame, low_standard: pd.DataFrame) -> None:
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        results.to_excel(writer, sheet_name="Supplier Comparison", index=False)
        low_standard.to_excel(writer, sheet_name="Low vs Standard", index=False)

    # Markdown summary
    summary_columns = [
        "supplier",
        "tariff",
        "plan_name",
        "with_battery",
        "battery_kwh",
        "annual_import_kwh",
        "annual_export_kwh",
        "annual_electricity_cost_nzd",
        "annual_daily_charge_nzd",
        "annual_dc_charging_nzd",
        "annual_gas_cost_nzd",
        "total_annual_cost_nzd",
        "export_credit_nzd",
        "battery_charged_from_grid_kwh",
    ]
    lines = [
        "# Supplier Comparison Summary (PV + 2 EVs)",
        "",
        f"Battery size: {BATTERY_KWH} kWh",
        f"Battery power limit: {BATTERY_POWER_LIMIT_KW} kW",
        "",
        "## Annual Costs",
        "",
    ]
    lines.append(results[summary_columns].round(2).fillna("").to_markdown(index=False))
    if not low_standard.empty:
        lines.extend(
            [
                "",
                "## Low vs Standard Usage",
                "",
                "Listed low-usage thresholds are shown as reference only; this table compares the modelled annual cost directly.",
                "",
                low_standard.round(2).fillna("").to_markdown(index=False),
            ]
        )
    lines.append("")
    lines.append(
        "**Note:** Costs include interval-priced home electricity, daily charges, public DC charging, gas (if applicable), discounts and rebates. Home EV charging is not added again because it is already part of measured home load."
    )

    OUTPUT_MARKDOWN.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    model = build_model_data()
    results = run_full_comparison(model)
    low_standard = low_standard_comparison(results)
    write_outputs(results, low_standard)
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
