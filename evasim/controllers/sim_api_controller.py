from enum import Enum
from asyncio import Event

class Commands(str, Enum):
    MOTION = "Motion"
    TALK = "Talk"
    WAIT = "Wait"
    LISTEN = "Listen"
    LED_ANIM = "Led_animation"
    LIGHT = "Light"
    LED = "Led"
    EMOTION = "Emotion"
    AUDIO = "Audio"
    USER_HAND_POSE = "User_hand_pose"
    USER_EMOTION = "User_emotion"
    QR_READ = "QR_Read"
    USER_ID = "User_id"
    END = "End of script"

class SIM_APIController:
    def __init__(self, id):
        self.id = id
        self.current_command = {}
        self.command_list = []
        self.result_event = Event()

    async def get_result(self):
        self.command_list.clear()
        self.current_command.clear()
        self.result_event.clear()
        await self.result_event.wait()
        return {"commands":self.command_list}

    def trigger_event(self):
        self.result_event.set()

    def input_command(self, command:Commands):
        self.command_list.append({"command":command, "state":"waiting input"})
        # self.current_command.update({"command":command, "state":"waiting input"})
        self.trigger_event()

    def command_motion(self, attrib : str, detail : str):
        attrib = attrib.lower()
        command = {"command" : Commands.MOTION.value}
        command["member"] = attrib
        command["direction"] = detail
        self.command_list.append(command)
        # self.current_command.update(command)

    def command_talk(self, text : str):
        command = {"command" : Commands.TALK.value}
        command["text"] = text
        self.command_list.append(command)
        # self.current_command.update(command)

    def command_end(self):
        self.command_list.append({"command" : Commands.END})
        # self.current_command.update({"command" : Commands.END})

    def command_wait(self, ms : int):
        self.command_list.append({"command":Commands.WAIT, "time":ms})
        # self.current_command.update({"command":Commands.WAIT, "time":ms})

    def command_listen(self):
        self.input_command(Commands.LISTEN)

    def command_led_animation(self, color : str):
        self.command_list.append({"command": Commands.LED_ANIM, "color":color})
        # self.current_command.update({"command": Commands.LED_ANIM, "color":color})

    def command_light(self, color : str, state : str):
        self.command_list.append({"command": Commands.LIGHT, "color":color, "state":state})
        # self.current_command.update({"command": Commands.LIGHT, "color":color, "state":state})
    
    def command_evaEmotion(self, emotion : str):
        self.command_list.append({"command":Commands.EMOTION, "emotion":emotion})
        # self.current_command.update({"command":Commands.EMOTION, "emotion":emotion})

    def command_audio(self, audioFile, block):
        self.command_list.append({"command":Commands.AUDIO, "file":audioFile, "block":block})
        # self.current_command.update({"command":Commands.AUDIO, "file":audioFile, "block":block})

    def command_userHandPose(self):
        self.input_command(Commands.USER_HAND_POSE)

    def command_userEmotion(self):
        self.input_command(Commands.USER_EMOTION)

    def command_qrRead(self):
        self.input_command(Commands.QR_READ)

    def command_userID(self):
        self.input_command(Commands.USER_ID)