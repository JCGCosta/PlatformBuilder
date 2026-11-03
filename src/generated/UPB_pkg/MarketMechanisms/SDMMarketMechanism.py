import numpy as np
import pandas as pd
from pathlib import Path
import os

# Entrypoint function
async def SDMMarketMechanism(d):
    if None in [d.params.get("ConsumptionPerMember"), d.params.get("GenerationPerMember")]:
        return {"status": "ERROR", "desc": "The energy community results are required."}

    members_states = _data_preprocessing(d.params.get("ConsumptionPerMember"), d.params.get("GenerationPerMember"))

    _, df = next(iter(members_states.items()))
    df['Timestamp'] = pd.to_datetime(df['Timestamp']) 
    start_date = df['Timestamp'].min()
    analysis_days_amount = df['Timestamp'].dt.normalize().nunique()
    
    x_val = 0.1
    per_day_interval = 96
    frequency = '15min'    
    time_intervals = analysis_days_amount * per_day_interval

    all_members_data = _load_member_data(
            member_states=members_states,
            start_date=start_date,
            time_intervals=time_intervals,
            frequency=frequency)

    p_load = np.array([df["consumption"].values for df in all_members_data])
    p_gen = np.array([df["generation"].values for df in all_members_data])

    sdm_res = _calculate_sdm(
        n_houses=len(all_members_data),
        time_intervals=time_intervals,
        p_load=p_load,
        p_gen=p_gen,
        x_val=x_val
    )

    return {
        'status': 'SUCCESS',
        'gamma_overtime': sdm_res.tolist(),
        'community_data': [
            {
                str(m): df.to_dict(orient='records')
            }
            for m, df in members_states.items()
        ]
    }

# Auxiliary functions

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

def _load_member_data(member_states: dict, start_date: str, time_intervals: int, frequency: str):
    members_data = []
    for m, df in member_states.items():
        df = df.sort_values("Timestamp").set_index("Timestamp")
        # Ensure columns exist
        for col in ["consumption", "generation"]:
            if col not in df.columns:
                df[col] = 0.0

        if len(df) > 1:
            orig_freq = df.index.to_series().diff().mode()[0]
        else:
            orig_freq = pd.Timedelta('1h')

        target_freq = pd.Timedelta(frequency)
        df.index = df.index - orig_freq

        if target_freq < orig_freq:
            ratio = orig_freq / target_freq
            df = df.resample(target_freq).ffill(limit=int(ratio) - 1)
            df[["consumption", "generation"]] = df[["consumption", "generation"]] / ratio
            df.index = df.index + target_freq
        elif target_freq > orig_freq:
            df = df.resample(target_freq, origin='start').sum()
            df.index = df.index + target_freq
        else:
            df.index = df.index + orig_freq

        full_range = pd.date_range(
            start=pd.to_datetime(start_date),
            periods=time_intervals,
            freq=frequency
        )
        df = df.reindex(full_range)

        df["consumption"] = df["consumption"].fillna(0.0)
        df["generation"] = df["generation"].fillna(0.0)
        df["consumption"] = df["consumption"].clip(lower=0)
        df["generation"] = df["generation"].clip(lower=0)
        members_data.append(df[["consumption", "generation"]])

    return members_data

def _calculate_sdm(n_houses, time_intervals, p_load, p_gen, x_val):
    gamma = np.zeros((n_houses, n_houses, time_intervals))
    for t in range(time_intervals):
        p_net = p_gen[:, t] - p_load[:, t]

        p_buy = np.maximum(-p_net, 0)
        p_sell = np.maximum(p_net, 0)

        p_max_buy = np.max(p_buy) if np.max(p_buy) > 0 else 1.0
        p_max_sell = np.max(p_sell) if np.max(p_sell) > 0 else 1.0

        gamma_b_rel = (x_val / 2) * (p_buy / p_max_buy)
        gamma_s_rel = (x_val / 2) * (p_sell / p_max_sell)

        for i in range(n_houses):
            for j in range(n_houses):
                if i == j:
                    gamma[i, j, t] = x_val
                elif p_buy[i] > 0 and p_sell[j] > 0:
                    gamma[i, j, t] = x_val - (gamma_b_rel[i] + gamma_s_rel[j])
                elif p_sell[i] > 0 and p_buy[j] > 0:
                    gamma[i, j, t] = x_val - (gamma_s_rel[i] + gamma_b_rel[j])
                else:
                    gamma[i, j, t] = x_val
    return np.maximum(gamma, 0)
