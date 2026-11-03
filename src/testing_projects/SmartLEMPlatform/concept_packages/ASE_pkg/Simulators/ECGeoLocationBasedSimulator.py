import inspect
import json
from datetime import datetime
from typing import List, Literal, Optional, Type

from OntologyToAPI import handle_upload_file
from pydantic import BaseModel, ValidationError

from SmartLEM.core import *
from SmartLEM.assets import *

# ---------------------------------------------------------------------------
# Data models of the full Energy Community configuration (single JSON input)
# ---------------------------------------------------------------------------

class BaselineLoadDTO(BaseModel):
    load_capacity: float
    installed_power: float

class BatteryAssetDTO(BaseModel):
    battery_storage: float
    capacity: float
    rated_power: float
    efficiency: float
    min_soc: float
    max_soc: float

class EVAssetDTO(BaseModel):
    ev_type: Literal['battery', 'fuel cell', 'hybrid', 'none']
    ev_charging: bool
    ev_charging_level: Literal["level 1", "level 2", "level 3"]
    ev_daily_distance_km: float
    ev_efficiency_kWh_per_km: float
    ev_charging_efficiency: float

class HeatPumpAssetDTO(BaseModel):
    hvac_power: float
    cop_heating: float
    cop_cooling: float
    cop_dhw: float

class PVAssetDTO(BaseModel):
    rated_power: float
    tilt: float
    orientation: float
    efficiency: float

class WindAssetDTO(BaseModel):
    rated_power: float
    ws_cut_in: float
    ws_cut_out: float
    ws_rated: float
    hub_height: float
    alpha: float

ASSET_MODELS: List[Type[BaseModel]] = [BaselineLoadDTO, BatteryAssetDTO, EVAssetDTO, HeatPumpAssetDTO, PVAssetDTO, WindAssetDTO]

class MemberDTO(BaseModel):
    member_id: int
    member_type: Literal["residential", "commercial", "utility"]
    building_size: int
    building_surface_area: float
    occupants: int
    appliances: int
    occupancy_schedule: Literal['daytime', 'evening', 'night']
    building_insulation: Optional[Literal['low', 'medium', 'high']] = None
    heating_type: Optional[Literal["individual", "central"]] = None
    heating_system: Optional[Literal["gas", "electric", "heat pump", "wood/coal", "none"]] = None
    cooling_system: Optional[Literal['heat pump', 'air conditioning', 'cooler', 'none']] = None
    water_heating_system: Optional[Literal['heat pump', 'electric', 'solar', 'other']] = None
    activity_type: Optional[Literal['office', 'retail', 'industrial', 'hospitality']] = None
    assets: dict

class ECConfigurationDTO(BaseModel):
    name: str
    latitude: float
    longitude: float
    members: List[MemberDTO]

# ---------------------------------------------------------------------------
# Entrypoint function
# ---------------------------------------------------------------------------

async def SimulateEnergyCommunity(data):
    """Receives the whole EC structure (members + assets) in one JSON file."""
    if data.params.get("ECConfiguration") is None:
        return {"status": "ERROR", "desc": "The energy community configuration is required."}
    file_path = handle_upload_file(data.params["ECConfiguration"])
    if ".json" not in file_path: 
        return {"status": "ERROR", "desc": "The ECConfiguration file must be .json file."}
    with open(file_path) as json_file: 
        raw_config = json.load(json_file)
    try:
        config = ECConfigurationDTO.model_validate(raw_config)
    except ValidationError as e:
        return {"status": "ERROR", "desc": f"Invalid energy community configuration: {e}"}
    if not config.members:
        return {"status": "ERROR", "desc": f"The {config.name} energy community does not have members."}
    return _run_community_simulation(config)

# ---------------------------------------------------------------------------
# Auxiliary functions
# ---------------------------------------------------------------------------

def _validate_asset(asset_key: str, asset_params: dict):
    model = next((m for m in ASSET_MODELS if m.__name__[:-3] == asset_key), None)
    if model is None:
        return f"Provided asset '{asset_key}' does not match any asset data model ({[m.__name__[:-3] for m in ASSET_MODELS]})."
    try:
        model.model_validate(asset_params)
    except ValidationError as e:
        return f"Asset '{asset_key}' has invalid parameters: {e}"
    return None

def _run_community_simulation(config: ECConfigurationDTO):
    EC = EnergyCommunity(config.latitude, config.longitude, 0, 0)
    try:
        EC.get_weather_from_api()
    except Exception:
        return {"status": "ERROR", "desc": "Error in retrieving data from the open-meteo API for the energy community."}

    for member_cfg in config.members:
        member_data = member_cfg.model_dump()
        assets = member_data.pop("assets")
        if not assets:
            return {"status": "ERROR", "desc": f"Member ID {member_cfg.member_id} does not have assets."}
        member = Member(member_id=member_cfg.member_id, member_type=member_cfg.member_type, assets=[])
        member.set_member_attributes(member_data)
        for key, params in assets.items():
            error = _validate_asset(key, params)
            if error:
                return {"status": "ERROR", "desc": error}
            member.set_member_attributes(params)
            member.create_member_states(EC.weather_data)
            cls = globals()[key]  # get asset class by name
            valid_params = inspect.signature(cls.__init__).parameters
            # the asset is named after its key, so an "asset_name" in the configuration must not be passed again
            asset = cls(key, **{k: v for k, v in member.__dict__.items() if k in valid_params and k != "asset_name"})
            member.add_asset(asset)
            member.simulate_assets_operation(EC.weather_data)
            member.aggregate_assets_states()

        EC.add_member(member)
    simulation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Community consumption and generation
    EC.aggregate_members_states()
    ec_cons_gen = EC.compute_aggregated_community_states()
    ec_cons_gen['Timestamp'] = ec_cons_gen['Timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')

    # Members consumption, generation
    member_cons, member_gen, member_net_balance, member_power, member_deficit, member_surplus, member_assets = {}, {}, {}, {}, {}, {}, {}
    for member in EC.members:
        member.states['Timestamp'] = member.states['Timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        member.all_assets_states['Timestamp'] = member.all_assets_states['Timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        member_cons[str(member.member_id)] = member.states[["Timestamp","consumption"]].to_dict(orient='records')
        member_gen[str(member.member_id)] = member.states[["Timestamp", "generation"]].to_dict(orient='records')
        member_net_balance[str(member.member_id)] = member.states[["Timestamp", "net_balance"]].to_dict(orient='records')
        member_power[str(member.member_id)] = member.states[["Timestamp", "power"]].to_dict(orient='records')
        member_deficit[str(member.member_id)] = member.states[["Timestamp", "deficit"]].to_dict(orient='records')
        member_surplus[str(member.member_id)] = member.states[["Timestamp", "surplus"]].to_dict(orient='records')
        member_assets[str(member.member_id)] = member.all_assets_states.to_dict(orient='records')

    return {
        "status": "SUCCESS",
        "simulation_timestamp": simulation_time,
        "community_aggregated_consumption": ec_cons_gen[["Timestamp","consumption"]].to_dict(orient='records'),
        "community_aggregated_generation": ec_cons_gen[["Timestamp","generation"]].to_dict(orient='records'),
        "community_aggregated_net_balance": ec_cons_gen[["Timestamp","net_balance"]].to_dict(orient='records'),
        "consumption_per_member": member_cons,
        "generation_per_member": member_gen,
        "net_balance_per_member": member_net_balance,
        "power_per_member": member_power,
        "surplus_per_member": member_surplus,
        "deficit_per_member": member_deficit,
        "asset_operation_per_member": member_assets,
        "community_aggregated_data_to_plot": {
                "graphType": "line",
                "title": "Community Aggregated Consumption and Generation",   
                "independent": {
                        "name": "Timestamp", 
                        "values": ec_cons_gen["Timestamp"].tolist()
                    },
                "dependent": [
                    {
                        "name": "Consumption",
                         "values": ec_cons_gen["consumption"].tolist()
                    },
                    {
                        "name": "Generation",
                         "values": ec_cons_gen["generation"].tolist()
                    },
                    {
                        "name": "NetBalance",
                         "values": ec_cons_gen["net_balance"].tolist()
                    },
                ]
             }
    }
