from fastapi import APIRouter
import uuid
from eva_sim import EvaSim
from controllers.api_sim_controller import API_SIMController
from controllers.sim_api_controller import SIM_APIController

from ..users.users import add_new_intance, get_dict, remove_dict, get_value
from task_queue import put_to_queue
from pydantic import BaseModel

import os

class InputModel(BaseModel):
    input : str


router = APIRouter(prefix="/sim", tags=["Simulator"])

@router.post("/init")
def init():
    sim_id = uuid.uuid1()
    add_new_intance(str(sim_id))
    return sim_id

@router.put("/import/{id}")
def import_file(id : str, path : str):
    from experiences.experiences import get_path

    if not os.path.exists(get_path(path)):
        return {"status":"file not found"}
    
    c = get_value(id)
    c.api_sim.importFile(c.eva_sim, path)
    return {"status":"success"}

@router.post("/start/{id}")
def start(id : str):
    if id not in get_dict():
        return {"status":"key not found"}
    
    c = get_value(id)

    if c.eva_sim.play:
        return {"status":"script is already playing"}
    
    if not c.api_sim.startSim(c.eva_sim):
        return {"error":"no file imported"}
    return {"status":"success"}

@router.post("/next/{id}")
async def next(id:str):
    if id not in get_dict():
        return {"status":"key not found"}
    
    s = {}
    
    c = get_value(id)

    if c.eva_sim.isWaitingInput:
            return {"status":"waiting input"}
    
    while not s:
        if not c.api_sim.next_step(c.eva_sim):
            return {"status":"script is not playing"}

        s = await c.sim_api.get_result()

    return s

@router.post("/send/{id}")
def send_input(id:str, input : InputModel):
    c = get_value(id)
    
    if c.eva_sim.isWaitingInput:
        c.api_sim.send_input(c.eva_sim, input.input)
        return {"status": "success"}
    else:
        return {"status":"not waiting input"}

@router.post("/stop/{id}")
def stop(id : str):
    if id not in get_dict():
        return {"status":"key not found"}
    
    c = get_value(id)
    if not c.eva_sim.play: return {"status":"script not playing"}
    
    c.api_sim.stopSim(c.eva_sim)
    return {"status": "success"}

@router.delete("/delete/{id}")
def delete_sim(id : str):
    if id not in get_dict():
        return {"status":"key not found"}
    
    remove_dict(id).eva_sim.window.destroy()

    return {"status": "success"}

@router.get("/dicts")
def dicts():
    return get_dict()