from OntologyToAPI import handle_upload_file  # helper to read files uploaded through the API/UI
import pandas as pd
# ---------------------------------------------------------------------------
# Entrypoint function (the name must match excode:hasFunction in CommunityConsGenCSVUpload.ttl)
# ---------------------------------------------------------------------------

async def RunCommunityConsGenCSVUpload(data):
    # Parameters declared in the .ttl (bm:hasParameter) arrive in data.params, by their bm:hasParameterLabel
    if data.params.get("ECConsGenCSV") is None:
        return dict(status="ERROR", desc="The energy community consumption and generation csv is required.")
        
    if data.params.get("StartingDate") is None:
        return dict(status="ERROR", desc="The starting date of the analysis is required.")
        
    if data.params.get("AnalysisPeriod") is None:
        return dict(status="ERROR", desc="The analysis period is required.")
    
    file_path = handle_upload_file(data.params["ECConsGenCSV"])
    
    if ".csv" not in file_path: 
        return {"status": "ERROR", "desc": "The ECConfiguration file must be .csv file."}
    
    df = pd.read_csv(file_path, sep=',')
    
    if not pd.Index(["member", "utc_timestamp", "consumption", "generation"]).isin(df.columns).all():
        return dict(status="ERROR", desc="The CSV must contain the columns \"member\", \"utc_timestamp\", \"consumption\" and \"generation\".")
        
    StartingDate = data.params["StartingDate"]
    AnalysisPeriod = data.params["AnalysisPeriod"]
    df["utc_timestamp"] = pd.to_datetime(df["utc_timestamp"], utc=True)

    start = pd.Timestamp(StartingDate, tz="UTC")
    end = start + pd.Timedelta(days=AnalysisPeriod)
    
    community_data = df[(df["utc_timestamp"] >= start) & (df["utc_timestamp"] < end)].copy()
    
    # The keys must match the outputs declared in the .ttl (bm:hasOutputMetadata)
    return _pre_process_data(community_data)

# ---------------------------------------------------------------------------
# Auxiliary functions
# ---------------------------------------------------------------------------

def _to_list(series):
    return [None if pd.isna(v) else float(v) for v in series]

def _per_member(df, value_col):
    grouped = (
        df.groupby(["member", "utc_timestamp"])[value_col]
        .sum()
        .reset_index()
        .sort_values(["member", "utc_timestamp"])
    )
    result = {}
    for member, rows in grouped.groupby("member"):
        result[str(member)] = [
            {
                "Timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                value_col: None if pd.isna(v) else float(v),
            }
            for ts, v in zip(rows["utc_timestamp"], rows[value_col])
        ]
    return result

def _pre_process_data(community_data: pd.DataFrame) -> dict:
    df = community_data.copy()
    df["utc_timestamp"] = pd.to_datetime(df["utc_timestamp"], utc=True)

    # Community totals per timestamp
    agg = (
        df.groupby("utc_timestamp")[["consumption", "generation"]]
        .sum()
        .sort_index()
    )
    agg["net_balance"] = agg["generation"] - agg["consumption"]
    timestamps = agg.index

    return {
        "status": "SUCCESS",
        "community_aggregated_data_to_plot": {
            "graphType": "line",
            "title": "Community Aggregated Consumption and Generation",
            "independent": {
                "name": "Timestamp",
                "values": [ts.isoformat() for ts in timestamps],
            },
            "dependent": [
                {"name": "Consumption", "values": _to_list(agg["consumption"])},
                {"name": "Generation", "values": _to_list(agg["generation"])},
                {"name": "NetBalance", "values": _to_list(agg["net_balance"])},
            ],
        },
        "consumption_per_member": _per_member(df, "consumption"),
        "generation_per_member": _per_member(df, "generation"),
    }
