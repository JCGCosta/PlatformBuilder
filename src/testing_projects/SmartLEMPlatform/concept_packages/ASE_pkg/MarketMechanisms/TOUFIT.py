import inspect
import json
import pandas as pd
from datetime import datetime
from typing import List, Literal, Optional, Type

from OntologyToAPI import handle_upload_file
from pydantic import BaseModel, ValidationError

# ---------------------------------------------------------------------------
# Entrypoint function
# ---------------------------------------------------------------------------

async def RunTOUFITMarket(d):
    if None in [d.params.get("ConsumptionPerMember"),d.params.get("GenerationPerMember"),d.params.get("DeficitPerMember"),d.params.get("SurplusPerMember")]:
        return {"status": "ERROR", "desc": "The energy community results are required."}
    members_states = _data_preprocessing(d.params.get("ConsumptionPerMember"),d.params.get("GenerationPerMember"),d.params.get("DeficitPerMember"),d.params.get("SurplusPerMember"))
    return _run_toufit_market_mechanism(members_states, d.params.get("TOU"), d.params.get("FIT"))

# ---------------------------------------------------------------------------
# Auxiliary functions
# ---------------------------------------------------------------------------

def _data_preprocessing(*dicts, how="outer"):
    # all keys across all dicts, in order of first appearance
    keys = list(dict.fromkeys(k for d in dicts for k in d))
    result = {}
    for k in keys:
        frames = []
        for d in dicts:
            records = d.get(k)
            if not records:
                continue
            df = pd.DataFrame(records)
            df["Timestamp"] = pd.to_datetime(df["Timestamp"])
            frames.append(df.set_index("Timestamp"))

        merged = pd.concat(frames, axis=1, join=how).sort_index()
        result[k] = merged.reset_index()   # drop .reset_index() to keep Timestamp as index
    return result

def _clean_hourly_tariffs(hourly_tariffs: pd.DataFrame) -> pd.DataFrame:
    tariffs = hourly_tariffs.copy()
    tariffs["hour"] = pd.to_numeric(tariffs["hour"], errors="coerce").fillna(0).astype(int).clip(0, 23)
    tariffs["ToU"] = pd.to_numeric(tariffs["ToU"], errors="coerce").ffill().bfill().fillna(0.3).astype(float)
    tariffs["FiT"] = pd.to_numeric(tariffs["FiT"], errors="coerce").ffill().bfill().fillna(0.1).astype(float)
    tariffs = tariffs.drop_duplicates("hour", keep="last").sort_values("hour")

    missing_hours = sorted(set(range(24)).difference(set(tariffs["hour"])))
    if missing_hours:
        defaults = pd.DataFrame(
            {
                "hour": missing_hours,
                "ToU": [float(tariffs["ToU"].mean())] * len(missing_hours),
                "FiT": [float(tariffs["FiT"].mean())] * len(missing_hours),
            }
        )
        tariffs = pd.concat([tariffs, defaults], ignore_index=True)
    return tariffs.sort_values("hour").reset_index(drop=True)

def _tariff_vector_from_hourly(timestamps, hourly_tariffs: pd.DataFrame) -> pd.DataFrame:
    timestamps = pd.Series(pd.to_datetime(timestamps)).reset_index(drop=True)
    hourly = _clean_hourly_tariffs(hourly_tariffs).set_index("hour")
    out = pd.DataFrame({"Timestamp": timestamps})
    out["_hour"] = out["Timestamp"].dt.hour
    out["ToU"] = out["_hour"].map(hourly["ToU"]).astype(float)
    out["FiT"] = out["_hour"].map(hourly["FiT"]).astype(float)
    return out.drop(columns=["_hour"])

def _normalize_tariff_vector(timestamps, tariffs, fit=None) -> pd.DataFrame:
    timestamps = pd.Series(pd.to_datetime(timestamps)).reset_index(drop=True)
    if isinstance(tariffs, pd.DataFrame):
        tariff_df = tariffs.copy()
        if {"hour", "ToU", "FiT"}.issubset(tariff_df.columns):
            return _tariff_vector_from_hourly(timestamps, tariff_df)
        if {"Timestamp", "ToU", "FiT"}.issubset(tariff_df.columns):
            tariff_df["Timestamp"] = pd.to_datetime(tariff_df["Timestamp"])
            merged = pd.DataFrame({"Timestamp": timestamps}).merge(
                tariff_df[["Timestamp", "ToU", "FiT"]],
                on="Timestamp",
                how="left",
            )
            merged["ToU"] = pd.to_numeric(merged["ToU"], errors="coerce").ffill().bfill()
            merged["FiT"] = pd.to_numeric(merged["FiT"], errors="coerce").ffill().bfill()
            return merged
        if {"ToU", "FiT"}.issubset(tariff_df.columns) and len(tariff_df) == len(timestamps):
            return pd.DataFrame(
                {
                    "Timestamp": timestamps,
                    "ToU": pd.to_numeric(tariff_df["ToU"], errors="coerce").ffill().bfill().to_numpy(dtype=float),
                    "FiT": pd.to_numeric(tariff_df["FiT"], errors="coerce").ffill().bfill().to_numpy(dtype=float),
                }
            )
    if isinstance(tariffs, pd.Series) and isinstance(fit, pd.Series):
        if len(tariffs) != len(timestamps) or len(fit) != len(timestamps):
            raise ValueError("Tariff vectors must match the timestamp vector length.")
        return pd.DataFrame(
            {
                "Timestamp": timestamps,
                "ToU": tariffs.to_numpy(dtype=float),
                "FiT": fit.to_numpy(dtype=float),
            }
        )
    if fit is not None:
        return pd.DataFrame(
            {
                "Timestamp": timestamps,
                "ToU": [float(tariffs)] * len(timestamps),
                "FiT": [float(fit)] * len(timestamps),
            }
        )
    raise ValueError(
        "Tariffs must be a DataFrame with either hourly columns "
        "['hour', 'ToU', 'FiT'] or timestamp-vector columns ['Timestamp', 'ToU', 'FiT']."
    )

def _calculate_hourly_costs(member_states, tou: float, fit: float):
    df = member_states.copy()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    tariff_vector = _normalize_tariff_vector(df["Timestamp"], tou, fit)
    # Calculate time resolution in hours
    if len(df) > 1:
        time_deltas = df['Timestamp'].diff().dropna().dt.total_seconds() / 3600
        avg_resolution = time_deltas.mean()
    else:
        avg_resolution = 1.0  # fallback to 1 hour if single record
    # Calculate hourly cost, revenue, payment
    df["ToU"] = tariff_vector["ToU"].to_numpy(dtype=float)
    df["FiT"] = tariff_vector["FiT"].to_numpy(dtype=float)
    df['cost'] = df['deficit'] * df['ToU'] * avg_resolution
    df['revenue'] = df['surplus'] * df['FiT'] * avg_resolution
    df['payment'] = df['cost'] - df['revenue']  # Payment is cost minus revenue
    return df[['Timestamp', 'ToU', 'FiT', 'cost', 'revenue', 'payment']]

def aggregate_members_costs(self):
    # Aggregate costs, revenues and payments of all members in the community
    self.all_costs = pd.concat([a.costs.assign(member_id=a.member_id) for a in self.members if not a.costs.empty])
    return self.all_costs

def _run_toufit_market_mechanism(members_states: dict, tou: float, fit: float):
    member_billing = {}
    community_billing = {
        "community_total_cost": 0,
        "community_total_revenue": 0,
        "community_total_payment": 0,
    }
    for m, v in members_states.items():
        member_costs = _calculate_hourly_costs(v, tou, fit)
        member_billing[m] = {
            "member_total_cost": member_costs.cost.sum(),
            "member_total_revenue": member_costs.revenue.sum(),
            "member_total_payment": member_costs.payment.sum()
        }
        community_billing["community_total_cost"] = community_billing["community_total_cost"] + member_costs.cost.sum()
        community_billing["community_total_revenue"] = community_billing["community_total_revenue"] + member_costs.revenue.sum()
        community_billing["community_total_payment"] = community_billing["community_total_payment"] + member_costs.payment.sum()

    return {
        "status": "SUCCESS",
        "billing_per_member": member_billing,
        "community_aggregated_billing": community_billing,
        "billing_per_member_to_table": [
            {"member_id": member_id, **values}
            for member_id, values in member_billing.items()
        ],
        "community_aggregated_billing_to_text": f"Community Aggregated Billing \n - Community Total Cost: {community_billing["community_total_cost"]} \n - Community Total Revenue: {community_billing["community_total_revenue"]} \n - Community Total Payment: {community_billing["community_total_payment"]}"
    }
