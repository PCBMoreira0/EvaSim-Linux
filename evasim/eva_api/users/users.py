import time
from typing import Dict
from eva_sim import EvaSim
from controllers.sim_api_controller import SIM_APIController
from controllers.api_sim_controller import API_SIMController
from task_queue import put_to_queue


class ControllerData:
    def __init__(self, eva_sim:EvaSim, sim_api:SIM_APIController, api_sim:API_SIMController):
        self.eva_sim = eva_sim
        self.sim_api = sim_api
        self.api_sim = api_sim


sim_dicts : Dict[str, ControllerData] = {}
total_ids = 0

def add_new_intance(id : str):
    global total_ids
    c = SIM_APIController(total_ids)
    a = API_SIMController(total_ids)
    e = EvaSim(c, a, "Simulador " + str(total_ids), True)
    sim_dicts[id] = ControllerData(e, c, a)
    put_to_queue(e)
    while(e.gui is None): # verifica se o gui foi criado, pois caso chame um endpoint que o opere dará erro
        time.sleep(0.5)

    total_ids += 1

def get_dict():
    return {key : obj.eva_sim.name for key, obj in sim_dicts.items()}

def get_value(id:str):
    return sim_dicts[id]

def remove_dict(id : str):
    return sim_dicts.pop(id)