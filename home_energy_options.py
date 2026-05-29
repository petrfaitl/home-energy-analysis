"""
Home Energy Options Analysis
============================

Replays raw Home Assistant cumulative energy meters to estimate the value of
adding BYD HVM battery storage and/or a larger solar array.

The model uses the supplied import, export, solar production, and EV charging
CSV files. Fronius import/export/solar meters are treated as MWh, while the EV
meter is treated as kWh, matching the existing workbook totals.

Outputs:
  analysis_files/home_energy_options_analysis.xlsx
  analysis_files/home_energy_options_summary.md
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from pathlib import Path
import numpy as np
import pandas as pd

# Input files -----------------------------------------------------------------
BASE_DIR = Path("analysis_files")
EXPORT_DIR = Path("summaries")
INPUT_FILES = {
    "import": (BASE_DIR / "Import-150525-150526.csv", "MWh"),
    "export": (BASE_DIR / "Energy_Export_160525-150526.csv", "MWh"),
    "solar": (BASE_DIR / "Energy_Solar_Production_160525-150526.csv", "MWh"),
    "ev": (BASE_DIR / "EV-Charging-150525-150526.csv", "kWh"),
}


# Tariff and site assumptions --------------------------------------------------
TIMEZONE = "Pacific/Auckland"
PEAK_START_HOUR = 7
PEAK_END_HOUR = 21
RATES = {
    "offpeak_import": 0.207345,
    "peak_import": 0.414805,
    "export": 0.144,
    "daily": 1.67325,
}

CURRENT_PANEL_COUNT = 18
CURRENT_PANEL_KW = 0.395
ADDED_PANEL_KW = 0.395
CURRENT_ARRAY_SPARE_PANEL_SLOTS = 1
CURRENT_SOLAR_KWP = CURRENT_PANEL_COUNT * CURRENT_PANEL_KW
MAX_TOTAL_SOLAR_KWP_TO_HIGHLIGHT = 10.0

# BYD Battery-Box Premium HVM usable capacities, one tower.
BYD_HVM_USABLE_KWH = [0.0, 8.28, 11.04, 13.80, 16.56, 19.32, 22.08]
EXTRA_LARGE_BATTERY_KWH = [27.60, 33.12, 38.64, 44.16]

# The model is primarily an energy dispatch model. Leave this as None unless
# you want to test a specific inverter/battery charge or discharge limit.
BATTERY_POWER_LIMIT_KW: float | None = None

ROUND_TRIP_EFFICIENCY = 0.90
BIN_FREQUENCY = "5min"
SPIKE_FILTER_KWH = 100.0
ADDED_PANEL_COUNTS = range(0, 13)  # 0..12 added 395 W panels.

OUTPUT_XLSX = EXPORT_DIR / "home_energy_options_analysis.xlsx"
OUTPUT_MARKDOWN = EXPORT_DIR / "home_energy_options_summary.md"


@dataclass(frozen=True)
class ModelData:
    interval: pd.DataFrame
    start_day: pd.Timestamp
    end_day: pd.Timestamp
    days: int
    peak_start_hour: int
    peak_end_hour: int
    is_peak: np.ndarray
    date_values: np.ndarray
    unique_dates: list
    peak_indices_by_date: dict
    target_date_by_interval: dict
    negative_load_kwh: float
    negative_load_bins: int


def load_cumulative_meter(path: Path, unit: str, name: str) -> pd.DataFrame:
    """Load a cumulative Home Assistant meter and return per-reading kWh diffs."""
    df = pd.read_csv(path)
    required = {"state", "last_changed"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path} is missing columns: {sorted(missing)}")

    timestamps = pd.to_datetime(df["last_changed"], utc=True).dt.tz_convert(TIMEZONE)
    state = df["state"].replace("unavailable", pd.NA)
    state = pd.to_numeric(state, errors="coerce").ffill()
    state_kwh = state * 1000.0 if unit.lower() == "mwh" else state

    diff = state_kwh.diff().fillna(0)
    valid = (diff >= 0) & (diff <= SPIKE_FILTER_KWH)
    diff = diff.where(valid, 0)
    return pd.DataFrame({name: diff.to_numpy()}, index=timestamps)


def first_complete_day(timestamp: pd.Timestamp) -> pd.Timestamp:
    if timestamp.hour == 0 and timestamp.minute == 0:
        return pd.Timestamp(timestamp.date())
    return pd.Timestamp(timestamp.date()) + pd.Timedelta(days=1)


def last_complete_day(timestamp: pd.Timestamp) -> pd.Timestamp:
    if timestamp.hour == 23 and timestamp.minute >= 45:
        return pd.Timestamp(timestamp.date())
    return pd.Timestamp(timestamp.date()) - pd.Timedelta(days=1)


def build_model_data(
    peak_start_hour: int = PEAK_START_HOUR,
    peak_end_hour: int = PEAK_END_HOUR,
) -> ModelData:
    raw = {
        name: load_cumulative_meter(path, unit, name)
        for name, (path, unit) in INPUT_FILES.items()
    }

    start_day = max(first_complete_day(df.index.min()) for df in raw.values())
    end_day = min(last_complete_day(df.index.max()) for df in raw.values())

    interval = None
    for name, df in raw.items():
        resampled = df.resample(BIN_FREQUENCY).sum()
        interval = (
            resampled if interval is None else interval.join(resampled, how="outer")
        )

    if interval is None:
        raise ValueError("No input data loaded")

    interval = interval.fillna(0)
    dates = pd.Series(interval.index.date, index=interval.index)
    interval = interval[(dates >= start_day.date()) & (dates <= end_day.date())].copy()

    reconstructed_load = interval["import"] + interval["solar"] - interval["export"]
    negative = reconstructed_load < 0
    negative_load_kwh = float(reconstructed_load[negative].sum())
    negative_load_bins = int(negative.sum())

    interval["load"] = reconstructed_load.clip(lower=0)
    interval["is_peak"] = (interval.index.hour >= peak_start_hour) & (
        interval.index.hour < peak_end_hour
    )
    interval["period"] = np.where(interval["is_peak"], "Peak", "Off-Peak")
    interval["date"] = [d.isoformat() for d in interval.index.date]
    interval["month"] = interval.index.tz_localize(None).to_period("M").astype(str)

    is_peak = interval["is_peak"].to_numpy(dtype=bool)
    date_values = np.array(interval.index.date)
    unique_dates = sorted(set(date_values))
    peak_indices_by_date = {
        date: np.where((date_values == date) & is_peak)[0] for date in unique_dates
    }

    target_date_by_interval = {}
    for i, timestamp in enumerate(interval.index):
        if timestamp.hour < peak_start_hour:
            target_date_by_interval[i] = timestamp.date()
        elif timestamp.hour >= peak_end_hour:
            target_date_by_interval[i] = (timestamp + pd.Timedelta(days=1)).date()

    return ModelData(
        interval=interval,
        start_day=start_day,
        end_day=end_day,
        days=len(unique_dates),
        peak_start_hour=peak_start_hour,
        peak_end_hour=peak_end_hour,
        is_peak=is_peak,
        date_values=date_values,
        unique_dates=unique_dates,
        peak_indices_by_date=peak_indices_by_date,
        target_date_by_interval=target_date_by_interval,
        negative_load_kwh=negative_load_kwh,
        negative_load_bins=negative_load_bins,
    )


def bill_cost(
    import_kwh: np.ndarray,
    export_kwh: np.ndarray,
    model: ModelData,
    rates: dict | None = None,
) -> dict:
    chosen_rates = RATES if rates is None else {**RATES, **rates}
    peak_import = float(import_kwh[model.is_peak].sum())
    offpeak_import = float(import_kwh[~model.is_peak].sum())
    export = float(export_kwh.sum())
    energy_cost = (
        offpeak_import * chosen_rates["offpeak_import"]
        + peak_import * chosen_rates["peak_import"]
        - export * chosen_rates["export"]
    )
    fixed_cost = model.days * chosen_rates["daily"]
    return {
        "offpeak_import_kwh": offpeak_import,
        "peak_import_kwh": peak_import,
        "export_kwh": export,
        "energy_cost_nzd": energy_cost,
        "fixed_daily_cost_nzd": fixed_cost,
        "total_cost_nzd": energy_cost + fixed_cost,
    }


def initial_soc_targets(
    net_kwh: np.ndarray,
    capacity_kwh: float,
    model: ModelData,
    charge_efficiency: float,
    discharge_efficiency: float,
) -> dict:
    """Estimate off-peak top-up targets for the next 07:00-21:00 peak window."""
    if capacity_kwh <= 0:
        return {}

    round_trip = charge_efficiency * discharge_efficiency
    capacity_deliverable = capacity_kwh * discharge_efficiency
    targets = {}

    for date, indices in model.peak_indices_by_date.items():
        cumulative_need = 0.0
        max_initial_deliverable_needed = 0.0
        for value in net_kwh[indices]:
            if value >= 0:
                cumulative_need += float(value)
            else:
                cumulative_need += float(value) * round_trip
                cumulative_need = max(cumulative_need, -capacity_deliverable)
            max_initial_deliverable_needed = max(
                max_initial_deliverable_needed, cumulative_need
            )

        targets[date] = min(
            capacity_kwh, max_initial_deliverable_needed / discharge_efficiency
        )

    return targets


def simulate_scenario(
    model: ModelData,
    total_solar_kwp: float,
    battery_kwh: float,
    allow_offpeak_grid_charge: bool,
    rates: dict | None = None,
) -> dict:
    """Replay household load against a solar/battery configuration."""
    interval = model.interval
    load = interval["load"].to_numpy(dtype=float)
    solar = interval["solar"].to_numpy(dtype=float) * (
        total_solar_kwp / CURRENT_SOLAR_KWP
    )
    net = load - solar

    import_kwh = np.zeros(len(interval))
    export_kwh = np.zeros(len(interval))
    state_of_charge = 0.0
    solar_charge_kwh = 0.0
    grid_charge_kwh = 0.0
    discharged_kwh = 0.0

    charge_efficiency = sqrt(ROUND_TRIP_EFFICIENCY)
    discharge_efficiency = sqrt(ROUND_TRIP_EFFICIENCY)
    interval_hours = pd.Timedelta(BIN_FREQUENCY).total_seconds() / 3600
    max_transfer = (
        float("inf")
        if BATTERY_POWER_LIMIT_KW is None
        else BATTERY_POWER_LIMIT_KW * interval_hours
    )

    offpeak_targets = initial_soc_targets(
        net, battery_kwh, model, charge_efficiency, discharge_efficiency
    )

    for i, value in enumerate(net):
        if value < 0:
            surplus = -float(value)
            if battery_kwh > 0:
                charge_ac = min(
                    surplus,
                    (battery_kwh - state_of_charge) / charge_efficiency,
                    max_transfer,
                )
                state_of_charge += charge_ac * charge_efficiency
                solar_charge_kwh += charge_ac
                surplus -= charge_ac
            export_kwh[i] = surplus
            continue

        need = float(value)
        if battery_kwh > 0 and model.is_peak[i] and need > 0:
            discharge_ac = min(
                need, state_of_charge * discharge_efficiency, max_transfer
            )
            state_of_charge -= discharge_ac / discharge_efficiency
            discharged_kwh += discharge_ac
            need -= discharge_ac

        import_kwh[i] = need

        if battery_kwh <= 0 or model.is_peak[i] or not allow_offpeak_grid_charge:
            continue

        target_date = model.target_date_by_interval.get(i)
        target_soc = offpeak_targets.get(target_date, 0.0)
        if state_of_charge < target_soc:
            charge_ac = min(
                (target_soc - state_of_charge) / charge_efficiency,
                (battery_kwh - state_of_charge) / charge_efficiency,
                max_transfer,
            )
            state_of_charge += charge_ac * charge_efficiency
            grid_charge_kwh += charge_ac
            import_kwh[i] += charge_ac

    cost = bill_cost(import_kwh, export_kwh, model, rates=rates)
    cost.update(
        {
            "total_solar_kwp": total_solar_kwp,
            "added_panels": round(
                (total_solar_kwp - CURRENT_SOLAR_KWP) / ADDED_PANEL_KW
            ),
            "current_array_extra_panels": min(
                round((total_solar_kwp - CURRENT_SOLAR_KWP) / ADDED_PANEL_KW),
                CURRENT_ARRAY_SPARE_PANEL_SLOTS,
            ),
            "second_array_panels": max(
                0,
                round((total_solar_kwp - CURRENT_SOLAR_KWP) / ADDED_PANEL_KW)
                - CURRENT_ARRAY_SPARE_PANEL_SLOTS,
            ),
            "added_solar_kwp": total_solar_kwp - CURRENT_SOLAR_KWP,
            "battery_kwh": battery_kwh,
            "battery_mode": (
                "solar + off-peak top-up" if allow_offpeak_grid_charge else "solar only"
            ),
            "solar_generation_kwh": float(solar.sum()),
            "load_kwh": float(load.sum()),
            "battery_charged_from_solar_kwh": solar_charge_kwh,
            "battery_charged_from_grid_kwh": grid_charge_kwh,
            "battery_discharged_to_load_kwh": discharged_kwh,
            "self_consumption_kwh": float(load.sum() - import_kwh.sum()),
        }
    )
    return cost


def add_savings_columns(
    df: pd.DataFrame, baseline_cost: float, days: int
) -> pd.DataFrame:
    out = df.copy()
    annual_factor = 365.25 / days
    out["period_savings_nzd"] = baseline_cost - out["total_cost_nzd"]
    out["annualized_savings_nzd"] = out["period_savings_nzd"] * annual_factor
    out["ten_year_break_even_capex_nzd"] = out["annualized_savings_nzd"] * 10
    out["fifteen_year_break_even_capex_nzd"] = out["annualized_savings_nzd"] * 15
    out["peak_import_reduction_pct"] = (
        1 - out["peak_import_kwh"] / out.attrs["baseline_peak_import_kwh"]
    ) * 100
    return out


def scenario_tables(
    model: ModelData,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    baseline = simulate_scenario(
        model,
        total_solar_kwp=CURRENT_SOLAR_KWP,
        battery_kwh=0.0,
        allow_offpeak_grid_charge=True,
    )
    baseline_cost = baseline["total_cost_nzd"]
    baseline_peak = baseline["peak_import_kwh"]

    battery_rows = []
    for capacity in BYD_HVM_USABLE_KWH:
        for grid_charge in (False, True):
            if capacity == 0 and not grid_charge:
                continue
            battery_rows.append(
                simulate_scenario(
                    model,
                    total_solar_kwp=CURRENT_SOLAR_KWP,
                    battery_kwh=capacity,
                    allow_offpeak_grid_charge=grid_charge,
                )
            )
    battery = pd.DataFrame(battery_rows)
    battery.attrs["baseline_peak_import_kwh"] = baseline_peak
    battery = add_savings_columns(battery, baseline_cost, model.days)

    matrix_rows = []
    for added_panels in ADDED_PANEL_COUNTS:
        total_kwp = CURRENT_SOLAR_KWP + added_panels * ADDED_PANEL_KW
        for capacity in BYD_HVM_USABLE_KWH:
            matrix_rows.append(
                simulate_scenario(
                    model,
                    total_solar_kwp=total_kwp,
                    battery_kwh=capacity,
                    allow_offpeak_grid_charge=True,
                )
            )
    matrix = pd.DataFrame(matrix_rows)
    matrix.attrs["baseline_peak_import_kwh"] = baseline_peak
    matrix = add_savings_columns(matrix, baseline_cost, model.days)

    larger_battery_rows = []
    for added_panels in ADDED_PANEL_COUNTS:
        total_kwp = CURRENT_SOLAR_KWP + added_panels * ADDED_PANEL_KW
        for capacity in EXTRA_LARGE_BATTERY_KWH:
            larger_battery_rows.append(
                simulate_scenario(
                    model,
                    total_solar_kwp=total_kwp,
                    battery_kwh=capacity,
                    allow_offpeak_grid_charge=True,
                )
            )
    larger_battery = pd.DataFrame(larger_battery_rows)
    larger_battery.attrs["baseline_peak_import_kwh"] = baseline_peak
    larger_battery = add_savings_columns(larger_battery, baseline_cost, model.days)

    return battery, matrix, larger_battery


def baseline_tables(
    model: ModelData,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    interval = model.interval
    actual_bill = bill_cost(
        interval["import"].to_numpy(dtype=float),
        interval["export"].to_numpy(dtype=float),
        model,
    )
    model_baseline = simulate_scenario(
        model,
        total_solar_kwp=CURRENT_SOLAR_KWP,
        battery_kwh=0.0,
        allow_offpeak_grid_charge=True,
    )

    ev_peak = float(interval.loc[interval["is_peak"], "ev"].sum())
    ev_offpeak = float(interval.loc[~interval["is_peak"], "ev"].sum())
    load = float(interval["load"].sum())
    solar = float(interval["solar"].sum())
    import_kwh = float(interval["import"].sum())
    export = float(interval["export"].sum())
    annual_factor = 365.25 / model.days

    baseline = pd.DataFrame(
        [
            {
                "metric": "Analysis start day",
                "value": model.start_day.date().isoformat(),
            },
            {"metric": "Analysis end day", "value": model.end_day.date().isoformat()},
            {"metric": "Days analysed", "value": model.days},
            {"metric": "Actual metered import kWh", "value": import_kwh},
            {
                "metric": "Actual metered peak import kWh",
                "value": actual_bill["peak_import_kwh"],
            },
            {
                "metric": "Actual metered off-peak import kWh",
                "value": actual_bill["offpeak_import_kwh"],
            },
            {"metric": "Actual metered export kWh", "value": export},
            {"metric": "Solar production kWh", "value": solar},
            {"metric": "Reconstructed household load kWh", "value": load},
            {"metric": "EV charging kWh", "value": ev_peak + ev_offpeak},
            {"metric": "EV peak charging kWh", "value": ev_peak},
            {"metric": "EV off-peak charging kWh", "value": ev_offpeak},
            {
                "metric": "EV peak charging %",
                "value": ev_peak / (ev_peak + ev_offpeak) * 100,
            },
            {
                "metric": "Actual metered bill NZD",
                "value": actual_bill["total_cost_nzd"],
            },
            {
                "metric": "Actual metered bill annualized NZD",
                "value": actual_bill["total_cost_nzd"] * annual_factor,
            },
            {
                "metric": "Model no-battery baseline bill NZD",
                "value": model_baseline["total_cost_nzd"],
            },
            {
                "metric": "Model no-battery baseline bill annualized NZD",
                "value": model_baseline["total_cost_nzd"] * annual_factor,
            },
            {
                "metric": "Negative load timing mismatch kWh clipped",
                "value": model.negative_load_kwh,
            },
            {
                "metric": "Negative load timing mismatch bins clipped",
                "value": model.negative_load_bins,
            },
        ]
    )

    daily = (
        interval.groupby(["date", "period"])[
            ["import", "export", "solar", "ev", "load"]
        ]
        .sum()
        .reset_index()
    )
    monthly = (
        interval.groupby(["month", "period"])[
            ["import", "export", "solar", "ev", "load"]
        ]
        .sum()
        .reset_index()
    )
    return baseline, daily, monthly


def recommendation_rows(
    battery: pd.DataFrame, matrix: pd.DataFrame, larger_battery: pd.DataFrame
) -> pd.DataFrame:
    current_grid = battery[
        (battery["total_solar_kwp"].round(2) == round(CURRENT_SOLAR_KWP, 2))
        & (battery["battery_mode"] == "solar + off-peak top-up")
        & (battery["battery_kwh"] > 0)
    ].copy()

    best_roi = (
        current_grid.assign(
            value_density=current_grid["annualized_savings_nzd"]
            / current_grid["battery_kwh"]
        )
        .sort_values("value_density", ascending=False)
        .iloc[0]
    )

    max_single_stack = current_grid.sort_values("battery_kwh").iloc[-1]
    ninety_pct_value = max_single_stack["annualized_savings_nzd"] * 0.90
    sweet_spot = (
        current_grid[current_grid["annualized_savings_nzd"] >= ninety_pct_value]
        .sort_values("battery_kwh")
        .iloc[0]
    )

    under_10kwp = matrix[matrix["total_solar_kwp"] <= MAX_TOTAL_SOLAR_KWP_TO_HIGHLIGHT]
    near_zero_single_stack = under_10kwp.sort_values(
        ["peak_import_kwh", "battery_kwh", "added_panels"]
    ).iloc[0]
    under_100 = under_10kwp[under_10kwp["peak_import_kwh"] <= 100]
    if len(under_100):
        smallest_under_100 = under_100.sort_values(
            ["added_panels", "battery_kwh"]
        ).iloc[0]
    else:
        smallest_under_100 = near_zero_single_stack

    large_under_10kwp = larger_battery[
        larger_battery["total_solar_kwp"] <= MAX_TOTAL_SOLAR_KWP_TO_HIGHLIGHT
    ]
    near_zero_large = large_under_10kwp.sort_values(
        ["peak_import_kwh", "battery_kwh", "added_panels"]
    ).iloc[0]

    rows = [
        (
            "Battery-only pure ROI",
            best_roi,
            "Highest annual savings per usable battery kWh on the current array.",
        ),
        (
            "Battery-only shoulder coverage",
            sweet_spot,
            "Smallest HVM option capturing at least 90% of the single-stack value.",
        ),
        (
            "Max single HVM stack",
            max_single_stack,
            "Best peak import reduction without adding panels, within one HVM tower.",
        ),
        (
            "Smallest single-stack near-zero peak option",
            smallest_under_100,
            "Smallest panel count found under 100 kWh/year residual peak import.",
        ),
        (
            "Best under 10 kWp with one HVM tower",
            near_zero_single_stack,
            "Lowest residual peak import while keeping total PV at or below about 10 kWp.",
        ),
        (
            "Near-zero peak import estimate",
            near_zero_large,
            "Shows the battery scale needed for true near-zero peak import.",
        ),
    ]

    records = []
    for label, row, note in rows:
        records.append(
            {
                "option": label,
                "added_panels": int(row["added_panels"]),
                "current_array_extra_panels": int(row["current_array_extra_panels"]),
                "second_array_panels": int(row["second_array_panels"]),
                "total_panels": int(CURRENT_PANEL_COUNT + row["added_panels"]),
                "total_solar_kwp": row["total_solar_kwp"],
                "battery_kwh": row["battery_kwh"],
                "annualized_savings_nzd": row["annualized_savings_nzd"],
                "ten_year_break_even_capex_nzd": row["ten_year_break_even_capex_nzd"],
                "peak_import_kwh": row["peak_import_kwh"],
                "peak_import_reduction_pct": row["peak_import_reduction_pct"],
                "export_kwh": row["export_kwh"],
                "note": note,
            }
        )
    return pd.DataFrame(records)


def assumptions_table() -> pd.DataFrame:
    assumptions = {
        "Timezone": TIMEZONE,
        "Peak window": f"{PEAK_START_HOUR}:00 to {PEAK_END_HOUR}:00",
        "Off-peak import NZD/kWh": RATES["offpeak_import"],
        "Peak import NZD/kWh": RATES["peak_import"],
        "Export NZD/kWh": RATES["export"],
        "Daily charge NZD/day": RATES["daily"],
        "Current panels": CURRENT_PANEL_COUNT,
        "Current panel rating kW": CURRENT_PANEL_KW,
        "Current solar kWp": CURRENT_SOLAR_KWP,
        "Added panel rating kW": ADDED_PANEL_KW,
        "Current array spare panel slots": CURRENT_ARRAY_SPARE_PANEL_SLOTS,
        "Round-trip battery efficiency": ROUND_TRIP_EFFICIENCY,
        "Battery power limit kW": BATTERY_POWER_LIMIT_KW
        or "Not limited in energy model",
        "Model interval": BIN_FREQUENCY,
        "BYD HVM capacities kWh": ", ".join(str(x) for x in BYD_HVM_USABLE_KWH[1:]),
    }
    return pd.DataFrame(
        [{"assumption": key, "value": value} for key, value in assumptions.items()]
    )


def write_outputs(
    model: ModelData,
    baseline: pd.DataFrame,
    daily: pd.DataFrame,
    monthly: pd.DataFrame,
    battery: pd.DataFrame,
    matrix: pd.DataFrame,
    larger_battery: pd.DataFrame,
    recommendations: pd.DataFrame,
) -> None:
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        assumptions_table().to_excel(writer, sheet_name="Assumptions", index=False)
        baseline.to_excel(writer, sheet_name="Baseline", index=False)
        recommendations.to_excel(writer, sheet_name="Recommendations", index=False)
        battery.to_excel(writer, sheet_name="Battery current PV", index=False)
        matrix.to_excel(writer, sheet_name="Solar battery matrix", index=False)
        larger_battery.to_excel(
            writer, sheet_name="Large battery sensitivity", index=False
        )
        monthly.to_excel(writer, sheet_name="Monthly baseline", index=False)
        daily.to_excel(writer, sheet_name="Daily baseline", index=False)

    write_markdown_summary(model, baseline, recommendations, battery, matrix)


def fmt_money(value: float) -> str:
    return f"${value:,.0f}"


def fmt_kwh(value: float) -> str:
    return f"{value:,.0f} kWh"


def markdown_table(df: pd.DataFrame) -> str:
    """Return a GitHub-style markdown table without optional dependencies."""
    display = df.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: f"{value:,.2f}")
        else:
            display[column] = display[column].astype(str)

    headers = list(display.columns)
    rows = display.values.tolist()
    table = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        table.append("| " + " | ".join(row) + " |")
    return "\n".join(table)


def row_for_option(recommendations: pd.DataFrame, option: str) -> pd.Series:
    return recommendations.loc[recommendations["option"] == option].iloc[0]


def strict_and_oversize_panel_counts() -> tuple[int, int | None]:
    strict = max(
        added
        for added in ADDED_PANEL_COUNTS
        if CURRENT_SOLAR_KWP + added * ADDED_PANEL_KW
        <= MAX_TOTAL_SOLAR_KWP_TO_HIGHLIGHT
    )
    oversize_options = [
        added
        for added in ADDED_PANEL_COUNTS
        if CURRENT_SOLAR_KWP + added * ADDED_PANEL_KW > MAX_TOTAL_SOLAR_KWP_TO_HIGHLIGHT
    ]
    return strict, min(oversize_options) if oversize_options else None


def write_markdown_summary(
    model: ModelData,
    baseline: pd.DataFrame,
    recommendations: pd.DataFrame,
    battery: pd.DataFrame,
    matrix: pd.DataFrame,
) -> None:
    baseline_values = dict(zip(baseline["metric"], baseline["value"]))
    roi = row_for_option(recommendations, "Battery-only pure ROI")
    shoulder = row_for_option(recommendations, "Battery-only shoulder coverage")
    max_stack = row_for_option(recommendations, "Max single HVM stack")
    under_100 = row_for_option(
        recommendations, "Smallest single-stack near-zero peak option"
    )
    under_10 = row_for_option(recommendations, "Best under 10 kWp with one HVM tower")
    near_zero = row_for_option(recommendations, "Near-zero peak import estimate")
    strict_panels, oversize_panels = strict_and_oversize_panel_counts()
    sensitivity_counts = {0, 1, 4, 8, strict_panels}
    if oversize_panels is not None:
        sensitivity_counts.add(oversize_panels)

    solar_only = matrix[
        (matrix["battery_kwh"] == 0)
        & (matrix["added_panels"].isin(sorted(sensitivity_counts)))
    ][
        [
            "added_panels",
            "current_array_extra_panels",
            "second_array_panels",
            "total_solar_kwp",
            "annualized_savings_nzd",
            "peak_import_kwh",
            "export_kwh",
        ]
    ]

    current_battery = battery[
        (battery["battery_mode"] == "solar + off-peak top-up")
        & (battery["battery_kwh"] > 0)
    ][
        [
            "battery_kwh",
            "annualized_savings_nzd",
            "ten_year_break_even_capex_nzd",
            "peak_import_kwh",
            "export_kwh",
            "battery_charged_from_grid_kwh",
            "battery_charged_from_solar_kwh",
        ]
    ]

    lines: list[str] = [
        "# Home Energy Options Summary",
        "",
        f"Analysis period: {model.start_day.date()} to {model.end_day.date()} "
        f"({model.days} complete days).",
        "",
        "## Current Site",
        "",
        f"- Actual metered import: {fmt_kwh(float(baseline_values['Actual metered import kWh']))}.",
        f"- Actual metered export: {fmt_kwh(float(baseline_values['Actual metered export kWh']))}.",
        f"- Solar production: {fmt_kwh(float(baseline_values['Solar production kWh']))}.",
        f"- Reconstructed household load: {fmt_kwh(float(baseline_values['Reconstructed household load kWh']))}.",
        f"- EV charging: {fmt_kwh(float(baseline_values['EV charging kWh']))}, "
        f"with {float(baseline_values['EV peak charging %']):.1f}% during peak hours.",
        f"- Actual metered bill for the analysed period: "
        f"{fmt_money(float(baseline_values['Actual metered bill NZD']))}; "
        f"annualised: {fmt_money(float(baseline_values['Actual metered bill annualized NZD']))}.",
        "",
        "## Battery View",
        "",
        f"- Pure ROI battery choice: HVM {roi['battery_kwh']:.2f} kWh, "
        f"about {fmt_money(roi['annualized_savings_nzd'])}/year. "
        f"A 10-year simple payback would need installed cost below "
        f"{fmt_money(roi['ten_year_break_even_capex_nzd'])}.",
        f"- Shoulder coverage sweet spot: HVM {shoulder['battery_kwh']:.2f} kWh, "
        f"about {fmt_money(shoulder['annualized_savings_nzd'])}/year and "
        f"{fmt_kwh(shoulder['peak_import_kwh'])} residual peak import.",
        f"- Max single HVM stack: HVM {max_stack['battery_kwh']:.2f} kWh leaves "
        f"{fmt_kwh(max_stack['peak_import_kwh'])} residual peak import and saves "
        f"about {fmt_money(max_stack['annualized_savings_nzd'])}/year.",
        "",
        "Battery-only scenarios, current array:",
        "",
        markdown_table(current_battery.round(2)),
        "",
        "## Solar Array View",
        "",
        f"- Added-panel scenarios now use {ADDED_PANEL_KW * 1000:.0f} W panels. "
        f"The first added panel is allocated to the spare slot on the current array; "
        "remaining added panels are counted as second-array panels.",
        f"- Strict ~10 kWp total array: add {strict_panels} x "
        f"{ADDED_PANEL_KW * 1000:.0f} W panels "
        f"({min(strict_panels, CURRENT_ARRAY_SPARE_PANEL_SLOTS)} current-array extra + "
        f"{max(0, strict_panels - CURRENT_ARRAY_SPARE_PANEL_SLOTS)} second-array panels; "
        f"{CURRENT_PANEL_COUNT + strict_panels} total panels; "
        f"{CURRENT_SOLAR_KWP + strict_panels * ADDED_PANEL_KW:.2f} kWp).",
        (
            f"- The next step above 10 kWp is {oversize_panels} added panels, giving "
            f"{CURRENT_SOLAR_KWP + oversize_panels * ADDED_PANEL_KW:.2f} kWp; "
            "check this with the installer if modest DC oversizing is acceptable."
            if oversize_panels is not None
            else "- No added-panel count in the configured range exceeds the 10 kWp marker."
        ),
        "- Solar-only savings are limited because extra daytime generation is heavily exported at the low export rate.",
        "",
        "Solar-only sensitivity:",
        "",
        markdown_table(solar_only.round(2)),
        "",
        "## Combined Options",
        "",
        f"- Smallest single-stack option under 100 kWh/year peak import: add "
        f"{int(under_100['added_panels'])} x {ADDED_PANEL_KW * 1000:.0f} W panels "
        f"({int(under_100['current_array_extra_panels'])} current-array extra + "
        f"{int(under_100['second_array_panels'])} second-array) and use HVM "
        f"{under_100['battery_kwh']:.2f} kWh. Annualized saving: "
        f"{fmt_money(under_100['annualized_savings_nzd'])}.",
        f"- Best modelled option under about 10 kWp with one HVM tower: add "
        f"{int(under_10['added_panels'])} x {ADDED_PANEL_KW * 1000:.0f} W panels "
        f"({int(under_10['current_array_extra_panels'])} current-array extra + "
        f"{int(under_10['second_array_panels'])} second-array) "
        f"({under_10['total_solar_kwp']:.2f} kWp total) and HVM "
        f"{under_10['battery_kwh']:.2f} kWh. Residual peak import: "
        f"{fmt_kwh(under_10['peak_import_kwh'])}.",
        f"- True near-zero peak import needs roughly {near_zero['battery_kwh']:.1f} kWh "
        f"of usable battery in this model, beyond a single HVM tower.",
        "",
        "## Notes",
        "",
        "- Savings are before system capital cost, finance, maintenance, degradation, and installer-specific limits.",
        "- The dispatch assumes the battery can charge from solar surplus and can top up during off-peak hours only enough for the next peak window.",
        "- Instantaneous power limits are not enabled by default because the source meters have irregular timestamp gaps; set BATTERY_POWER_LIMIT_KW in the script to test a specific inverter limit.",
        "- The daily fixed charge is included in total bills but does not change between options.",
        "",
    ]

    OUTPUT_MARKDOWN.write_text("\n".join(lines), encoding="utf-8")


def print_key_results(
    baseline: pd.DataFrame, recommendations: pd.DataFrame, battery: pd.DataFrame
) -> None:
    baseline_values = dict(zip(baseline["metric"], baseline["value"]))
    print(f"Wrote {OUTPUT_XLSX}")
    print(f"Wrote {OUTPUT_MARKDOWN}")
    print()
    print("Current site:")
    print(
        f"  Import {float(baseline_values['Actual metered import kWh']):,.0f} kWh | "
        f"Export {float(baseline_values['Actual metered export kWh']):,.0f} kWh | "
        f"Solar {float(baseline_values['Solar production kWh']):,.0f} kWh"
    )
    print(
        f"  EV charging {float(baseline_values['EV charging kWh']):,.0f} kWh "
        f"({float(baseline_values['EV peak charging %']):.1f}% peak)"
    )
    print()
    print("Recommended decision points:")
    for _, row in recommendations.iterrows():
        print(
            f"  {row['option']}: add {int(row['added_panels'])} x "
            f"{ADDED_PANEL_KW * 1000:.0f} W panels "
            f"({int(row['current_array_extra_panels'])} current-array extra, "
            f"{int(row['second_array_panels'])} second-array), "
            f"{row['total_solar_kwp']:.2f} kWp total, "
            f"{row['battery_kwh']:.2f} kWh battery, "
            f"{row['annualized_savings_nzd']:,.0f} NZD/year, "
            f"{row['peak_import_kwh']:,.0f} kWh residual peak import"
        )


def main() -> None:
    model = build_model_data()
    baseline, daily, monthly = baseline_tables(model)
    battery, matrix, larger_battery = scenario_tables(model)
    recommendations = recommendation_rows(battery, matrix, larger_battery)
    write_outputs(
        model,
        baseline,
        daily,
        monthly,
        battery,
        matrix,
        larger_battery,
        recommendations,
    )
    print_key_results(baseline, recommendations, battery)


if __name__ == "__main__":
    main()
