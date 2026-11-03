import numpy as np
import pandas as pd
from pathlib import Path
from collections import deque
import os, json
from OntologyToAPI import handle_upload_file

# Entrypoint function
async def DBMMarketMechanism(d):
    if d.params.get("CommunityTopology") is None:
        return {"status" : "ERROR", "desc": "The energy topology is required."}

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

    #if len(all_members_data) != 10: return {"status": "ERROR", "desc": "This strategy does not expect a house amount lower or greater than 10."}

    hop_price = 0.005
    topology = {int(k): v for k, v in d.params["CommunityTopology"].items()}

    dbm_res, dist_df = _calculate_dbm(
        n_houses=len(all_members_data),
        time_intervals=time_intervals,
        topology=topology,
        hop_price=hop_price,
    )

    return {
        'status': 'SUCCESS',
        'distances': dist_df.to_dict(),
        'gamma_overtime': dbm_res.tolist()
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

def _calculate_dbm(n_houses, time_intervals, topology, hop_price):
    # BFS para cada casa i∈[0..9]
    distance_matrix = np.zeros((n_houses, n_houses), dtype=int)
    for src in range(n_houses):
        dist = {n: np.inf for n in topology}
        dist[src] = 0
        queue = deque([src])
        while queue:
            u = queue.popleft()
            for v in topology[u]:
                if dist[v] == np.inf:
                    dist[v] = dist[u] + 1
                    queue.append(v)
        for j in range(n_houses):
            distance_matrix[src, j] = int(dist[j])

    distance_df = pd.DataFrame(
        distance_matrix,
        index=range(1, n_houses + 1),
        columns=range(1, n_houses + 1)
    )

    gamma_hops = hop_price * distance_df.values
    gamma = np.repeat(gamma_hops[:, :, None], time_intervals, axis=2)

    return gamma, distance_df
