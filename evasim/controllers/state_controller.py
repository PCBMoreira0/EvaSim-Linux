from enum import Enum
from asyncio import Event

class Commands(str, Enum):
    MOTION = "Motion"
    TALK = "Talk"
    END = "End of script"

class StateController:
    def __init__(self):
        self.current_command = []
        self.result_event = Event()

    async def get_result(self):
        self.current_command.clear()
        self.result_event.clear()
        await self.result_event.wait()
        return self.current_command

    def trigger_event(self):
        self.result_event.set()

    def command_motion(self, attrib : str, detail : str):
        attrib = attrib.lower()
        command = {"command" : Commands.MOTION.value}
        if attrib == "left-arm":
            command["left-arm"] = detail

        if attrib == "right-arm":
            command["right-arm"] = detail

        if attrib == "head":
            command["head"] = detail
        else:
            if attrib == "type":
                command["type"] = detail

        self.current_command.append(command)

    def command_talk(self, text : str):
        command = {"command" : Commands.TALK.value}
        command["text"] = text
        self.current_command.append(command)

    def command_end(self):
        self.current_command.append({"command" : Commands.END})