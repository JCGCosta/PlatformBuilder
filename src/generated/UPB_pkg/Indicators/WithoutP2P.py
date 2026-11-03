from OntologyToAPI import handle_upload_file  # helper to read files uploaded through the API/UI
import numpy as np
import pandas as pd
# ---------------------------------------------------------------------------
# Entrypoint function (the name must match excode:hasFunction in WithoutP2P.ttl)
# ---------------------------------------------------------------------------

async def RunWithoutP2P(data):
    # Parameters declared in the .ttl (bm:hasParameter) arrive in data.params, by their bm:hasParameterLabel
    if None in [d.params.get("ConsumptionPerMember"), d.params.get("GenerationPerMember")]:
        return {"status": "ERROR", "desc": "The energy community results are required."}
    if fixed_price is None: return {"status": "ERROR", "desc": "FixedPrice is required."}

    members_states = _data_preprocessing(d.params.get("ConsumptionPerMember"), d.params.get("GenerationPerMember"))

    _, df = next(iter(members_states.items()))
    df['Timestamp'] = pd.to_datetime(df['Timestamp']) 
    start_date = df['Timestamp'].min()
    analysis_days_amount = df['Timestamp'].dt.normalize().nunique()
    
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

    # Insert the business logic here.
    result = _compute_no_p2p_indicators(p_load, p_gen, time_intervals, fixed_price)

    # The keys must match the outputs declared in the .ttl (bm:hasOutputMetadata)
    return {
        "status": "OK", 
        "result": result
    }

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

def _compute_no_p2p_indicators(P_load, P_gen, time_intervals, fixed_price) -> dict:
    """Cenário SEM P2P: cada casa só troca com a rede."""
    lambda_buy = np.full(time_intervals, fixed_price)
    lambda_sell = lambda_buy * 0.2
    P_g = P_load - P_gen
    imp, exp = grid_flows(P_g)
    cost_mat = lambda_buy * imp - lambda_sell * exp
    return {
        'P_g': P_g,
        'total_cost_t': cost_mat.sum(axis=0),
        'grid_import': imp.sum(axis=0),
        'grid_export': exp.sum(axis=0),
        'house_grid_import': imp.sum(axis=1),
        'house_grid_export': exp.sum(axis=1),
        'house_grid_cost': cost_mat.sum(axis=1),
    }
