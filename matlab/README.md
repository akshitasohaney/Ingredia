# MATLAB integration

`POST /api/v1/matlab/ingredient-score` accepts `{ "values": [0.2, 0.6, 0.8] }` and runs `ingredient_score.m` through the MATLAB Engine for Python.

## Setup

1. Install MATLAB and use the same Python environment as this backend.
2. Install the Engine API from a MATLAB-aware terminal:

   ```powershell
   cd <MATLABROOT>\extern\engines\python
   python -m pip install .
   ```

3. Start FastAPI normally. MATLAB starts only on the first endpoint call.

Set `MATLAB_SCRIPTS_DIR` if the `.m` files reside elsewhere. Without MATLAB, this endpoint responds with HTTP 503 while the rest of the API remains available.

Add further capabilities as dedicated service methods and endpoints; never expose arbitrary MATLAB function names in client input.
