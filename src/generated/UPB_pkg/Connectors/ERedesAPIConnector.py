from OntologyToAPI import handle_upload_file  # helper to read files uploaded through the API/UI

# ---------------------------------------------------------------------------
# Entrypoint function (the name must match excode:hasFunction in ERedesAPIConnector.ttl)
# ---------------------------------------------------------------------------

async def RunERedesAPIConnector(data):
    # Parameters declared in the .ttl (bm:hasParameter) arrive in data.params, by their bm:hasParameterLabel

    # Insert the business logic here.
    comm_topology = _process()

    # The keys must match the outputs declared in the .ttl (bm:hasOutputMetadata)
    return {
    "status": "SUCCESS",  
    "community_topology": comm_topology
    }

# ---------------------------------------------------------------------------
# Auxiliary functions
# ---------------------------------------------------------------------------

def _process() -> dict:
    return {
            "0": [10],
            "1": [10],
            "2": [10],
            "3": [11],
            "4": [11],
            "5": [11],
            "6": [11],
            "7": [12],
            "8": [12],
            "9": [12],
            "10": [0, 1, 2, 13],
            "11": [3, 4, 5, 6, 13],
            "12": [7, 8, 9, 13],
            "13": [10, 11, 12]
        }
