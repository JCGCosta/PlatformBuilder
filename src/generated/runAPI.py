
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from OntologyToAPI.core.APIGenerator import APIGenerator

if __name__ == "__main__":
    APIGen = APIGenerator(showLogs=False)
    APIGen.load_ontologies(paths=['./ASE_pkg/MarketMechanisms/TOUFIT.ttl', './ASE_pkg/Simulators/ECGeoLocationBasedSimulator.ttl', './UPB_pkg/Connectors/ERedesAPIConnector.ttl', './UPB_pkg/FileInterface/CommunityConsGenCSVUpload.ttl', './UPB_pkg/MarketMechanisms/DBMMarketMechanism.ttl', './UPB_pkg/MarketMechanisms/SDMMarketMechanism.ttl', './UPB_pkg/Optimization/ADMMOptimization.ttl'])
    APIGen.serialize_ontologies()
    api_app = APIGen.generate_api_routes()
    api_app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:3000', 'http://localhost:3000'], allow_methods=["*"], allow_headers=["*"])
    uvicorn.run(api_app, host='127.0.0.1', port=5000)
