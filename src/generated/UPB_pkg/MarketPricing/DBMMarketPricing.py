from OntologyToAPI import handle_upload_file  # helper to read files uploaded through the API/UI

# ---------------------------------------------------------------------------
# Entrypoint function (the name must match excode:hasFunction in DBMMarketPricing.ttl)
# ---------------------------------------------------------------------------

async def RunDBMMarketPricing(data):
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

def _process(example_input: float) -> float:
    return example_input
