"""
Energy Peak / Off-Peak Analysis
================================
Analyses Home Assistant energy meter history exported as CSV.

Expected CSV columns:
  entity_id    - sensor name (ignored, single-sensor files assumed)
  state        - cumulative meter reading in MWh (Fronius meter default)
  last_changed - UTC ISO8601 timestamp

Peak hours:    07:00 – 21:00 NZDT/NZST (Pacific/Auckland)
Off-Peak hours: 21:00 – 07:00 NZDT/NZST (Pacific/Auckland)

Usage:
  python energy_analysis.py                        # uses INPUT_FILE below
  python energy_analysis.py my_export.csv          # pass file as argument
  python energy_analysis.py my_export.csv --xlsx   # also write Excel output
"""

import sys
import pandas as pd

# ── Configuration ──────────────────────────────────────────────────────────────
INPUT_FILE   = "history.csv"          # default input filename
TIMEZONE     = "Pacific/Auckland"     # NZDT/NZST, handles DST automatically
PEAK_START   = 7                      # hour (24h), inclusive
PEAK_END     = 21                     # hour (24h), exclusive  → 07:00–20:59
UNIT         = "MWh"                  # sensor unit: "MWh" or "kWh"
SPIKE_FILTER = 100                    # max plausible kWh per reading interval
# ──────────────────────────────────────────────────────────────────────────────


def load_and_prepare(filepath: str) -> pd.DataFrame:
    """Load CSV, convert timezone, compute consumption per interval."""
    print(f"Loading {filepath} …")
    df = pd.read_csv(filepath)

    required = {"state", "last_changed"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing columns: {missing}")

    df["last_changed"] = pd.to_datetime(df["last_changed"], utc=True)
    df["state"] = pd.to_numeric(df["state"], errors="coerce")
    df = df.dropna(subset=["state", "last_changed"])
    df = df.sort_values("last_changed").reset_index(drop=True)

    # Convert to local time
    df["nzdt"] = df["last_changed"].dt.tz_convert(TIMEZONE)

    # Convert MWh → kWh if needed
    if UNIT.upper() == "MWH":
        df["state_kwh"] = df["state"] * 1000
    else:
        df["state_kwh"] = df["state"]

    # Consumption = diff between consecutive readings
    df["consumption_kwh"] = df["state_kwh"].diff().fillna(0)

    # Filter out negatives (meter resets) and spikes (data gaps)
    n_before = len(df)
    df = df[(df["consumption_kwh"] >= 0) & (df["consumption_kwh"] <= SPIKE_FILTER)]
    n_dropped = n_before - len(df)
    if n_dropped:
        print(f"  ⚠  Dropped {n_dropped} rows (negative diffs or spikes > {SPIKE_FILTER} kWh)")

    # Tag peak vs off-peak by start time of each interval
    df["period"] = df["nzdt"].apply(
        lambda t: "Peak" if PEAK_START <= t.hour < PEAK_END else "Off-Peak"
    )
    df["month"] = df["nzdt"].dt.to_period("M")
    df["date"]  = df["nzdt"].dt.date

    print(f"  {len(df):,} rows | "
          f"{df['nzdt'].min().date()} → {df['nzdt'].max().date()} "
          f"({df['nzdt'].max().date() - df['nzdt'].min().date()} days)\n")
    return df


def print_totals(df: pd.DataFrame):
    print("=" * 54)
    print("TOTAL CONSUMPTION (kWh)")
    print("=" * 54)
    total = df.groupby("period")["consumption_kwh"].sum()
    grand  = total.sum()
    for period in ["Peak", "Off-Peak"]:
        v = total.get(period, 0)
        print(f"  {period:<12} {v:>10,.1f} kWh   ({v/grand*100:.1f}%)")
    print(f"  {'Grand Total':<12} {grand:>10,.1f} kWh")
    print()
    return total


def print_monthly(df: pd.DataFrame):
    print("=" * 54)
    print("MONTHLY CONSUMPTION (kWh)")
    print("=" * 54)
    monthly = (df.groupby(["month", "period"])["consumption_kwh"]
                 .sum().unstack(fill_value=0))
    for col in ["Peak", "Off-Peak"]:
        if col not in monthly.columns:
            monthly[col] = 0
    monthly["Total"]  = monthly["Peak"] + monthly["Off-Peak"]
    monthly["Peak %"] = (monthly["Peak"] / monthly["Total"] * 100).round(1)

    print(f"  {'Month':<10} {'Off-Peak':>10} {'Peak':>10} {'Total':>10} {'Peak %':>8}")
    print("  " + "-" * 50)
    for m, row in monthly.iterrows():
        print(f"  {str(m):<10} {row['Off-Peak']:>10.1f} {row['Peak']:>10.1f} "
              f"{row['Total']:>10.1f} {row['Peak %']:>7.1f}%")
    print()
    return monthly


def print_daily_averages(df: pd.DataFrame):
    print("=" * 54)
    print("AVERAGE DAILY CONSUMPTION PER MONTH (kWh)")
    print("=" * 54)
    daily = (df.groupby(["date", "period"])["consumption_kwh"]
               .sum().unstack(fill_value=0))
    for col in ["Peak", "Off-Peak"]:
        if col not in daily.columns:
            daily[col] = 0
    daily.index = pd.to_datetime(daily.index)
    daily["Total"] = daily["Peak"] + daily["Off-Peak"]

    avg = daily.groupby(daily.index.to_period("M")).mean()
    print(f"  {'Month':<10} {'Off-Peak':>10} {'Peak':>10} {'Total':>10}")
    print("  " + "-" * 42)
    for m, row in avg.iterrows():
        print(f"  {str(m):<10} {row['Off-Peak']:>10.2f} {row['Peak']:>10.2f} {row['Total']:>10.2f}")
    print()
    return daily


def print_daily_stats(daily: pd.DataFrame):
    print("=" * 54)
    print("DAILY CONSUMPTION STATISTICS (kWh, all days)")
    print("=" * 54)
    for label, series in [("Off-Peak", daily["Off-Peak"]),
                           ("Peak",     daily["Peak"]),
                           ("Total",    daily["Total"])]:
        print(f"  {label}:")
        print(f"    Mean   {series.mean():>8.2f}    Median {series.median():>8.2f}")
        print(f"    Min    {series.min():>8.2f}    Max    {series.max():>8.2f}")
        print(f"    StdDev {series.std():>8.2f}")
    print(f"\n  Days analysed: {len(daily)}")
    print()


def write_excel(df: pd.DataFrame, monthly, daily, output_path: str):
    """Write summary tables to an Excel workbook."""
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("  ⚠  openpyxl not installed — skipping Excel output (pip install openpyxl)")
        return

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        # Raw daily
        daily_out = daily.reset_index()
        daily_out.to_excel(writer, sheet_name="Daily", index=False)

        # Monthly
        monthly.reset_index().to_excel(writer, sheet_name="Monthly", index=False)

        # Totals
        totals = df.groupby("period")["consumption_kwh"].sum().reset_index()
        totals.columns = ["Period", "kWh"]
        totals.to_excel(writer, sheet_name="Totals", index=False)

    print(f"  Excel written → {output_path}")


def main():
    filepath = sys.argv[1] if len(sys.argv) > 1 else INPUT_FILE
    write_xlsx = "--xlsx" in sys.argv

    df = load_and_prepare(filepath)

    print_totals(df)
    monthly = print_monthly(df)
    daily   = print_daily_averages(df)
    print_daily_stats(daily)

    if write_xlsx:
        out = filepath.replace(".csv", "_analysis.xlsx")
        write_excel(df, monthly, daily, out)


if __name__ == "__main__":
    main()
