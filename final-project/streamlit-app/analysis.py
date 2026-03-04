import pandas as pd
from pandas import DataFrame
from scipy import stats

# Compute per-station Pearson r between monthly crime count and rides.
def get_station_correlations(df: DataFrame):
    results = []
    for station, group in df.groupby("stationname_mapped"):
        clean = group[["crime_count", "rides"]].dropna()
        if len(clean) < 6:
            continue
        r, p = stats.pearsonr(clean["crime_count"], clean["rides"])
        line = group["primary_line"].iloc[0] if "primary_line" in group.columns else "Unknown"
        results.append({
            "Station": station,
            "Line": line,
            "Pearson r": round(float(r), 3),
            "p-value": round(float(p), 4),
            "Months of Data": len(clean),
            "Significant (p<0.05)": "Yes" if p < 0.05 else "No",
        })

    return pd.DataFrame(results).sort_values("Pearson r").reset_index(drop=True)

