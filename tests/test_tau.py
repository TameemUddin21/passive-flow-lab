import numpy as np
import pandas as pd
from estimate_tau import fit_tau

def test_fit_tau_math():
    """Verify WLS through the origin calculates tau accurately."""
    true_tau = 0.135
    adv = np.array([1_000_000.0, 2_000_000.0])
    shares = np.array([50_000_000.0, 100_000_000.0])
    excess_volume = true_tau * shares

    df = pd.DataFrame({"shares": shares, "adv": adv, "excess_volume": excess_volume})
    result = fit_tau(df)
    assert np.isclose(result["tau_hat"], true_tau, atol=1e-5)