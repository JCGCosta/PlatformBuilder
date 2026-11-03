from OntologyToAPI import handle_upload_file  # helper to read files uploaded through the API/UI
import pandas as pd
import numpy as np
import cvxpy as cp

# ---------------------------------------------------------------------------
# Entrypoint function (the name must match excode:hasFunction in ADMMOptimization.ttl)
# ---------------------------------------------------------------------------

async def RunADMMOptimization(data):
    # Parameters declared in the .ttl (bm:hasParameter) arrive in data.params, by their bm:hasParameterLabel
    gamma_overtime = data.params.get("GammaOvertime")
    fixed_price = data.params.get("FixedPrice")
    if gamma_overtime is None: return {"status": "ERROR", "desc": "GammaOvertime is required."}
    if fixed_price is None: return {"status": "ERROR", "desc": "FixedPrice is required."}
    if None in [data.params.get("ConsumptionPerMember"), data.params.get("GenerationPerMember")]:
        return {"status": "ERROR", "desc": "The energy community results are required."}

    members_states = _data_preprocessing(data.params.get("ConsumptionPerMember"), data.params.get("GenerationPerMember"))

    _, df = next(iter(members_states.items()))
    df['Timestamp'] = pd.to_datetime(df['Timestamp']) 
    start_date = df['Timestamp'].min()
    frequency = '15min'
    time_intervals = len(gamma_overtime)

    all_members_data = _load_member_data(
            member_states=members_states,
            start_date=start_date,
            time_intervals=time_intervals,
            frequency=frequency)
            
    p_load = np.array([df["consumption"].values for df in all_members_data])
    p_gen = np.array([df["generation"].values for df in all_members_data])

    n_houses = len(all_members_data)

    admm = _admm_optimization(np.array(gamma_overtime), n_houses, time_intervals, fixed_price, p_load, p_gen)

    # The keys must match the outputs declared in the .ttl (bm:hasOutputMetadata)
    return {
        "status": "SUCCESS",
        "aggred_p2p_trades_kwh": admm["D_all"],
        "grid_exchanges_per_member_kwh": admm["P_g_all"],
        "energy_shadow_price_euro_per_kwh": admm["mu_all"],
        "aggreament_condition_multiplier": admm["U_all"],
        "iterations_per_timestep": admm["iters"]
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

def _admm_optimization(gamma_overtime: np.ndarray, n_houses: int, time_intervals: int, fixed_price: float, p_load: np.ndarray, p_gen: np.ndarray) -> dict:
    rho = 5
    max_iter = 80
    epsilon_p = 0.002
    epsilon_d = 0.002
    lambda_buy = np.full(time_intervals, fixed_price)
    lambda_sell = lambda_buy * 0.2

    D_all = np.zeros((n_houses, n_houses, time_intervals))
    P_g_all = np.zeros((n_houses, time_intervals))
    mu_all = np.zeros((n_houses, time_intervals))
    
    # Variável dual (consenso)
    U_all = np.zeros((n_houses, n_houses, time_intervals))
    iters_to_converge = np.zeros(time_intervals, dtype=int)
    rho0 = rho  # valor base de rho, fixo por instante t

    optimization_process = {}

    for t in range(time_intervals):
        gamma_t = gamma_overtime[:, :, t]
        rho_t = rho0  # reiniciar rho em cada instante
        optimization_process[str(t)] = None
        # Variáveis ADMM
        x = np.zeros((n_houses, n_houses))
        z = np.zeros((n_houses, n_houses))
        u = np.zeros((n_houses, n_houses))
        for it in range(max_iter):
            z_old = z.copy() # 1) x-update
            x_new = np.zeros_like(x)
            for i in range(n_houses):
                p_plus = cp.Variable(nonneg=True)
                p_minus = cp.Variable(nonneg=True)
                d_i = cp.Variable(n_houses)
                cost_grid = lambda_buy[t] * p_plus - lambda_sell[t] * p_minus
                cost_trade = cp.sum(cp.multiply(gamma_t[i, :], cp.abs(d_i)))
                aug_term = (rho_t / 2) * cp.sum_squares(
                    d_i - z[i, :] + u[i, :]
                )
                objective = cp.Minimize(cost_grid + cost_trade + aug_term)
                surplus_i = max(p_gen[i, t] - p_load[i, t], 0)
                constraints = [
                    p_plus - p_minus + cp.sum(d_i) == (p_load[i, t] - p_gen[i, t]),
                    d_i[i] == 0,
                    cp.sum(cp.pos(-d_i)) <= surplus_i
                ]
                prob = cp.Problem(objective, constraints)
                prob.solve(solver=cp.SCS, verbose=False)
                if prob.status in [cp.OPTIMAL, cp.OPTIMAL_INACCURATE] and d_i.value is not None:
                    x_new[i, :] = d_i.value
                else:
                    x_new[i, :] = x[i, :]
                mu_all[i, t] = constraints[0].dual_value if constraints[0].dual_value is not None else 0.0
            # 2) z-update
            z = 0.5 * ((x_new + u) - (x_new + u).T)
            np.fill_diagonal(z, 0.0)
            # 3) u-update
            u = u + (x_new - z)
            # 4) resíduos ADMM
            primal_residual = np.linalg.norm(x_new - z, 'fro')
            dual_residual = rho_t * np.linalg.norm(z - z_old, 'fro')
            # 5) adaptive rho
            rho_old = rho_t
            if primal_residual > 10 * dual_residual:
                rho_t *= 2.0
                u *= rho_old / rho_t
            elif dual_residual > 10 * primal_residual:
                rho_t /= 2.0
                u *= rho_old / rho_t

            optimization_process = {
                "t": f"{t:03d}",
                "iter": f"{it+1:04d}",
                "primal": f"{primal_residual:.6e}",
                "dual": f"{dual_residual:.6e}",
                "rho": f"{rho_t:.3f}"
            }

            # 6) critério de convergência
            if primal_residual < epsilon_p and dual_residual < epsilon_d:
                iters_to_converge[t] = it + 1
                break
            if it == max_iter - 1:
                iters_to_converge[t] = max_iter
            x = x_new.copy()
    
        # guardar resultados finais
        D_all[:, :, t] = z
        U_all[:, :, t] = u
        for i in range(n_houses):
            net_p2p = np.sum(D_all[i, :, t])
            P_g_all[i, t] = (p_load[i, t] - p_gen[i, t]) - net_p2p

    return {
        "D_all": D_all.tolist(),
        "P_g_all": P_g_all.tolist(),
        "mu_all": mu_all.tolist(),
        "U_all": U_all.tolist(),
        "iters": iters_to_converge.tolist()
    }
