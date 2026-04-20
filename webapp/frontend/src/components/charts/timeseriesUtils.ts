/**
 * Shared helpers for quarter-hour time-series charts.
 *
 * The backend serves arrays of 35 040 floats (one per quarter-hour of
 * the year). Plotly handles that many points but the interaction feels
 * sluggish on lower-end machines, and stacked-area charts with 5-10
 * generators × 35 040 points × 4 bytes start to dominate the render
 * budget. Charts that display the full year therefore downsample to
 * daily (365 points) or hourly (8 760 points) resolution; zoomed-in
 * views use the raw quarter-hour data.
 */

/** Quarter-hours per day. */
export const QH_PER_DAY = 96;

/** Quarter-hours per hour. */
export const QH_PER_HOUR = 4;

/** Days per month in a non-leap year, indexed from 0 (January). */
export const DAYS_PER_MONTH = [
  31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31,
];

/**
 * Aggregate a quarter-hour array to daily means (365 points).
 *
 * Expected input length is a multiple of 96; trailing values that do
 * not form a complete day are discarded.
 */
export function toDailyMean(values: number[]): number[] {
  const nDays = Math.floor(values.length / QH_PER_DAY);
  const out = new Array(nDays).fill(0);
  for (let d = 0; d < nDays; d++) {
    let s = 0;
    for (let q = 0; q < QH_PER_DAY; q++) s += values[d * QH_PER_DAY + q];
    out[d] = s / QH_PER_DAY;
  }
  return out;
}

/**
 * Aggregate a quarter-hour array to daily sums (365 points).
 *
 * Useful for extensive quantities (curtailment energy) where the mean
 * would hide the seasonal envelope.
 */
export function toDailySum(values: number[]): number[] {
  const nDays = Math.floor(values.length / QH_PER_DAY);
  const out = new Array(nDays).fill(0);
  for (let d = 0; d < nDays; d++) {
    let s = 0;
    for (let q = 0; q < QH_PER_DAY; q++) s += values[d * QH_PER_DAY + q];
    out[d] = s;
  }
  return out;
}

/**
 * Day-of-year ticks for month labels on a 365-point axis.
 *
 * Returns the day-of-year at which each month starts (1-indexed dates
 * converted to 0-indexed day-of-year), plus the month names. Use as
 * ``xaxis: { tickvals, ticktext }`` on Plotly layouts.
 */
export function monthTicks(): { tickvals: number[]; ticktext: string[] } {
  const names = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  const tickvals: number[] = [];
  let d = 0;
  for (let m = 0; m < 12; m++) {
    tickvals.push(d);
    d += DAYS_PER_MONTH[m];
  }
  return { tickvals, ticktext: names };
}

/** Slice a quarter-hour array to a specific day window (96 points). */
export function sliceDay(values: number[], dayIdx: number): number[] {
  const start = dayIdx * QH_PER_DAY;
  return values.slice(start, start + QH_PER_DAY);
}

/** Quarter-hour indices (0..95) as HH:MM labels for intra-day charts. */
export function dayHourLabels(): string[] {
  const out: string[] = [];
  for (let q = 0; q < QH_PER_DAY; q++) {
    const h = Math.floor(q / 4);
    const m = (q % 4) * 15;
    out.push(`${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`);
  }
  return out;
}
