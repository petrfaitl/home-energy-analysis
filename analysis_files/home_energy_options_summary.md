# Home Energy Options Summary

Analysis period: 2025-05-16 to 2026-05-13 (363 complete days).

## Current Site

- Actual metered import: 9,893 kWh.
- Actual metered export: 1,607 kWh.
- Solar production: 7,886 kWh.
- Reconstructed household load: 16,197 kWh.
- EV charging: 5,440 kWh, with 24.0% during peak hours.
- Actual metered bill for the analysed period: $3,076; annualised: $3,095.

## Battery View

- Pure ROI battery choice: HVM 8.28 kWh, about $476/year. A 10-year simple payback would need installed cost below $4,763.
- Shoulder coverage sweet spot: HVM 13.80 kWh, about $568/year and 368 kWh residual peak import.
- Max single HVM stack: HVM 22.08 kWh leaves 132 kWh residual peak import and saves about $616/year.

Battery-only scenarios, current array:

| battery_kwh | annualized_savings_nzd | ten_year_break_even_capex_nzd | peak_import_kwh | export_kwh | battery_charged_from_grid_kwh | battery_charged_from_solar_kwh |
| --- | --- | --- | --- | --- | --- | --- |
| 8.28 | 476.28 | 4,762.76 | 818.77 | 495.14 | 1,474.13 | 997.13 |
| 11.04 | 532.22 | 5,322.22 | 541.67 | 424.13 | 1,711.01 | 1,068.14 |
| 13.80 | 567.51 | 5,675.15 | 367.56 | 377.33 | 1,857.67 | 1,114.95 |
| 16.56 | 591.64 | 5,916.43 | 248.99 | 343.97 | 1,956.05 | 1,148.30 |
| 19.32 | 606.48 | 6,064.80 | 177.52 | 319.29 | 2,010.79 | 1,172.98 |
| 22.08 | 616.44 | 6,164.41 | 131.83 | 296.01 | 2,038.28 | 1,196.26 |

## Solar Array View

- Added-panel scenarios now use 395 W panels. The first added panel is allocated to the spare slot on the current array; remaining added panels are counted as second-array panels.
- Strict ~10 kWp total array: add 7 x 395 W panels (1 current-array extra + 6 second-array panels; 25 total panels; 9.88 kWp).
- The next step above 10 kWp is 8 added panels, giving 10.27 kWp; check this with the installer if modest DC oversizing is acceptable.
- Solar-only savings are limited because extra daytime generation is heavily exported at the low export rate.

Solar-only sensitivity:

| added_panels | current_array_extra_panels | second_array_panels | total_solar_kwp | annualized_savings_nzd | peak_import_kwh | export_kwh |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 0 | 0 | 7.11 | 0.00 | 3,042.91 | 1,492.27 |
| 1 | 1 | 0 | 7.51 | 86.18 | 2,959.68 | 1,846.79 |
| 4 | 1 | 3 | 8.69 | 321.43 | 2,795.52 | 2,995.88 |
| 7 | 1 | 6 | 9.88 | 543.65 | 2,679.16 | 4,192.82 |
| 8 | 1 | 7 | 10.27 | 616.15 | 2,646.12 | 4,597.56 |

## Combined Options

- Smallest single-stack option under 100 kWh/year peak import: add 7 x 395 W panels (1 current-array extra + 6 second-array) and use HVM 22.08 kWh. Annualized saving: $1,145.
- Best modelled option under about 10 kWp with one HVM tower: add 7 x 395 W panels (1 current-array extra + 6 second-array) (9.88 kWp total) and HVM 22.08 kWh. Residual peak import: 98 kWh.
- True near-zero peak import needs roughly 44.2 kWh of usable battery in this model, beyond a single HVM tower.

## Notes

- Savings are before system capital cost, finance, maintenance, degradation, and installer-specific limits.
- The dispatch assumes the battery can charge from solar surplus and can top up during off-peak hours only enough for the next peak window.
- Instantaneous power limits are not enabled by default because the source meters have irregular timestamp gaps; set BATTERY_POWER_LIMIT_KW in the script to test a specific inverter limit.
- The daily fixed charge is included in total bills but does not change between options.
