from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class SearchRequest(BaseModel):
    keyword: str
    category: str = ""

@app.post("/api/search")
async def search(req: SearchRequest):
    # BUG: no encoding handling for Chinese characters
    # BUG: special characters cause 500 errors
    keyword = req.keyword
    result = do_search(keyword)
    return {"results": result}

def do_search(keyword: str):
    # BUG: no input sanitization
    return [{"id": 1, "name": f"Result for {keyword}"}]
