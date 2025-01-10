from enum import Enum
from asyncio import Event

class Commands(str, Enum):
    MOTION = "Motion"
    TALK = "Talk"
    WAIT = "Wait"
    LISTEN = "Listen"
    LED_ANIM = "Led_animation"
    END = "End of script"

class SIM_APIController:
    def __init__(self, id):
        self.id = id
        self.current_command = {}
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

        self.current_command.update(command)

    def command_talk(self, text : str):
        command = {"command" : Commands.TALK.value}
        command["text"] = text
        self.current_command.update(command)

    def command_end(self):
        self.current_command.update({"command" : Commands.END})

    def command_wait(self, ms : int):
        self.current_command.update({"command":Commands.WAIT, "time":ms})

    def command_listen(self):
        self.current_command.update({"command":"Listen", "state":"waiting input"})
        self.trigger_event()

    def command_led_animation(self, color : str):
        self.current_command.update({"command": Commands.LED_ANIM, "color":color})