from OntologyToAPI import handle_upload_file  # helper to read files uploaded through the API/UI
import base64
import io

import cvxpy as cp
import matplotlib
matplotlib.use("Agg")  # no display needed: figures are rendered to PNG in memory
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

FREQUENCY = "15min"
STEPS_PER_DAY = 96
SELL_RATIO = 0.2

# ---------------------------------------------------------------------------
# Entrypoint function (the name must match excode:hasFunction in ADMMOptimization.ttl)
# ---------------------------------------------------------------------------

async def RunADMMOptimization(data):
    # Parameters declared in the .ttl (bm:hasParameter) arrive in data.params, by their bm:hasParameterLabel
    gamma_overtime = data.params.get("GammaOvertime")
    fixed_price = data.params.get("FixedPrice")
    if gamma_overtime is None: return {"status": "ERROR", "desc": "GammaOvertime is required."}
    if fixed_price is None: return {"status": "ERROR", "desc": "FixedPrice is required."}
    if data.params.get("CommunityData") is None:
        return {"status": "ERROR", "desc": "The energy community data are required."}

    members_states = data.params.get("CommunityData")
    house_names = [str(next(iter(m.keys()))) for m in members_states]

    _, first_member_records = next(iter(members_states[0].items()))
    df = pd.DataFrame.from_records(first_member_records)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    start_date = df['Timestamp'].min()
    analysis_days_amount = df['Timestamp'].dt.normalize().nunique()
    time_intervals = analysis_days_amount * STEPS_PER_DAY

    gamma = np.asarray(gamma_overtime, dtype=float)
    if gamma.ndim != 3 or gamma.shape[2] != time_intervals:
        return {"status": "ERROR",
                "desc": f"GammaOvertime must have shape (N, N, {time_intervals}); got {gamma.shape}."}

    all_members_data = _load_member_data(
            member_states=members_states,
            start_date=start_date,
            time_intervals=time_intervals,
            frequency=FREQUENCY)

    p_load = np.array([m["consumption"].values for m in all_members_data])
    p_gen = np.array([m["generation"].values for m in all_members_data])
    timestamps = all_members_data[0].index

    n_houses = len(all_members_data)
    if gamma.shape[0] != n_houses:
        return {"status": "ERROR",
                "desc": f"GammaOvertime is for {gamma.shape[0]} houses, but CommunityData has {n_houses}."}

    admm = _admm_optimization(gamma, n_houses, time_intervals, fixed_price, p_load, p_gen)

    visuals = _build_visualizations(
        gamma=gamma, admm=admm, p_load=p_load, p_gen=p_gen,
        fixed_price=fixed_price, timestamps=timestamps, house_names=house_names)

    # The keys must match the outputs declared in the .ttl (bm:hasOutputMetadata)
    return {
        "status": "SUCCESS",
        "admm_results": {
            "D_all": admm["D_all"],
            "P_g_all": admm["P_g_all"],
            "mu_all": admm["mu_all"],
            "U_all": admm["U_all"],
            "iters": admm["iters"]
        },
        "community_data_propagation": members_states,
        "gamma_overtime_propagation": gamma_overtime,
        "fixed_price_propagation": fixed_price,
        **visuals,
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

def _admm_optimization(gamma_overtime: np.ndarray, n_houses: int, time_intervals: int, fixed_price: float, p_load: np.ndarray, p_gen: np.ndarray) -> dict:
    rho = 5
    max_iter = 80
    epsilon_p = 0.002
    epsilon_d = 0.002
    lambda_buy = np.full(time_intervals, fixed_price)
    lambda_sell = lambda_buy * SELL_RATIO

    D_all = np.zeros((n_houses, n_houses, time_intervals))
    P_g_all = np.zeros((n_houses, time_intervals))
    mu_all = np.zeros((n_houses, time_intervals))

    # Variável dual (consenso)
    U_all = np.zeros((n_houses, n_houses, time_intervals))
    iters_to_converge = np.zeros(time_intervals, dtype=int)
    rho0 = rho  # valor base de rho, fixo por instante t

    for t in range(time_intervals):
        gamma_t = gamma_overtime[:, :, t]
        rho_t = rho0  # reiniciar rho em cada instante
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
        "iters": iters_to_converge.tolist(),
        "max_iter": max_iter,
    }

# ---------------------------------------------------------------------------
# Indicators (with and without P2P)
# ---------------------------------------------------------------------------

def _compute_indicators(gamma, D, P_g, p_load, p_gen, lambda_buy, lambda_sell) -> dict:
    """All per-house arrays are (N, T); D convention: D[i,j] > 0 -> i receives from j."""
    imp, exp = np.maximum(P_g, 0.0), np.maximum(-P_g, 0.0)
    net = p_load - p_gen
    imp0, exp0 = np.maximum(net, 0.0), np.maximum(-net, 0.0)

    D_pos = np.maximum(D, 0.0)
    D_neg = np.maximum(-D, 0.0)
    trade_cost = (gamma * np.abs(D)).sum(axis=1)                   # (N, T)
    grid_cost = lambda_buy * imp - lambda_sell * exp               # (N, T)
    grid_cost0 = lambda_buy * imp0 - lambda_sell * exp0            # (N, T)

    p2p_volume = D_pos.sum(axis=(0, 1))                            # (T,)
    trade_cost_t = trade_cost.sum(axis=0)
    p2p_fee = np.full_like(p2p_volume, np.nan)
    mask = p2p_volume > 1e-9
    p2p_fee[mask] = trade_cost_t[mask] / p2p_volume[mask]

    return {
        "imp": imp, "exp": exp, "imp0": imp0, "exp0": exp0,
        "p2p_in": D_pos.sum(axis=1), "p2p_out": D_neg.sum(axis=1),  # (N, T)
        "grid_cost": grid_cost, "grid_cost0": grid_cost0, "trade_cost": trade_cost,
        "p2p_volume": p2p_volume, "p2p_fee": p2p_fee,
        "trade_matrix": D_pos.sum(axis=2),                          # [buyer i, seller j] kWh
        "trade_fee_matrix": (gamma * D_pos).sum(axis=2),            # fee paid by buyer i on trades from j
    }

# ---------------------------------------------------------------------------
# UI helpers (Graph / Table / Text / Image schemas)
# ---------------------------------------------------------------------------

def _clean(values, nd=4):
    """JSON-safe list: Python floats, NaN/inf -> None."""
    return [None if not np.isfinite(v) else round(float(v), nd)
            for v in np.asarray(values, dtype=float).ravel()]


def _graph(title, graph_type, x_name, x_values, series):
    return {
        "graphType": graph_type,
        "title": title,
        "independent": {"name": x_name, "values": list(x_values)},
        "dependent": [{"name": name, "values": _clean(vals)} for name, vals in series],
    }


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _image_trade_matrix(matrix, house_names):
    n = len(house_names)
    fig, ax = plt.subplots(figsize=(1.2 * n + 3, 1.0 * n + 2.5))
    im = ax.imshow(matrix, cmap="YlGn")
    ax.set_xticks(range(n), labels=house_names, rotation=45, ha="right")
    ax.set_yticks(range(n), labels=house_names)
    ax.set_xlabel("Seller (from)")
    ax.set_ylabel("Buyer (to)")
    ax.set_title("Total P2P energy traded (kWh)")
    vmax = matrix.max() if matrix.size else 0
    for i in range(n):
        for j in range(n):
            if i != j:
                ax.text(j, i, f"{matrix[i, j]:.1f}", ha="center", va="center",
                        color="white" if vmax and matrix[i, j] > 0.6 * vmax else "black", fontsize=8)
    fig.colorbar(im, ax=ax, label="kWh")
    return _fig_to_base64(fig)


def _image_p2p_day_heatmap(p2p_volume, day_labels):
    n_days = len(day_labels)
    grid = p2p_volume[: n_days * STEPS_PER_DAY].reshape(n_days, STEPS_PER_DAY)
    fig, ax = plt.subplots(figsize=(10, 0.45 * n_days + 2))
    im = ax.imshow(grid, aspect="auto", cmap="viridis")
    ticks = np.arange(0, STEPS_PER_DAY + 1, STEPS_PER_DAY // 12)
    ax.set_xticks(ticks - 0.5, labels=[f"{int(t * 24 / STEPS_PER_DAY):02d}h" for t in ticks])
    ax.set_yticks(range(n_days), labels=day_labels)
    ax.set_xlabel("Time of day")
    ax.set_title("P2P energy traded per 15-min step (kWh)")
    fig.colorbar(im, ax=ax, label="kWh")
    return _fig_to_base64(fig)

# ---------------------------------------------------------------------------
# Visualizations returned to the UI
# ---------------------------------------------------------------------------

def _build_visualizations(gamma, admm, p_load, p_gen, fixed_price, timestamps, house_names) -> dict:
    D = np.asarray(admm["D_all"], dtype=float)
    P_g = np.asarray(admm["P_g_all"], dtype=float)
    mu = np.asarray(admm["mu_all"], dtype=float)
    iters = np.asarray(admm["iters"], dtype=int)
    T = P_g.shape[1]

    lambda_buy = np.full(T, float(fixed_price))
    lambda_sell = lambda_buy * SELL_RATIO
    ind = _compute_indicators(gamma, D, P_g, p_load, p_gen, lambda_buy, lambda_sell)

    time_labels = [ts.strftime("%Y-%m-%d %H:%M") for ts in timestamps]
    n_days = T // STEPS_PER_DAY
    day_starts = [timestamps[d * STEPS_PER_DAY] for d in range(n_days)]
    day_labels = [ts.strftime("%a %d/%m") for ts in day_starts]

    # ---------- Graphs ----------
    graph_energy = _graph(
        "Community energy flows (with vs without P2P)", "line", "Time", time_labels, [
            ("Load (kWh)", p_load.sum(axis=0)),
            ("Generation (kWh)", p_gen.sum(axis=0)),
            ("Grid import with P2P (kWh)", ind["imp"].sum(axis=0)),
            ("Grid export with P2P (kWh)", ind["exp"].sum(axis=0)),
            ("Grid import without P2P (kWh)", ind["imp0"].sum(axis=0)),
            ("Grid export without P2P (kWh)", ind["exp0"].sum(axis=0)),
            ("P2P volume (kWh)", ind["p2p_volume"]),
        ])

    graph_prices = _graph(
        "Prices per step", "line", "Time", time_labels, [
            ("Grid buy price (€/kWh)", lambda_buy),
            ("Grid sell price (€/kWh)", lambda_sell),
            ("Average P2P fee (€/kWh)", ind["p2p_fee"]),
            ("Mean shadow price μ (€/kWh)", mu.mean(axis=0)),
        ])

    graph_convergence = _graph(
        "ADMM iterations per step", "bar", "Time", time_labels,
        [("Iterations", iters)])

    graph_house_flows = _graph(
        "Grid exchange per house", "bar", "House", house_names, [
            ("Import with P2P (kWh)", ind["imp"].sum(axis=1)),
            ("Import without P2P (kWh)", ind["imp0"].sum(axis=1)),
            ("Export with P2P (kWh)", ind["exp"].sum(axis=1)),
            ("Export without P2P (kWh)", ind["exp0"].sum(axis=1)),
            ("P2P in (kWh)", ind["p2p_in"].sum(axis=1)),
            ("P2P out (kWh)", ind["p2p_out"].sum(axis=1)),
        ])

    daily = []
    for d in range(n_days):
        s = slice(d * STEPS_PER_DAY, (d + 1) * STEPS_PER_DAY)
        cost_p2p = ind["grid_cost"][:, s].sum() + ind["trade_cost"][:, s].sum()
        cost_no = ind["grid_cost0"][:, s].sum()
        daily.append((d, s, cost_p2p, cost_no))

    graph_daily_costs = _graph(
        "Daily community cost", "bar", "Day", day_labels, [
            ("Cost with P2P (€)", [c for _, _, c, _ in daily]),
            ("Cost without P2P (€)", [c for _, _, _, c in daily]),
        ])

    # ---------- Tables ----------
    table_houses = []
    for i, name in enumerate(house_names):
        cost_with = ind["grid_cost"][i].sum() + ind["trade_cost"][i].sum()
        cost_without = ind["grid_cost0"][i].sum()
        table_houses.append({
            "House": name,
            "Load (kWh)": round(float(p_load[i].sum()), 2),
            "Generation (kWh)": round(float(p_gen[i].sum()), 2),
            "Grid Import P2P (kWh)": round(float(ind["imp"][i].sum()), 2),
            "Grid Export P2P (kWh)": round(float(ind["exp"][i].sum()), 2),
            "P2P In (kWh)": round(float(ind["p2p_in"][i].sum()), 2),
            "P2P Out (kWh)": round(float(ind["p2p_out"][i].sum()), 2),
            "Grid Cost P2P (€)": round(float(ind["grid_cost"][i].sum()), 2),
            "P2P Fee (€)": round(float(ind["trade_cost"][i].sum()), 2),
            "Total Cost P2P (€)": round(float(cost_with), 2),
            "Total Cost no P2P (€)": round(float(cost_without), 2),
            "Savings (€)": round(float(cost_without - cost_with), 2),
        })

    table_daily = []
    for d, s, cost_p2p, cost_no in daily:
        gen_d = p_gen[:, s].sum()
        exp_d, exp0_d = ind["exp"][:, s].sum(), ind["exp0"][:, s].sum()
        table_daily.append({
            "Day": day_labels[d],
            "Cost P2P (€)": round(float(cost_p2p), 2),
            "Cost no P2P (€)": round(float(cost_no), 2),
            "Savings (€)": round(float(cost_no - cost_p2p), 2),
            "P2P Volume (kWh)": round(float(ind["p2p_volume"][s].sum()), 2),
            "Grid Import P2P (kWh)": round(float(ind["imp"][:, s].sum()), 2),
            "Grid Import no P2P (kWh)": round(float(ind["imp0"][:, s].sum()), 2),
            "Self-consumption P2P (%)": round(float(100 * (gen_d - exp_d) / gen_d), 2) if gen_d > 0 else 0.0,
            "Self-consumption no P2P (%)": round(float(100 * (gen_d - exp0_d) / gen_d), 2) if gen_d > 0 else 0.0,
            "Avg ADMM Iterations": round(float(iters[s].mean()), 2),
        })

    table_trades = []
    for i, buyer in enumerate(house_names):
        for j, seller in enumerate(house_names):
            energy = ind["trade_matrix"][i, j]
            if i != j and energy > 1e-6:
                table_trades.append({
                    "From (seller)": seller,
                    "To (buyer)": buyer,
                    "Energy (kWh)": round(float(energy), 3),
                    "Buyer fee (€)": round(float(ind["trade_fee_matrix"][i, j]), 3),
                })

    # ---------- Text summary ----------
    total_with = ind["grid_cost"].sum() + ind["trade_cost"].sum()
    total_without = ind["grid_cost0"].sum()
    savings = total_without - total_with
    savings_pct = 100 * savings / total_without if total_without > 0 else 0.0
    gen_total = p_gen.sum()
    sc_with = 100 * (gen_total - ind["exp"].sum()) / gen_total if gen_total > 0 else 0.0
    sc_without = 100 * (gen_total - ind["exp0"].sum()) / gen_total if gen_total > 0 else 0.0
    not_converged = int((iters >= admm["max_iter"]).sum())

    text_summary = (
        f"Period: {time_labels[0]} to {time_labels[-1]} ({n_days} days, {T} steps of 15 min), "
        f"{len(house_names)} houses.\n"
        f"Total cost with P2P: {total_with:.2f} €\n"
        f"Total cost without P2P: {total_without:.2f} €\n"
        f"Savings: {savings:.2f} € ({savings_pct:.1f}%)\n"
        f"P2P energy traded: {ind['p2p_volume'].sum():.2f} kWh "
        f"(fees: {ind['trade_cost'].sum():.2f} €)\n"
        f"Grid import: {ind['imp'].sum():.2f} kWh with P2P vs {ind['imp0'].sum():.2f} kWh without\n"
        f"Community self-consumption: {sc_with:.1f}% with P2P vs {sc_without:.1f}% without\n"
        f"ADMM: {iters.mean():.1f} iterations per step on average; "
        f"{not_converged} of {T} steps reached the {admm['max_iter']}-iteration limit."
    )

    # ---------- Images ----------
    image_trade_matrix = _image_trade_matrix(ind["trade_matrix"], house_names)
    image_p2p_heatmap = _image_p2p_day_heatmap(ind["p2p_volume"], day_labels)

    return {
        # Graph
        "graph_community_energy": graph_energy,
        "graph_prices": graph_prices,
        "graph_admm_convergence": graph_convergence,
        "graph_house_flows": graph_house_flows,
        "graph_daily_costs": graph_daily_costs,
        # Table
        "table_house_summary": table_houses,
        "table_daily_summary": table_daily,
        "table_p2p_trades": table_trades,
        # Text
        "text_summary": text_summary,
        # Image
        "image_trade_matrix": image_trade_matrix,
        "image_p2p_heatmap": image_p2p_heatmap,
    }