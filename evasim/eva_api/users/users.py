from typing import Dict
from eva_sim import EvaSim
from task_queue import put_to_queue

sim_dicts : Dict[str, EvaSim] = {"ainda" : EvaSim()}
total_ids = 0

def add_new_intance(id : str):
    global total_ids
    e = EvaSim("Simulador " + str(total_ids), True)
    sim_dicts[id] = e
    put_to_queue(e)
    total_ids += 1

def get_dict():
    return {key : obj.name for key, obj in sim_dicts.items()}

def get_value(id:str):
    return sim_dicts[id]

def remove_dict(id : str):
    return sim_dicts.pop(id)