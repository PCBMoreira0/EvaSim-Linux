from fastapi import FastAPI
from .routes import simulator
import os

app = FastAPI()

app.include_router(simulator.router)

@app.get("/")
def home():
    return {"hello":"world"}