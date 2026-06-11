from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class ABTestConfig(BaseModel):
    name: str
    variants: list
    traffic_ratio: list

# TODO: implement A/B test routing feature
# - Route requests to different model versions by ratio
# - Collect and compare results automatically
# - Support dynamic ratio adjustment
