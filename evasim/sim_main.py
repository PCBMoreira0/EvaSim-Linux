from tkinter import Tk

from eva_sim import EvaSim
import threading
import task_queue
from queue import Empty

root = Tk()

def get_root():
    return root

def process_queue():
    """Processa as tarefas da fila na thread principal."""
    try:
        while not task_queue.isEmpty():
            new_sim = task_queue.pop_queue()
            new_sim.init_sim(root)
            new_sim.powerOn(None)
    except Empty:
        pass

    root.after(500, process_queue)


def run_uvicorn():
    import uvicorn
    uvicorn.run("eva_api.main:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    # e = EvaSim('SLA', False)
    # e.init_sim(root)
    t = threading.Thread(target=run_uvicorn, daemon=True)
    t.start()

    root.after(100, process_queue)
    root.mainloop()