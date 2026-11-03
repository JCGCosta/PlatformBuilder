from OntologyToAPI import handle_upload_file  # helper to read files uploaded through the API/UI

# ---------------------------------------------------------------------------
# Entrypoint function (the name must match excode:hasFunction in WithP2P.ttl)
# ---------------------------------------------------------------------------

async def RunWithP2P(data):
    # Parameters declared in the .ttl (bm:hasParameter) arrive in data.params, by their bm:hasParameterLabel
    example_input = data.params.get("ExampleInput")
    if example_input is None:
        return {"status": "ERROR", "desc": "ExampleInput is required."}

    # Insert the business logic here.
    result = _process(example_input)

    # The keys must match the outputs declared in the .ttl (bm:hasOutputMetadata)
    return {"status": "OK", "desc": "Executed successfully.", "result": result}

# ---------------------------------------------------------------------------
# Auxiliary functions
# ---------------------------------------------------------------------------

def compute_p2p_indicators(data: CommunityData, Gamma, admm: ADMMResult) -> dict:
    """Cenário COM P2P. Convenção: D>0 recebe/compra, D<0 envia/vende."""
    imp, exp = grid_flows(admm.P_g_all)
    grid_cost_mat = data.lambda_buy * imp - data.lambda_sell * exp     # (N, T)
    trade_cost_mat = Gamma * np.abs(admm.D_all)                         # (N, N, T)
    D_pos = np.maximum(admm.D_all, 0.0)
    D_neg = np.maximum(-admm.D_all, 0.0)
 
    grid_cost_t = grid_cost_mat.sum(axis=0)
    trade_cost_t = trade_cost_mat.sum(axis=(0, 1))
 
    return {
        # séries temporais (T,)
        'grid_cost_t': grid_cost_t,
        'trade_cost_t': trade_cost_t,
        'total_cost_t': grid_cost_t + trade_cost_t,
        'p2p_volume': D_pos.sum(axis=(0, 1)),
        'grid_import': imp.sum(axis=0),
        'grid_export': exp.sum(axis=0),
        # por casa (N,)
        'house_grid_import': imp.sum(axis=1),
        'house_grid_export': exp.sum(axis=1),
        'house_p2p_in': D_pos.sum(axis=(1, 2)),
        'house_p2p_out': D_neg.sum(axis=(1, 2)),
        'house_grid_cost': grid_cost_mat.sum(axis=1),
        'house_trade_cost': trade_cost_mat.sum(axis=(1, 2)),
    }
