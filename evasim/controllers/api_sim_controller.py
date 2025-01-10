class API_SIMController:
    def __init__(self, id):
        self.id = id
        self.current_input = ""

    def next_step(self, eva_sim):
        return eva_sim.next_command_step()
    
    def importFile(self, eva_sim, fileName : str):
        eva_sim.importfile_API(fileName)

    def startSim(self, eva_sim):
        if eva_sim.script_file == "":
            return False
        
        eva_sim.setSimMode(None)
        return True

    def stopSim(self, eva_sim):
        eva_sim.stopScript(None)

    def send_input(self, eva_sim, input : str):
        self.current_input = input
        eva_sim.trigger_input_event()

    def get_input(self):
        input = self.current_input
        self.current_input = ""
        return input
        
