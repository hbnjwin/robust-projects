import pandas as pd
from typing import List, Dict, Any

def transform_records(records: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    # BUG: assumes all expected columns exist
    df["total"] = df["price"] * df["quantity"]
    # BUG: no handling for new unexpected columns
    df = df[["id", "name", "total"]]
    return df
