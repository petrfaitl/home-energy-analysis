# PV System ROI Summary

Install cost modelled: $20,650.
Install date assumed: 2022-02-01; old rates run through 2026-03-31, then current rates are used.
Projection uses flat tariffs, no price inflation, and no solar degradation.

## Headline Results

| scenario | annual_no_pv_bill_current_rates | annual_with_pv_bill_current_rates | annual_savings_current_rates | break_even_from_install | break_even_date | 25yr_cumulative_savings | 25yr_net_after_install | 25yr_net_roi_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Current EVs, measured home load | 5,953.02 | 3,075.26 | 2,877.76 | 7.42 | 2029-07-03 | 71,247.99 | 50,597.99 | 245.03 |
| No EVs, 11.3 MWh/year base load | 4,719.06 | 2,066.25 | 2,652.81 | 8.01 | 2030-02-05 | 65,714.25 | 45,064.25 | 218.23 |

## Annual Bills By Tariff

| scenario | rate_set | load_kwh_per_year | annual_no_pv_bill_nzd | annual_with_pv_bill_nzd | annual_savings_nzd | annual_savings_pct_of_install_cost | simple_break_even_years | annual_export_kwh |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Current EVs, measured home load | Old rates to Mar 2026 | 16,297.01 | 5,385.17 | 2,674.18 | 2,711.00 | 13.13 | 7.62 | 1,501.52 |
| Current EVs, measured home load | Current rates | 16,297.01 | 5,953.02 | 3,075.26 | 2,877.76 | 13.94 | 7.18 | 1,501.52 |
| No EVs, 11.3 MWh/year base load | Old rates to Mar 2026 | 11,300.00 | 4,228.55 | 1,720.92 | 2,507.63 | 12.14 | 8.23 | 2,331.35 |
| No EVs, 11.3 MWh/year base load | Current rates | 11,300.00 | 4,719.06 | 2,066.25 | 2,652.81 | 12.85 | 7.78 | 2,331.35 |

## EV Context

Current-EV ROI uses measured Home Assistant home charging. DC charging is shown for context only because roof PV cannot offset public DC charging.

| vehicle | annual_km | kwh_per_100km | annual_vehicle_energy_kwh | home_charge_pct | dc_charge_pct | estimated_home_kwh | estimated_dc_kwh | start_date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Tesla | 26000.0 | 15.3 | 3978.0 | 0.65 | 0.35 | 2,585.70 | 1392.3 | 2023-03-01 |
| MG | 7000.0 | 19.0 | 1330.0 | 0.5 | 0.5 | 665.00 | 665.0 | 2024-12-01 |
| Home Assistant measured EV charging |  |  |  |  |  | 5,473.52 |  | measurement period |

## Notes

- The no-EV scenario uses your stated pre-PV consumption of 11,300 kWh/year and the measured non-EV load shape.
- The current-EV scenario uses the reconstructed measured household load, so EV home charging is already part of the load.
- Daily fixed charges are included in annual bills, but they do not affect PV savings because they apply with or without PV.
