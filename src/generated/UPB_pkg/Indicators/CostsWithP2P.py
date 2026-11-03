from OntologyToAPI import handle_upload_file  # helper to read files uploaded through the API/UI
import numpy as np
import pandas as pd
# ---------------------------------------------------------------------------
# Entrypoint function (the name must match excode:hasFunction in CostsWithP2P.ttl)
# ---------------------------------------------------------------------------

async def RunCostsWithP2P(data):
    # Parameters declared in the .ttl (bm:hasParameter) arrive in data.params, by their bm:hasParameterLabel
    admm = data.params.get("ADMMResults")
    gamma_overtime = data.params.get("GammaOvertime")
    fixed_price = data.params.get("FixedPrice")
    members_states = data.params.get("CommunityData")
    if admm is None: {"status": "ERROR", "desc": "ADMM Optimization results are required."}
    if gamma_overtime is None: return {"status": "ERROR", "desc": "GammaOvertime is required."}
    if fixed_price is None: return {"status": "ERROR", "desc": "FixedPrice is required."}
    if members_states is None: return {"status": "ERROR", "desc": "The energy community data are required."}

    _, data = next(iter(members_states[0].items()))
    df = pd.DataFrame.from_records(data)
    df['Timestamp'] = pd.to_datetime(df['Timestamp']) 
    start_date = df['Timestamp'].min()
    frequency = '15min'
    per_day_interval = 96
    analysis_days_amount = df['Timestamp'].dt.normalize().nunique()
    time_intervals = analysis_days_amount * per_day_interval

    all_members_data = _load_member_data(
            member_states=members_states,
            start_date=start_date,
            time_intervals=time_intervals,
            frequency=frequency)
    
    data = {
        "P_load": np.array([df["consumption"].values for df in all_members_data]),
        "P_gen": np.array([df["generation"].values for df in all_members_data]),
        "lambda_buy": np.full(time_intervals, fixed_price),
        "lambda_sell": np.full(time_intervals, fixed_price) * 0.2
    }

    # Insert the business logic here.
    result = _compute_p2p_indicators(data, np.array(gamma_overtime), admm)

    # The keys must match the outputs declared in the .ttl (bm:hasOutputMetadata)
    return {"status": "SUCCESS", "costs": result}

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

def _load_member_data(member_states: list, start_date: str, time_intervals: int, frequency: str):
    members_data = []
    for data in member_states:
        df = pd.DataFrame.from_records(next(iter(data.values())))
        df['Timestamp'] = pd.to_datetime(df['Timestamp']) 
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

def _grid_flows(P_g: list):
    """Separa a troca com a rede em importação e exportação (ambas >= 0)."""
    P_g = np.asarray(P_g, dtype=float)
    return np.maximum(P_g, 0.0), np.maximum(-P_g, 0.0)

def _compute_p2p_indicators(data, Gamma, admm) -> dict:
    """Cenário COM P2P. Convenção: D>0 recebe/compra, D<0 envia/vende."""
    imp, exp = _grid_flows(admm["P_g_all"])
    grid_cost_mat = data["lambda_buy"] * imp - data["lambda_sell"] * exp     # (N, T)
    trade_cost_mat = Gamma * np.abs(admm["D_all"])                         # (N, N, T)
    D_pos = np.maximum(np.array(admm["D_all"]), 0.0)
    D_neg = np.maximum(-np.array(admm["D_all"]), 0.0)
 
    grid_cost_t = grid_cost_mat.sum(axis=0)
    trade_cost_t = trade_cost_mat.sum(axis=(0, 1))
 
    return {
        # séries temporais (T,)
        'grid_cost_t': grid_cost_t.tolist(),
        'trade_cost_t': trade_cost_t.tolist(),
        'total_cost_t': (grid_cost_t + trade_cost_t).tolist(),
        'p2p_volume': D_pos.sum(axis=(0, 1)).tolist(),
        'grid_import': imp.sum(axis=0).tolist(),
        'grid_export': exp.sum(axis=0).tolist(),
        # por casa (N,)
        'house_grid_import': imp.sum(axis=1).tolist(),
        'house_grid_export': exp.sum(axis=1).tolist(),
        'house_p2p_in': D_pos.sum(axis=(1, 2)).tolist(),
        'house_p2p_out': D_neg.sum(axis=(1, 2)).tolist(),
        'house_grid_cost': grid_cost_mat.sum(axis=1).tolist(),
        'house_trade_cost': trade_cost_mat.sum(axis=(1, 2)).tolist(),
    }
