import queue
from eva_sim import EvaSim
top_queue = queue.Queue()

def put_to_queue(sim : EvaSim):
    top_queue.put(sim)

def isEmpty():
    return top_queue.empty()

def pop_queue():
    return top_queue.get_nowait()