from fastapi import FastAPI
from .routes import simulator

app = FastAPI()

app.include_router(simulator.router)

@app.get("/")
def home():
    return {"hello":"world"}    