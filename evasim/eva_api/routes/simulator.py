from fastapi import APIRouter
import uuid
from eva_sim import EvaSim
from ..users.users import add_new_intance, get_dict, remove_dict, get_value
from task_queue import put_to_queue

import os

router = APIRouter(prefix="/sim", tags=["Simulator"])

@router.post("/init")
def init():
    sim_id = uuid.uuid4()
    add_new_intance(str(sim_id))
    return sim_id

@router.put("/import/{id}")
def import_file(id : str, path : str):
    from experiences.experiences import get_path
    if not os.path.exists(get_path(path)):
        return {"status":"file not found"}
    get_value(id).importfile_API(path)
    return {"status":"success"}

@router.post("/start/{id}")
def start(id : str):
    if id not in get_dict():
        return {"status":"key not found"}
    
    get_value(id).setSimMode(None)
    return {"status":"success"}

@router.post("/next/{id}")
async def next(id:str):
    if id not in get_dict():
        return {"status":"key not found"}
    
    e = get_value(id)
    if not e.next_command_step():
        return {"status":"script is not playing"}
    
    s = await e.state_controller.get_result()
    return s

@router.post("/stop/{id}")
def stop(id : str):
    if id not in get_dict():
        return {"status":"key not found"}
    e = get_value(id)
    if not e.play: return {"status":"script not playing"}
    e.stopScript(None)
    return {"status": "success"}

@router.delete("/delete/{id}")
def delete_sim(id : str):
    if id not in get_dict():
        return {"status":"key not found"}
    remove_dict(id).window.destroy()
    return {"status": "success"}

@router.get("/dicts")
def dicts():
    return get_dict()