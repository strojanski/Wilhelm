from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from datetime import datetime

app = FastAPI(
    title="FastAPI Docker Demo",
    description="A simple FastAPI application running in Docker",
    version="1.0.0",
)


# In-memory "database"
items_db: dict[int, dict] = {}
next_id = 1


class ItemCreate(BaseModel):
    name: str
    description: str | None = None
    price: float


class Item(ItemCreate):
    id: int
    created_at: datetime


@app.get("/")
def read_root():
    return {
        "message": "Hello from FastAPI in Docker!",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/items", response_model=List[Item])
def list_items():
    return list(items_db.values())


@app.post("/items", response_model=Item, status_code=201)
def create_item(item: ItemCreate):
    global next_id
    new_item = {
        "id": next_id,
        "created_at": datetime.utcnow(),
        **item.model_dump(),
    }
    items_db[next_id] = new_item
    next_id += 1
    return new_item


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int):
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    return items_db[item_id]


@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int):
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    del items_db[item_id]