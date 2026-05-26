"""
PV System ROI Analysis
======================

Calculates simple payback and 25-year savings for the installed 6.12 kWp PV
system and inverter, using the same reconstructed load/solar model as
home_energy_options.py.

Outputs:
  analysis_files/pv_system_roi_analysis.xlsx
  analysis_files/pv_system_roi_summary.md
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from home_energy_options import (
    CURRENT_SOLAR_KWP,
    RATES as CURRENT_RATES,
    build_model_data,
)

OUTPUT_DIR = Path("summaries")
OUTPUT_XLSX = OUTPUT_DIR / "pv_system_roi_analysis.xlsx"
OUTPUT_MARKDOWN = OUTPUT_DIR / "pv_system_roi_summary.md"

PV_INSTALL_COST_NZD = 20_650.0
INSTALL_DATE = date(2022, 2, 1)
OLD_RATES_END_DATE = date(2026, 3, 31)
PROJECTION_YEARS = 25

OLD_RATES = {
    "offpeak_import": 0.19435,
    "peak_import": 0.388815,
    "daily": 1.035,
    "export": 0.144,
}

PRE_PV_NO_EV_CONSUMPTION_KWH_PER_YEAR = 11_300.0

# These are context only. Current-EV ROI uses measured Home Assistant EV charging
# from the same raw files as the rest of the analysis.
EV_CONTEXT = [
    {
        "vehicle": "Tesla",
        "annual_km": 26_000,
        "kwh_per_km": 0.153,
        "home_charge_pct": 0.65,
        "dc_charge_pct": 0.35,
        "start_date": date(2023, 3, 1),
    },
    {
        "vehicle": "MG",
        "annual_km": 13_000,
        "kwh_per_km": 0.190,
        "home_charge_pct": 0.60,
        "dc_charge_pct": 0.40,
        "start_date": date(2024, 12, 1),
    },
]


def bill_cost(
    import_kwh: np.ndarray,
    export_kwh: np.ndarray,
    is_peak: np.ndarray,
    days: int,
    rates: dict,
) -> dict:
    peak_import = float(import_kwh[is_peak].sum())
    offpeak_import = float(import_kwh[~is_peak].sum())
    export = float(export_kwh.sum())
    variable_cost = (
        offpeak_import * rates["offpeak_import"]
        + peak_import * rates["peak_import"]
        - export * rates["export"]
    )
    daily_cost = days * rates["daily"]
    return {
        "offpeak_import_kwh": offpeak_import,
        "peak_import_kwh": peak_import,
        "export_kwh": export,
        "variable_cost_nzd": variable_cost,
        "daily_cost_nzd": daily_cost,
        "total_cost_nzd": variable_cost + daily_cost,
    }


def scenario_profiles(model) -> dict:
    interval = model.interval
    annual_factor = 365.25 / model.days

    current_load = interval["load"].to_numpy(dtype=float)
    measured_ev = interval["ev"].to_numpy(dtype=float)
    non_ev_measured = np.clip(current_load - measured_ev, 0, None)
    annual_non_ev = float(non_ev_measured.sum() * annual_factor)
    non_ev_scale = PRE_PV_NO_EV_CONSUMPTION_KWH_PER_YEAR / annual_non_ev
    no_ev_load = non_ev_measured * non_ev_scale

    return {
        "Current EVs, measured home load": {
            "load_kwh": current_load,
            "description": (
                "Measured reconstructed household load, including Home Assistant "
                "EV charging."
            ),
        },
        "No EVs, 11.3 MWh/year base load": {
            "load_kwh": no_ev_load,
            "description": (
                "Measured non-EV load shape scaled to the stated pre-PV annual "
                "consumption of 11,300 kWh."
            ),
        },
    }


def annual_scenario_bill(
    model, scenario_name: str, load_kwh: np.ndarray, rates: dict
) -> dict:
    interval = model.interval
    annual_factor = 365.25 / model.days
    solar_kwh = interval["solar"].to_numpy(dtype=float)
    is_peak = model.is_peak

    no_pv = bill_cost(load_kwh, np.zeros_like(load_kwh), is_peak, model.days, rates)

    net = load_kwh - solar_kwh
    with_pv_import = np.clip(net, 0, None)
    with_pv_export = np.clip(-net, 0, None)
    with_pv = bill_cost(with_pv_import, with_pv_export, is_peak, model.days, rates)

    return {
        "scenario": scenario_name,
        "load_kwh_per_year": float(load_kwh.sum() * annual_factor),
        "solar_kwh_per_year": float(solar_kwh.sum() * annual_factor),
        "rate_set": "custom",
        "annual_no_pv_bill_nzd": no_pv["total_cost_nzd"] * annual_factor,
        "annual_with_pv_bill_nzd": with_pv["total_cost_nzd"] * annual_factor,
        "annual_savings_nzd": (no_pv["total_cost_nzd"] - with_pv["total_cost_nzd"])
        * annual_factor,
        "annual_no_pv_peak_import_kwh": no_pv["peak_import_kwh"] * annual_factor,
        "annual_no_pv_offpeak_import_kwh": no_pv["offpeak_import_kwh"] * annual_factor,
        "annual_with_pv_peak_import_kwh": with_pv["peak_import_kwh"] * annual_factor,
        "annual_with_pv_offpeak_import_kwh": with_pv["offpeak_import_kwh"]
        * annual_factor,
        "annual_export_kwh": with_pv["export_kwh"] * annual_factor,
        "annual_savings_pct_of_install_cost": (
            (no_pv["total_cost_nzd"] - with_pv["total_cost_nzd"])
            * annual_factor
            / PV_INSTALL_COST_NZD
            * 100
        ),
        "simple_break_even_years": (
            PV_INSTALL_COST_NZD
            / ((no_pv["total_cost_nzd"] - with_pv["total_cost_nzd"]) * annual_factor)
        ),
    }


def annual_bill_table(model) -> pd.DataFrame:
    rows = []
    profiles = scenario_profiles(model)
    for scenario_name, profile in profiles.items():
        for rate_name, rates in [
            ("Old rates to Mar 2026", OLD_RATES),
            ("Current rates", CURRENT_RATES),
        ]:
            row = annual_scenario_bill(model, scenario_name, profile["load_kwh"], rates)
            row["rate_set"] = rate_name
            row["profile_description"] = profile["description"]
            rows.append(row)
    return pd.DataFrame(rows)


def overlap_days(start: date, end: date, window_start: date, window_end: date) -> int:
    latest_start = max(start, window_start)
    earliest_end = min(end, window_end)
    if latest_start > earliest_end:
        return 0
    return (earliest_end - latest_start).days + 1


def break_even_from_install(
    old_annual_savings: float, current_annual_savings: float
) -> dict:
    old_days = max((OLD_RATES_END_DATE - INSTALL_DATE).days + 1, 0)
    old_daily = old_annual_savings / 365.25
    current_daily = current_annual_savings / 365.25
    old_cumulative = old_days * old_daily

    if old_cumulative >= PV_INSTALL_COST_NZD:
        days_to_break_even = PV_INSTALL_COST_NZD / old_daily
    else:
        days_to_break_even = (
            old_days + (PV_INSTALL_COST_NZD - old_cumulative) / current_daily
        )

    break_even_date = INSTALL_DATE + timedelta(days=int(round(days_to_break_even)))
    return {
        "break_even_years_from_install": days_to_break_even / 365.25,
        "break_even_date": break_even_date.isoformat(),
        "savings_to_mar_2026_nzd": old_cumulative,
        "remaining_after_mar_2026_nzd": max(PV_INSTALL_COST_NZD - old_cumulative, 0),
    }


def projection_table(annual_bills: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scenario in annual_bills["scenario"].unique():
        old_savings = float(
            annual_bills[
                (annual_bills["scenario"] == scenario)
                & (annual_bills["rate_set"] == "Old rates to Mar 2026")
            ]["annual_savings_nzd"].iloc[0]
        )
        current_savings = float(
            annual_bills[
                (annual_bills["scenario"] == scenario)
                & (annual_bills["rate_set"] == "Current rates")
            ]["annual_savings_nzd"].iloc[0]
        )
        cumulative = 0.0
        for year_index in range(1, PROJECTION_YEARS + 1):
            year_start = date(
                INSTALL_DATE.year + year_index - 1, INSTALL_DATE.month, INSTALL_DATE.day
            )
            year_end = date(
                INSTALL_DATE.year + year_index, INSTALL_DATE.month, INSTALL_DATE.day
            ) - timedelta(days=1)
            total_days = (year_end - year_start).days + 1
            old_days = overlap_days(
                year_start, year_end, INSTALL_DATE, OLD_RATES_END_DATE
            )
            current_days = total_days - old_days
            year_savings = (
                old_days * old_savings / 365.25
                + current_days * current_savings / 365.25
            )
            cumulative += year_savings
            rows.append(
                {
                    "scenario": scenario,
                    "projection_year": year_index,
                    "year_start": year_start.isoformat(),
                    "year_end": year_end.isoformat(),
                    "old_rate_days": old_days,
                    "current_rate_days": current_days,
                    "year_savings_nzd": year_savings,
                    "cumulative_savings_nzd": cumulative,
                    "net_after_install_cost_nzd": cumulative - PV_INSTALL_COST_NZD,
                    "net_roi_pct": (cumulative - PV_INSTALL_COST_NZD)
                    / PV_INSTALL_COST_NZD
                    * 100,
                }
            )
    return pd.DataFrame(rows)


def payback_table(annual_bills: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scenario in annual_bills["scenario"].unique():
        scenario_rows = annual_bills[annual_bills["scenario"] == scenario]
        old = scenario_rows[scenario_rows["rate_set"] == "Old rates to Mar 2026"].iloc[
            0
        ]
        current = scenario_rows[scenario_rows["rate_set"] == "Current rates"].iloc[0]
        combined = break_even_from_install(
            float(old["annual_savings_nzd"]),
            float(current["annual_savings_nzd"]),
        )
        rows.append(
            {
                "scenario": scenario,
                "install_cost_nzd": PV_INSTALL_COST_NZD,
                "old_rate_annual_savings_nzd": old["annual_savings_nzd"],
                "current_rate_annual_savings_nzd": current["annual_savings_nzd"],
                "current_rate_annual_roi_pct": current[
                    "annual_savings_pct_of_install_cost"
                ],
                "simple_break_even_years_old_rates": old["simple_break_even_years"],
                "simple_break_even_years_current_rates": current[
                    "simple_break_even_years"
                ],
                **combined,
            }
        )
    return pd.DataFrame(rows)


def ev_context_table(model) -> pd.DataFrame:
    annual_factor = 365.25 / model.days
    rows = []
    for item in EV_CONTEXT:
        annual_vehicle_kwh = item["annual_km"] * item["kwh_per_km"]
        rows.append(
            {
                "vehicle": item["vehicle"],
                "annual_km": item["annual_km"],
                "kwh_per_100km": item["kwh_per_km"] * 100,
                "annual_vehicle_energy_kwh": annual_vehicle_kwh,
                "home_charge_pct": item["home_charge_pct"],
                "dc_charge_pct": item["dc_charge_pct"],
                "estimated_home_kwh": annual_vehicle_kwh * item["home_charge_pct"],
                "estimated_dc_kwh": annual_vehicle_kwh * item["dc_charge_pct"],
                "start_date": item["start_date"].isoformat(),
            }
        )
    rows.append(
        {
            "vehicle": "Home Assistant measured EV charging",
            "annual_km": None,
            "kwh_per_100km": None,
            "annual_vehicle_energy_kwh": None,
            "home_charge_pct": None,
            "dc_charge_pct": None,
            "estimated_home_kwh": float(model.interval["ev"].sum() * annual_factor),
            "estimated_dc_kwh": None,
            "start_date": "measurement period",
        }
    )
    return pd.DataFrame(rows)


def assumptions_table(model) -> pd.DataFrame:
    assumptions = {
        "PV install cost NZD": PV_INSTALL_COST_NZD,
        "PV install date assumed": INSTALL_DATE.isoformat(),
        "Old rates end date assumed": OLD_RATES_END_DATE.isoformat(),
        "Projection years": PROJECTION_YEARS,
        "Current solar kWp": CURRENT_SOLAR_KWP,
        "Pre-PV no-EV annual consumption kWh": PRE_PV_NO_EV_CONSUMPTION_KWH_PER_YEAR,
        "Analysis data start": model.start_day.date().isoformat(),
        "Analysis data end": model.end_day.date().isoformat(),
        "Analysis data days": model.days,
        "Projection price inflation": "0%",
        "Solar degradation": "0% in base projection",
        "DC charging treatment": "Excluded from PV payback because it is not offset by roof PV.",
    }
    return pd.DataFrame(
        [{"assumption": key, "value": value} for key, value in assumptions.items()]
    )


def fmt_money(value: float) -> str:
    return f"${value:,.0f}"


def fmt_years(value: float) -> str:
    return f"{value:.1f} years"


def markdown_table(df: pd.DataFrame) -> str:
    display = df.copy()
    display = display.replace({np.nan: ""})
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(
                lambda value: "" if pd.isna(value) else f"{value:,.2f}"
            )
        else:
            display[column] = display[column].astype(str)
    lines = [
        "| " + " | ".join(display.columns) + " |",
        "| " + " | ".join(["---"] * len(display.columns)) + " |",
    ]
    for row in display.values.tolist():
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def write_markdown(
    annual_bills: pd.DataFrame,
    payback: pd.DataFrame,
    projection: pd.DataFrame,
    ev_context: pd.DataFrame,
) -> None:
    summary_rows = []
    for scenario in annual_bills["scenario"].unique():
        current = annual_bills[
            (annual_bills["scenario"] == scenario)
            & (annual_bills["rate_set"] == "Current rates")
        ].iloc[0]
        pb = payback[payback["scenario"] == scenario].iloc[0]
        year_25 = projection[
            (projection["scenario"] == scenario)
            & (projection["projection_year"] == PROJECTION_YEARS)
        ].iloc[0]
        summary_rows.append(
            {
                "scenario": scenario,
                "annual_no_pv_bill_current_rates": current["annual_no_pv_bill_nzd"],
                "annual_with_pv_bill_current_rates": current["annual_with_pv_bill_nzd"],
                "annual_savings_current_rates": current["annual_savings_nzd"],
                "break_even_from_install": pb["break_even_years_from_install"],
                "break_even_date": pb["break_even_date"],
                "25yr_cumulative_savings": year_25["cumulative_savings_nzd"],
                "25yr_net_after_install": year_25["net_after_install_cost_nzd"],
                "25yr_net_roi_pct": year_25["net_roi_pct"],
            }
        )
    summary = pd.DataFrame(summary_rows)

    lines = [
        "# PV System ROI Summary",
        "",
        f"Install cost modelled: {fmt_money(PV_INSTALL_COST_NZD)}.",
        f"Install date assumed: {INSTALL_DATE.isoformat()}; old rates run through "
        f"{OLD_RATES_END_DATE.isoformat()}, then current rates are used.",
        "Projection uses flat tariffs, no price inflation, and no solar degradation.",
        "",
        "## Headline Results",
        "",
        markdown_table(summary.round(2)),
        "",
        "## Annual Bills By Tariff",
        "",
        markdown_table(
            annual_bills[
                [
                    "scenario",
                    "rate_set",
                    "load_kwh_per_year",
                    "annual_no_pv_bill_nzd",
                    "annual_with_pv_bill_nzd",
                    "annual_savings_nzd",
                    "annual_savings_pct_of_install_cost",
                    "simple_break_even_years",
                    "annual_export_kwh",
                ]
            ].round(2)
        ),
        "",
        "## EV Context",
        "",
        "Current-EV ROI uses measured Home Assistant home charging. DC charging is shown for context only because roof PV cannot offset public DC charging.",
        "",
        markdown_table(ev_context.round(2)),
        "",
        "## Notes",
        "",
        "- The no-EV scenario uses your stated pre-PV consumption of 11,300 kWh/year and the measured non-EV load shape.",
        "- The current-EV scenario uses the reconstructed measured household load, so EV home charging is already part of the load.",
        "- Daily fixed charges are included in annual bills, but they do not affect PV savings because they apply with or without PV.",
        "",
    ]
    OUTPUT_MARKDOWN.write_text("\n".join(lines), encoding="utf-8")


def write_outputs(
    assumptions: pd.DataFrame,
    annual_bills: pd.DataFrame,
    payback: pd.DataFrame,
    projection: pd.DataFrame,
    ev_context: pd.DataFrame,
) -> None:
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        assumptions.to_excel(writer, sheet_name="Assumptions", index=False)
        annual_bills.to_excel(writer, sheet_name="Annual bills", index=False)
        payback.to_excel(writer, sheet_name="Payback", index=False)
        projection.to_excel(writer, sheet_name="25 year projection", index=False)
        ev_context.to_excel(writer, sheet_name="EV context", index=False)

    write_markdown(annual_bills, payback, projection, ev_context)


def print_summary(
    annual_bills: pd.DataFrame, payback: pd.DataFrame, projection: pd.DataFrame
) -> None:
    print(f"Wrote {OUTPUT_XLSX}")
    print(f"Wrote {OUTPUT_MARKDOWN}")
    print()
    for scenario in annual_bills["scenario"].unique():
        current = annual_bills[
            (annual_bills["scenario"] == scenario)
            & (annual_bills["rate_set"] == "Current rates")
        ].iloc[0]
        pb = payback[payback["scenario"] == scenario].iloc[0]
        year_25 = projection[
            (projection["scenario"] == scenario)
            & (projection["projection_year"] == PROJECTION_YEARS)
        ].iloc[0]
        print(scenario)
        print(
            f"  Current-rate annual bill: no PV {fmt_money(current['annual_no_pv_bill_nzd'])}, "
            f"with PV {fmt_money(current['annual_with_pv_bill_nzd'])}, "
            f"savings {fmt_money(current['annual_savings_nzd'])}"
        )
        print(
            f"  Break-even from install: {fmt_years(pb['break_even_years_from_install'])} "
            f"({pb['break_even_date']})"
        )
        print(
            f"  25-year savings: {fmt_money(year_25['cumulative_savings_nzd'])}; "
            f"net after install cost {fmt_money(year_25['net_after_install_cost_nzd'])}"
        )


def main() -> None:
    model = build_model_data()
    assumptions = assumptions_table(model)
    annual_bills = annual_bill_table(model)
    payback = payback_table(annual_bills)
    projection = projection_table(annual_bills)
    ev_context = ev_context_table(model)
    write_outputs(assumptions, annual_bills, payback, projection, ev_context)
    print_summary(annual_bills, payback, projection)


if __name__ == "__main__":
    main()
