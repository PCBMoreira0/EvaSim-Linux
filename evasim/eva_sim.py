#!/usr/bin/env python3
# EvaSIM 2.0 - Software Simulador para o robô EVA
# Software developed by Marcelo Marques da Rocha
# MidiaCom Laboratory - Universidade Federal Fluminense
# This work was funded by CAPES and Google Research

import platform 

import hashlib
import re
import os

import random as rnd
import xml.etree.ElementTree as ET

from eva_memory import EvaMemory # EvaSIM memory module

import json_to_evaml_conv # json to XML conversion module (No longer used in this version of the simulator)

from tkinter import *
from tkinter import messagebox
from tkinter import filedialog as fd
import tkinter


# Adapter module for the audio library
# Depending on the OS it matters and defines a function called "self.playsound"
from play_audio import playsound

import time
import threading
import sys

# importing libraries to place Listen using API

# import speech_recognition as sr

import face_recognition.recognition as fr

import handpose.handpose as hp

import emotion_recognition.emotion as ue

import qr.qrRead as qr


import config # Module with the constants and parameters used in other modules.

TTS_IBM_WATSON = False # Define the use of IBM Watson service
ROBOT_MODE_ENABLED = False # 


class EvaSim:
    def __init__(self):
        global TTS_IBM_WATSON, ROBOT_MODE_ENABLED
        if len(sys.argv) > 1: # Verify if is an argument in the command line
            for parameter in sys.argv[1:]: # Sweep all parameters
                if parameter.lower() == "tts=ibm-watson": # Watson was selected
                    TTS_IBM_WATSON = True
                elif parameter.lower() == "robot-mode=on":
                    ROBOT_MODE_ENABLED = True
                elif parameter.lower() == "h" or parameter.lower() == "-h" or parameter.lower() == "help" or parameter.lower() == "-help":
                    print("\n############################################################")
                    print("                   EvaSIM Help Information")
                    print("############################################################")
                    print("-help, help\tShow all available parameters.") 
                    print("tts=ibm-watson\tUse the IBM Watson TTS service.") 
                    print("robot-mode=on\tEnable robot mode control and execution.")
                    print("############################################################\n")
                    exit(1)
                else:
                    print("\nSorry, I guess you entered an illegal parameter.")
                    exit(1)

        # Select the self.gui definition file for the host operating system
        if platform.system() == "Linux":
            print("\nLinux platform identified. Loading self.gui formatting for Linux.\n")
            import gui_linux as EvaSIM_gui # Definition of the graphical user interface (Linux)
            audio_ext = ".mp3" # Audio extension used by the audio library on Linux
            ibm_audio_ext = "audio/mp3" # Audio extension used to generate watson audios
        elif platform.system() == "Windows":
            # This version of the Graphical User Interface (self.gui) has been discontinued.
            print("Windows platform identified. Loading self.gui formatting for Windows.")
            print("This version of the Graphical User Interface (self.gui) has been discontinued. Sorry!\n")
            exit(1)
        else:
            print("Sorry, the current OS is not supported by EvaSIM.") # Incompatible OS
            exit(1)

        self.broker = config.MQTT_BROKER_ADRESS # broker adress
        self.port = config.MQTT_PORT # broker port
        self.topic_base = config.EVA_TOPIC_BASE

        self.EVA_ROBOT_STATE = "FREE"
        self.EVA_DOLLAR = ""
        self.RUNNING_MODE = "SIMULATOR" # EvaSIM operating mode (Physical Robot Simulator or self.player)

        # Watson library import and api key configuration
        if TTS_IBM_WATSON: # Only if tts=ibm-watson option was selected in command line
            print("\n\nWARNING: You have chosen to use the IBM Watson Text-To-Speech service. To do this, you must have installed the Watson library for Python and you must also have, in the EvaSIM   directory,    the file (ibm_cred.txt) with the IBM service credentials.")
            print("\n\nPlease, press <ENTER> to continue or <ctrl> + c to stop.")
            input()

            from ibm_watson.text_to_speech_v1 import Voice
            from ibm_watson import TextToSpeechV1
            from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

            with open("ibm_cred.txt", "r") as ibm_cred:
                ibm_config = ibm_cred.read().splitlines()
            apikey = ibm_config[0]
            url = ibm_config[1]
            # Setup watson service
            authenticator = IAMAuthenticator(apikey)
            # TTS service
            tts = TextToSpeechV1(authenticator = authenticator)
            tts.set_service_url(url)


        # import and config mqtt library and client
        if ROBOT_MODE_ENABLED: # Only if robot-mode=on was selected in command line
            print("\n\nWARNING: You have chosen to use the Robot mode. To do this, you must have installed the paho.mqtt library and also install and configure the mosquitto broker.")
            print("\n\nPlease, press <ENTER> to continue or <ctrl> + c to stop.")
            input()
            from paho.mqtt import client as mqtt_client
            # MQTT
            # The callback for when the client receives a CONNACK response from the server.
            def on_connect(client, userdata, flags, rc):
                print("Connected with result code " + str(rc))
                # Subscribing in on_connect() means that if we lose the connection and
                # Reconnect then subscriptions will be renewed.
                client.subscribe(topic=[(self.topic_base + '/state', 1), ])
                client.subscribe(topic=[(self.topic_base + '/var/dollar', 1), ])

            # The callback for when a PUBLISH message is received from the server.
            def on_message(client, userdata, msg):
                if msg.topic == self.topic_base + '/state':
                    self.EVA_ROBOT_STATE = "FREE" # msg.payload.decode()
                elif msg.topic == self.topic_base + '/var/dollar':
                    self.EVA_DOLLAR = msg.payload.decode()

            self.client = mqtt_client.Client()
            self.client.on_connect = on_connect
            self.client.on_message = on_message
            self.client.connect(self.broker, self.port)
            self.client.loop_start()

        else: # User not selected the robot-mode=on in commend line
            class Fake_Mqtt_Client(): # Fake mqtt class to work woth mqtt commands
                def __init__(self):
                    print("A fake mqtt client was created!")
                def publish(self, fake_topic, fake_message):
                    print(f"A fake publish method with topic: {fake_topic} and message: {fake_message} is being executed.")
            self.client = Fake_Mqtt_Client()


        # VM global variables
        self.root = {}
        self.script_node = {}
        self.links_node = {}
        self.fila_links =  [] # Link queue (commands)
        self.thread_pop_pause = False
        self.play = False # self.play status of the script. This variable has an influence on the function. link_process
        self.script_file = "" # Variable that stores the pointer to the xml script file on disk.

        # Eva memory
        self.memory = EvaMemory()

        # Create the Tkinter window
        self.window = Tk()
        self.gui = EvaSIM_gui.Gui(self.window) # Instance of the self.gui class within the graphical user interface definition module

        self.font1 = self.gui.font1 # Sse the same font defined in the self.gui module

        # EVA expressions images
        self.im_eyes_neutral = PhotoImage(file = "images/eyes_neutral.png")
        self.im_eyes_angry = PhotoImage(file = "images/eyes_angry.png")
        self.im_eyes_sad = PhotoImage(file = "images/eyes_sad.png")
        self.im_eyes_happy = PhotoImage(file = "images/eyes_happy.png")
        self.im_eyes_fear = PhotoImage(file = "images/eyes_fear.png")
        self.im_eyes_surprise = PhotoImage(file = "images/eyes_surprise.png")
        self.im_eyes_disgust = PhotoImage(file = "images/eyes_disgust.png")
        self.im_eyes_inlove = PhotoImage(file = "images/eyes_inlove.png")
        self.im_eyes_on = PhotoImage(file = "images/eyes_on.png")
  
        # Matrix Voice images
        self.im_matrix_blue = PhotoImage(file = "images/matrix_blue.png")
        self.im_matrix_green = PhotoImage(file = "images/matrix_green.png")
        self.im_matrix_yellow = PhotoImage(file = "images/matrix_yellow.png")
        self.im_matrix_white = PhotoImage(file = "images/matrix_white.png")
        self.im_matrix_red = PhotoImage(file = "images/matrix_red.png")
        self.im_matrix_grey = PhotoImage(file = "images/matrix_grey.png")
        self.im_bt_play = PhotoImage(file = "images/bt_play.png")
        self.im_bt_stop = PhotoImage(file = "images/bt_stop.png")


        # Connect callbacks to buttons
        # The use of another module to define the self.gui did not allow callbacks to be associated with buttons at the time of their creation
        # Using the bind method to define callbacks has a limitation
        # The element, even in the "disable" state, continues to respond to mouse click events
        # Therefore, when disabling a button, it is necessary to use "unbind" to unbind the callback from the button
        # If the button is placed in the "normal" state, the callback must be reset using "bind" again
        self.gui.bt_power.bind("<Button-1>", self.powerOn)
        self.gui.bt_clear.bind("<Button-1>", self.clear_terminal)


        # WoZ light buttons binding
        self.gui.bt_bulb_green_btn.bind("<Button-1>", self.woz_light_green)
        self.gui.bt_bulb_blue_btn.bind("<Button-1>", self.woz_light_blue)
        self.gui.bt_bulb_off_btn.bind("<Button-1>", self.woz_light_black)
        self.gui.bt_bulb_pink_btn.bind("<Button-1>", self.woz_light_pink)
        self.gui.bt_bulb_red_btn.bind("<Button-1>", self.woz_light_red)
        self.gui.bt_bulb_yellow_btn.bind("<Button-1>", self.woz_light_yellow)
        self.gui.bt_bulb_white_btn.bind("<Button-1>", self.woz_light_white)

        # WoZ expression buttons binding
        self.gui.bt_exp_angry.bind("<Button-1>", self.woz_expression_angry)
        self.gui.bt_exp_fear.bind("<Button-1>", self.woz_expression_fear)
        self.gui.bt_exp_happy.bind("<Button-1>", self.woz_expression_happy)
        self.gui.bt_exp_neutral.bind("<Button-1>", self.woz_expression_neutral)
        self.gui.bt_exp_sad.bind("<Button-1>", self.woz_expression_sad)
        self.gui.bt_exp_surprise.bind("<Button-1>", self.woz_expression_surprise)
        self.gui.bt_exp_disgust.bind("<Button-1>", self.woz_expression_disgust)
        self.gui.bt_exp_inlove.bind("<Button-1>", self.woz_expression_inlove)

        # WoZ led buttons binding
        self.gui.bt_led_stop.bind("<Button-1>", self.woz_led_stop)
        self.gui.bt_led_angry.bind("<Button-1>", self.woz_led_angry)
        self.gui.bt_led_sad.bind("<Button-1>", self.woz_led_sad)
        self.gui.bt_led_angry2.bind("<Button-1>", self.woz_led_angry2)
        self.gui.bt_led_happy.bind("<Button-1>", self.woz_led_happy)
        self.gui.bt_led_listen.bind("<Button-1>", self.woz_led_listen)
        self.gui.bt_led_rainbow.bind("<Button-1>", self.woz_led_rainbow)
        self.gui.bt_led_speak.bind("<Button-1>", self.woz_led_speak)
        self.gui.bt_led_surprise.bind("<Button-1>", self.woz_led_surprise)
        self.gui.bt_led_white.bind("<Button-1>", self.woz_led_white)
    
        # Woz arms motion buttons binding
        self.gui.bt_arm_left_motion_up.bind("<Button-1>", self.woz_arm_left_motion_up)
        self.gui.bt_arm_right_motion_up.bind("<Button-1>", self.woz_arm_right_motion_up)
        self.gui.bt_arm_left_motion_down.bind("<Button-1>", self.woz_arm_left_motion_down)
        self.gui.bt_arm_right_motion_down.bind("<Button-1>", self.woz_arm_right_motion_down)
        self.gui.bt_arm_left_motion_pos_0.bind("<Button-1>", self.woz_arm_left_motion_pos_0)
        self.gui.bt_arm_right_motion_pos_0.bind("<Button-1>", self.woz_arm_right_motion_pos_0)
        self.gui.bt_arm_left_motion_pos_1.bind("<Button-1>", self.woz_arm_left_motion_pos_1)
        self.gui.bt_arm_right_motion_pos_1.bind("<Button-1>", self.woz_arm_right_motion_pos_1)
        self.gui.bt_arm_left_motion_pos_2.bind("<Button-1>", self.woz_arm_left_motion_pos_2)
        self.gui.bt_arm_right_motion_pos_2.bind("<Button-1>", self.woz_arm_right_motion_pos_2)
        self.gui.bt_arm_left_motion_pos_3.bind("<Button-1>", self.woz_arm_left_motion_pos_3)
        self.gui.bt_arm_right_motion_pos_3.bind("<Button-1>", self.woz_arm_right_motion_pos_3)
        self.gui.bt_arm_left_motion_shake.bind("<Button-1>", self.woz_arm_left_motion_shake)
        self.gui.bt_arm_right_motion_shake.bind("<Button-1>", self.woz_arm_right_motion_shake)
        
        # WoZ head motion buttons binding
        self.gui.bt_head_motion_yes.bind("<Button-1>", self.woz_head_motion_yes)
        self.gui.bt_head_motion_no.bind("<Button-1>", self.woz_head_motion_no)
        self.gui.bt_head_motion_center.bind("<Button-1>", self.woz_head_motion_center)
        self.gui.bt_head_motion_left.bind("<Button-1>", self.woz_head_motion_left)
        self.gui.bt_head_motion_right.bind("<Button-1>", self.woz_head_motion_right)
        self.gui.bt_head_motion_up.bind("<Button-1>", self.woz_head_motion_up)
        self.gui.bt_head_motion_down.bind("<Button-1>", self.woz_head_motion_down)
        self.gui.bt_head_motion_2left.bind("<Button-1>", self.woz_head_motion_2left)
        self.gui.bt_head_motion_2right.bind("<Button-1>", self.woz_head_motion_2right)
        self.gui.bt_head_motion_2up.bind("<Button-1>", self.woz_head_motion_2up)
        self.gui.bt_head_motion_2down.bind("<Button-1>", self.woz_head_motion_2down)
        self.gui.bt_head_motion_up_left.bind("<Button-1>", self.woz_head_motion_up_left)
        self.gui.bt_head_motion_up_right.bind("<Button-1>", self.woz_head_motion_up_right)
        self.gui.bt_head_motion_down_left.bind("<Button-1>", self.woz_head_motion_down_left)
        self.gui.bt_head_motion_down_right.bind("<Button-1>", self.woz_head_motion_down_right)

        # TTS buttons binding
        self.gui.bt_send_tts.bind("<Button-1>", self.woz_tts)

        self.gui.mainloop()

    # Variable control function that blocks popups
    def lock_thread_pop(self):
        self.thread_pop_pause = True
    
    def unlock_thread_pop(self):
        self.thread_pop_pause = False


    # Function to write memory data to the variable table
    def tab_load_mem_vars(self):
        for i in self.gui.tab_vars.get_children(): # Clear table values
            self.gui.tab_vars.delete(i)

        for var_name in self.memory.vars: # Read memory by inserting values ​​into the table
            self.gui.tab_vars.insert(parent='',index='end',text='', values=(var_name, self.memory.vars[var_name]))



    # Function to write memory data to the mem dollar table
    def tab_load_mem_dollar(self):
        indice = 1 # Index for the dollar variable
        for i in self.gui.tab_dollar.get_children(): # Clear table values
            self.gui.tab_dollar.delete(i)
    
        for var_dollar in self.memory.var_dolar: # Read memory by inserting values ​​into the table
            if indice == len(self.memory.var_dolar):
                var_name = "$"
            else:
                var_name = "$" + str(indice)
    
            self.gui.tab_dollar.insert(parent='',index='end',text='', values=(var_name, var_dollar[0], var_dollar[1]))
            indice = indice + 1


    # Eva initialization function
    def evaInit(self):
        self.gui.bt_power['state'] = DISABLED
        self.gui.bt_power.unbind("<Button-1>")
        self.evaEmotion("POWER_ON")
        self.gui.terminal.insert(INSERT, "\nSTATE: Initializing.")
        self.gui.terminal.insert(INSERT, "\nSTATE: Entering in standby mode.")
        self.gui.bt_import['state'] = NORMAL
        self.gui.bt_import.bind("<Button-1>", self.importFileThread)
        self.gui.bt_reload['state'] = DISABLED
        self.gui.bt_reload.bind("<Button-1>", self.reloadFile)
        self.evaMatrix("white")
        while self.gui.bt_run_sim['state'] == DISABLED: # Matrix light animation on stand by
            self.evaMatrix("white")
            time.sleep(0.5)
            self.evaMatrix("grey")
            time.sleep(0.5)


    # Eva powerOn function
    def powerOn(self, s):
        threading.Thread(target=self.evaInit, args=()).start()


    # Run in Simulator mode
    def setSimMode(self, s):
        self.RUNNING_MODE = "SIMULATOR"
        self.runScript()


    # Runs in EVA Robot self.player mode
    def setEVAMode(self, s):
        self.RUNNING_MODE = "EVA_ROBOT"
        self.runScript()

    # Activate the thread that runs the script
    def runScript(self):
        # initialize the robot memory
        print("Intializing the robot memory.")
        self.memory.var_dolar = []
        self.memory.vars = {}
        self.memory.reg_case = 0
        # Cleaning the tables
        print("Clearing memory map tables.")
        self.tab_load_mem_dollar()
        self.tab_load_mem_vars()
        # Initializing the memory of simulator
        self.fila_links =  []
        # Buttons states
        self.gui.bt_run_sim['state'] = DISABLED
        self.gui.bt_run_sim.unbind("<Button-1>")
        self.gui.bt_run_robot['state'] = DISABLED
        self.gui.bt_run_robot.unbind("<Button-1>")
        self.gui.bt_import['state'] = DISABLED
        self.gui.bt_reload['state'] = DISABLED
        self.gui.bt_stop['state'] = NORMAL
        self.gui.bt_stop.bind("<Button-1>", self.stopScript)
        self.gui.bt_import.unbind("<Button-1>")
        self.play = True # ativa a var do self.play do script
        self.root.find("settings").find("voice").attrib["key"]
        self.busca_links(self.root.find("settings").find("voice").attrib["key"]) # o primeiro elemento da interação é o voice
        threading.Thread(target=self.link_process, args=()).start()

    # Activate the script self.play var
    def stopScript(self, s):
        self.gui.bt_run_sim['state'] = NORMAL
        self.gui.bt_run_sim.bind("<Button-1>", self.setSimMode)
        if ROBOT_MODE_ENABLED: self.gui.bt_run_robot['state'] = NORMAL
        self.gui.bt_run_robot.bind("<Button-1>", self.setEVAMode)
        self.gui.bt_stop['state'] = DISABLED
        self.gui.bt_stop.unbind("<Button-1>")
        self.gui.bt_import['state'] = NORMAL
        self.gui.bt_reload['state'] = NORMAL
        self.gui.bt_import.bind("<Button-1>", self.importFileThread)
        self.play = False # desativa a var de self.play do script. Faz com que o script seja interrompido
        self.EVA_ROBOT_STATE = "FREE" # libera a execução, caso esteja executando algum comando bloqueante

    # Import file thread
    def importFileThread(self, s):
        threading.Thread(target=self.importFile, args=()).start()

    # Eva Import Script function
    def importFile(self):
        print("Importing a file.")
        # Now EvaSIM can read json
        filetypes = (('evaML files', '*.xml *.json'), )
        self.script_file = fd.askopenfile(mode = "r", title = 'Open an EvaML Script File', initialdir = './', filetypes = filetypes)
        # imagine that the guy will read a json or an xml
        if (re.findall(r'\.(xml|json|JSON|XML)', str(self.script_file)))[0].lower() == "json": # leitura de json
            print("Converting and running a JSON file.")
            # self.script_file is not a string and still has information beyond the file path
            # So it needs to be processed before being passed to the conversion module
            json_to_evaml_conv.converte(str(self.script_file).split("'")[1], tkinter)
            self.script_file = "_json_to_evaml_converted.xml" # Json file converted to XML
        else: # Reading an XML
            print("Running a XML file.")
        # VM variables
        tree = ET.parse(self.script_file)  # XML code file
        self.root = tree.getroot() # EvaML root node
        self.script_node = self.root.find("script")
        self.links_node = self.root.find("links")
        self.gui.bt_run_sim['state'] = NORMAL
        self.gui.bt_run_sim.bind("<Button-1>", self.setSimMode)
        if ROBOT_MODE_ENABLED: self.gui.bt_run_robot['state'] = NORMAL
        self.gui.bt_run_robot.bind("<Button-1>", self.setEVAMode)
        self.gui.bt_stop['state'] = DISABLED
        self.gui.bt_reload['state'] = NORMAL
        self.evaEmotion("NEUTRAL")
        only_file_name = str(self.script_file).split("/")[-1].split("'")[0]
        self.window.title("Eva Simulator for EvaML - Version 2.0 - UFF / MidiaCom / CICESE -- [ " + only_file_name + " ]")
        self.gui.terminal.insert(INSERT, '\nSTATE: Script => ' + only_file_name + ' was LOADED.')
        self.gui.terminal.see(tkinter.END)

    def reloadFile(self, s):
        self.script_file.seek(0) # Places the file object pointer at the beginning
        tree = ET.parse(self.script_file) # # XML code file
        self.root = tree.getroot() # EvaML root node
        self.script_node = self.root.find("script")
        self.links_node = self.root.find("links")
        self.evaEmotion("NEUTRAL")
        only_file_name = str(self.script_file).split("/")[-1].split("'")[0]
        self.gui.terminal.insert(INSERT, '\nSTATE: Script => ' + only_file_name + ' was RELOADED.')
        self.gui.terminal.see(tkinter.END)


    def clear_terminal(self, s):
        self.gui.terminal.delete('1.0', END)
        # Creating terminal text
        self.gui.terminal.insert(INSERT, "=============================================================================================================\n")
        self.gui.terminal.insert(INSERT, "                                                                                            Eva Simulator for EvaML\n")
        self.gui.terminal.insert(INSERT, "                                                                         Version 2.0 - UFF / MidiaCom / CICESE - [2024]\n")
        self.gui.terminal.insert(INSERT, "=============================================================================================================")



    # WoZ light functions
    def woz_light_blue(self, s):
        self.client.publish(self.topic_base + "/light", "BLUE|ON")
    def woz_light_green(self, s):
        self.client.publish(self.topic_base + "/light", "GREEN|ON")
    def woz_light_black(self, s):
        self.client.publish(self.topic_base + "/light", "BLACK|OFF")
    def woz_light_pink(self, s):
        self.client.publish(self.topic_base + "/light", "PINK|ON")
    def woz_light_red(self, s):
        self.client.publish(self.topic_base + "/light", "RED|ON")
    def woz_light_yellow(self, s):
        self.client.publish(self.topic_base + "/light", "YELLOW|ON")
    def woz_light_white(self, s):
        self.client.publish(self.topic_base + "/light", "WHITE|ON")



    # WoZ expressions functions
    def woz_expression_angry(self, s):
        self.client.publish(self.topic_base + "/evaEmotion", "ANGRY")
    def woz_expression_fear(self, s):
        self.client.publish(self.topic_base + "/evaEmotion", "FEAR")
    def woz_expression_happy(self, s):
        self.client.publish(self.topic_base + "/evaEmotion", "HAPPY")
    def woz_expression_neutral(self, s):
        self.client.publish(self.topic_base + "/evaEmotion", "NEUTRAL")
    def woz_expression_sad(self, s):
        self.client.publish(self.topic_base + "/evaEmotion", "SAD")
    def woz_expression_surprise(self, s):
        self.client.publish(self.topic_base + "/evaEmotion", "SURPRISE")
    def woz_expression_disgust(self, s):
        self.client.publish(self.topic_base + "/evaEmotion", "DISGUST")
    def woz_expression_inlove(self, s):
        self.client.publish(self.topic_base + "/evaEmotion", "INLOVE")


    # WoZ led functions
    def woz_led_stop(self, s):
        self.client.publish(self.topic_base + '/log', "Leds Animation: " + "STOP") 
        self.client.publish(self.topic_base + "/leds", "STOP")
    def woz_led_angry(self):
        self.client.publish(self.topic_base + "/leds", "STOP")
        self.client.publish(self.topic_base + "/leds", "ANGRY")
    def woz_led_sad(self, s):
        self.client.publish(self.topic_base + "/leds", "STOP")
        self.client.publish(self.topic_base + "/leds", "SAD")
    def woz_led_angry2(self, s):
        self.client.publish(self.topic_base + "/leds", "STOP")
        self.client.publish(self.topic_base + "/leds", "ANGRY2")
    def woz_led_happy(self, s):
        self.client.publish(self.topic_base + "/leds", "STOP")
        self.client.publish(self.topic_base + "/leds", "HAPPY")
    def woz_led_listen(self, s):
        self.client.publish(self.topic_base + "/leds", "STOP")
        self.client.publish(self.topic_base + "/leds", "LISTEN")
    def woz_led_rainbow(self, s):
        self.client.publish(self.topic_base + "/leds", "STOP")
        self.client.publish(self.topic_base + "/leds", "RAINBOW")
    def woz_led_speak(self, s):
        self.client.publish(self.topic_base + "/leds", "STOP")
        self.client.publish(self.topic_base + "/leds", "SPEAK")
    def woz_led_surprise(self, s):
        self.client.publish(self.topic_base + "/leds", "STOP")
        self.client.publish(self.topic_base + "/leds", "SURPRISE")
    def woz_led_white(self, s):
        self.client.publish(self.topic_base + "/leds", "STOP")
        self.client.publish(self.topic_base + "/leds", "WHITE")


    # WoZ head motion functions
    def woz_head_motion_yes(self, s):
        self.client.publish(self.topic_base + "/motion/head", "2YES")
    def woz_head_motion_no(self, s):
        self.client.publish(self.topic_base + "/motion/head", "2NO")
    def woz_head_motion_center(self, s):
        self.client.publish(self.topic_base + "/motion/head", "CENTER")
    def woz_head_motion_left(self, s):
        self.client.publish(self.topic_base + "/motion/head", "LEFT")
    def woz_head_motion_right(self, s):
        self.client.publish(self.topic_base + "/motion/head", "RIGHT")
    def woz_head_motion_up(self, s):
        self.client.publish(self.topic_base + "/motion/head", "UP")
    def woz_head_motion_down(self, s):
        self.client.publish(self.topic_base + "/motion/head", "DOWN")
    def woz_head_motion_2left(self, s):
        self.client.publish(self.topic_base + "/motion/head", "2LEFT")
    def woz_head_motion_2right(self, s):
        self.client.publish(self.topic_base + "/motion/head", "2RIGHT")
    def woz_head_motion_2up(self, s):
        self.client.publish(self.topic_base + "/motion/head", "2UP")
    def woz_head_motion_2down(self, s):
        self.client.publish(self.topic_base + "/motion/head", "2DOWN")
    def woz_head_motion_up_left(self, s):
        self.client.publish(self.topic_base + "/motion/head", "UP_LEFT")
    def woz_head_motion_up_right(self, s):
        self.client.publish(self.topic_base + "/motion/head", "UP_RIGHT")
    def woz_head_motion_down_left(self, s):
        self.client.publish(self.topic_base + "/motion/head", "DOWN_LEFT")
    def woz_head_motion_down_right(self, s):
        self.client.publish(self.topic_base + "/motion/head", "DOWN_RIGHT")

    # WoZ arms motion functions
    def woz_arm_left_motion_up(self, s):
        self.client.publish(self.topic_base + "/motion/arm/left", "UP")
    def woz_arm_right_motion_up(self, s):
        self.client.publish(self.topic_base + "/motion/arm/right", "UP")
    def woz_arm_left_motion_down(self, s):
        self.client.publish(self.topic_base + "/motion/arm/left", "DOWN")
    def woz_arm_right_motion_down(self, s):
        self.client.publish(self.topic_base + "/motion/arm/right", "DOWN")
    def woz_arm_left_motion_pos_0(self, s):
        self.client.publish(self.topic_base + "/motion/arm/left", "POSITION 0")
    def woz_arm_right_motion_pos_0(self, s):
        self.client.publish(self.topic_base + "/motion/arm/right", "POSITION 0")
    def woz_arm_left_motion_pos_1(self, s):
        self.client.publish(self.topic_base + "/motion/arm/left", "POSITION 1")
    def woz_arm_right_motion_pos_1(self, s):
        self.client.publish(self.topic_base + "/motion/arm/right", "POSITION 1")
    def woz_arm_left_motion_pos_2(self, s):
        self.client.publish(self.topic_base + "/motion/arm/left", "POSITION 2")
    def woz_arm_right_motion_pos_2(self, s):
        self.client.publish(self.topic_base + "/motion/arm/right", "POSITION 2")
    def woz_arm_left_motion_pos_3(self, s):
        self.client.publish(self.topic_base + "/motion/arm/left", "POSITION 3")
    def woz_arm_right_motion_pos_3(self, s):
        self.client.publish(self.topic_base + "/motion/arm/right", "POSITION 3")
    def woz_arm_left_motion_shake(self, s):
        self.client.publish(self.topic_base + "/motion/arm/left", "SHAKE2")
    def woz_arm_right_motion_shake(self, s):
        self.client.publish(self.topic_base + "/motion/arm/right", "SHAKE2")


    # TTS function
    def woz_tts(self, s):
        self.client.publish(self.topic_base + "/log", "EVA will try to speak a text: " + self.gui.msg_tts_text.get('1.0','end').strip())
        voice_option = self.gui.Lb_voices.get(ANCHOR)
        print(voice_option + "|" + self.gui.msg_tts_text.get('1.0','end').strip())
        self.client.publish(self.topic_base + "/talk", voice_option + "|" + self.gui.msg_tts_text.get('1.0','end'))



    # Led "animations"
    def ledAnimation(self, animation):
        if self.RUNNING_MODE == "EVA_ROBOT":
            self.client.publish(self.topic_base + "/leds", "STOP")
            self.client.publish(self.topic_base + "/leds", animation)
        if animation == "STOP":
            self.evaMatrix("grey")
        elif animation == "LISTEN":
            self.evaMatrix("green")
        elif animation == "SPEAK":
            self.evaMatrix("blue")
        elif animation == "ANGRY" or animation == "ANGRY2":
            self.evaMatrix("red")
        elif animation == "HAPPY":
            self.evaMatrix("green")
        elif animation == "SAD":
            self.evaMatrix("blue")
        elif animation == "SURPRISE":
            self.evaMatrix("yellow")
        elif animation == "WHITE":
            self.evaMatrix("white")
        elif animation == "RAINBOW":
            self.evaMatrix("white")
            print("Falta gerar a imagem do RAINBOW para os leds do EvaSIM")
        else: print("A wrong led animation was selected.")


    # Set the Eva emotion
    def evaEmotion(self, expression):
        if expression == "NEUTRAL":
            self.gui.canvas.create_image(156, 161, image = self.im_eyes_neutral)
        elif expression == "ANGRY":
            self.gui.canvas.create_image(156, 161, image = self.im_eyes_angry)
        elif expression == "HAPPY":
            self.gui.canvas.create_image(156, 161, image = self.im_eyes_happy)
        elif expression == "SAD":
            self.gui.canvas.create_image(156, 161, image = self.im_eyes_sad)
        elif expression == "FEAR":
            self.gui.canvas.create_image(156, 161, image = self.im_eyes_fear)
        elif expression == "SURPRISE":
            self.gui.canvas.create_image(156, 161, image = self.im_eyes_surprise)
        elif expression == "DISGUST":
            self.gui.canvas.create_image(156, 161, image = self.im_eyes_disgust)
        elif expression == "INLOVE":
            self.gui.canvas.create_image(156, 161, image = self.im_eyes_inlove)
        elif expression == "POWER_ON": 
            self.gui.canvas.create_image(156, 161, image = self.im_eyes_on)
        else: 
            print("A wrong expression was selected.")
        if self.RUNNING_MODE == "SIMULATOR":
            time.sleep(1) # apenas um tempo simbólico para o simulador


    # Set the Eva matrix
    def evaMatrix(self, color):
        if color == "blue":
            self.gui.canvas.create_image(155, 349, image = self.im_matrix_blue)
        elif color == "red":
            self.gui.canvas.create_image(155, 349, image = self.im_matrix_red)
        elif color == "yellow":
            self.gui.canvas.create_image(155, 349, image = self.im_matrix_yellow)
        elif color == "green":
            self.gui.canvas.create_image(155, 349, image = self.im_matrix_green)
        elif color == "white":
            self.gui.canvas.create_image(155, 349, image = self.im_matrix_white)
        elif color == "grey": # somente para representar a luz da matrix apagada
            self.gui.canvas.create_image(155, 349, image = self.im_matrix_grey)
        else : 
            print("A wrong color to matrix was selected.")


    # Set the image of light (color and state)
    def light(self, color, state):
        color_map = {"WHITE":"#ffffff", "BLACK":"#000000", "RED":"#ff0000", "PINK":"#e6007e", "GREEN":"#00ff00", "YELLOW":"#ffff00", "BLUE":"#0000ff"}
        if color_map.get(color) != None:
            color = color_map.get(color)
        if state == "ON":
            self.gui.canvas.create_oval(300, 205, 377, 285, fill = color, outline = color )
            self.gui.canvas.create_image(340, 285, image = self.gui.bulb_image) # redesenha a lampada
        else:
            self.gui.canvas.create_oval(300, 205, 377, 285, fill = "#000000", outline = "#000000" ) # cor preta indica light off
            self.gui.canvas.create_image(340, 285, image = self.gui.bulb_image) # redesenha a lampada



    # Virtual machine functions
    # Execute the commands
    def exec_comando(self, node):
        global img_neutral, img_happy, img_angry, img_sad, img_surprise
        
        if node.tag == "voice":
            self.gui.terminal.insert(INSERT, "\nSTATE: Selected Voice => " + node.attrib["tone"])
            self.gui.terminal.see(tkinter.END)
            self.gui.terminal.insert(INSERT, "\nTIP: If the <talk> command doesn't speak some text, try emptying the audio_cache_files folder", "tip")
            if self.RUNNING_MODE == "EVA_ROBOT":
                self.client.publish(self.topic_base + "/log", "Using the voice: " + node.attrib["tone"]) # 
    
    
        if node.tag == "motion": # Movement of the head and arms
            if node.get("left-arm") != None: # Move the left arm
                self.gui.terminal.insert(INSERT, "\nSTATE: Moving the left arm! Movement type => " + node.attrib["left-arm"], "motion")
                self.gui.terminal.see(tkinter.END)
            if node.get("right-arm") != None: # Move the right arm
                self.gui.terminal.insert(INSERT, "\nSTATE: Moving the right arm! Movement type => " + node.attrib["right-arm"], "motion")
                self.gui.terminal.see(tkinter.END)
            if node.get("head") != None: # Move head with the new format (<head> element)
                    self.gui.terminal.insert(INSERT, "\nSTATE: Moving the head! Movement type => " + node.attrib["head"], "motion")
                    self.gui.terminal.see(tkinter.END)
            else: # Check if the old version was used
                if node.get("type") != None: # Maintaining compatibility with the old version of the motion element
                    self.gui.terminal.insert(INSERT, "\nSTATE: Moving the head! Movement type => " + node.attrib["type"], "motion")
                    self.gui.terminal.see(tkinter.END)
            print("Moving the head and/or the arms.")
            if self.RUNNING_MODE == "EVA_ROBOT":
                if node.get("left-arm") != None: # Move the left arm
                    self.client.publish(self.topic_base + "/motion/arm/left", node.attrib["left-arm"]); # comando para o robô físico
                if node.get("right-arm") != None:  # Move the right arm
                    self.client.publish(self.topic_base + "/motion/arm/right", node.attrib["right-arm"]); # comando para o robô físico
                if node.get("head") != None: # Move head with the new format (<head> element)
                        self.client.publish(self.topic_base + "/motion/head", node.attrib["head"]); # Command for the physical robot
                        time.sleep(0.2) # This pause is necessary for arm commands to be received via the serial port
                else: # Check if the old version was used
                    if node.get("type") != None: # Maintaining compatibility with the old version of the motion element    
                        self.client.publish(self.topic_base + "/motion/head", node.attrib["type"]); # Command for the physical robot
                        time.sleep(0.2) # This pause is necessary for arm commands to be received via the serial port
            else:
                time.sleep(0.1) # A symbolic time. In the robot, the movement does not block the script and takes different times
    
    
        elif node.tag == "light":
            lightEffect = "ON"
            state = node.attrib["state"]
            # Process light Effects settings
            if self.root.find("settings").find("lightEffects") != None:
                if self.root.find("settings").find("lightEffects").attrib["mode"] == "OFF":
                    lightEffect = "OFF"
            
            # Following case, if the state is off, and may not have a color attribute defined
            if state == "OFF":
                color = "BLACK"
                if lightEffect == "OFF":
                    message_state = "\nSTATE: Light Effects DISABLED."
                else:
                    message_state = "\nSTATE: Turnning off the light."
                self.gui.terminal.insert(INSERT, message_state)
                self.gui.terminal.see(tkinter.END)
            else:
                color = node.attrib["color"]
                if lightEffect == "OFF":
                    message_state = "\nSTATE: Light Effects DISABLED."
                    state = "OFF"
                else:
                    message_state = "\nSTATE: Turnning on the light. Color = " + color + "."
                self.gui.terminal.insert(INSERT, message_state)
                self.gui.terminal.see(tkinter.END) # Autoscrolling
            self.light(color , state)
    
            if self.RUNNING_MODE == "EVA_ROBOT":
                self.client.publish(self.topic_base + "/light", color + "|" + state); # Command for the physical robot
            else:
                time.sleep(0.1) # Emulates real bulb response time
    
    
        elif node.tag == "wait":
            duration = node.attrib["duration"]
            self.gui.terminal.insert(INSERT, "\nSTATE: Pausing. Duration = " + duration + " ms")
            self.gui.terminal.see(tkinter.END)
            time.sleep(int(duration)/1000) # Convert to seconds
    
    
        elif node.tag == "led":
            # Selection of the execution mode is done within the ledAnimation() function
            self.ledAnimation(node.attrib["animation"])
            self.gui.terminal.insert(INSERT, "\nSTATE: Matrix Leds. Animation = " + node.attrib["animation"])
            self.gui.terminal.see(tkinter.END)
            
    
        elif node.tag == "mqtt":
            mqtt_topic = node.attrib["topic"]
            mqtt_message = node.attrib["message"]
            if (len(mqtt_topic) or len(mqtt_message)) == 0: # erro
                self.gui.terminal.insert(INSERT, "\nError -> The topic or message attribute is empty.")
                self.gui.terminal.see(tkinter.END)
                exit(1)
            else:
                self.client.publish(mqtt_topic, mqtt_message)
                print("Publishing a MQTT message to an external device.", mqtt_topic, mqtt_message)
                self.gui.terminal.insert(INSERT, "\nSTATE: MQTT publishing. Topic = " + mqtt_topic + " and Message = " + mqtt_message + ".")
                self.gui.terminal.see(tkinter.END)
    
    
        elif node.tag == "random":
            min = node.attrib["min"]
            max = node.attrib["max"]
            # Check if min <= max
            if (int(min) > int(max)):
                self.gui.terminal.insert(INSERT, "\nError -> The 'min' attribute of the random command must be less than or equal to the 'max' attribute. Please, check your code.", "error")
                self.gui.terminal.see(tkinter.END)
                exit(1)
    
            if node.get("var") == None: # Maintains compatibility with the use of the $ variable
                self.memory.var_dolar.append([str(rnd.randint(int(min), int(max))), "<random>"])
                self.gui.terminal.insert(INSERT, "\nSTATE: Generating a random number (using the variable $): " + self.memory.var_dolar[-1][0])
                self.tab_load_mem_dollar()
                self.gui.terminal.see(tkinter.END)
                print("random command, min = " + min + ", max = " + max + ", valor = " + self.memory.var_dolar[-1][0])
            else:
                var_name = node.attrib["var"]
                self.memory.vars[var_name] = str(rnd.randint(int(min), int(max)))
                print("Eva ram => ", self.memory.vars)
                self.gui.terminal.insert(INSERT, "\nSTATE: Generating a random number (using the user variable '" + var_name + "'): " + str(self.memory.vars[var_name]))
                self.tab_load_mem_vars() # Enter data from variable memory into the var table
                self.gui.terminal.see(tkinter.END)
                print("random command USING VAR, min = " + min + ", max = " + max + ", valor = ")
    
    
        elif node.tag == "listen":
            if node.get("language") == None: # Maintains compatibility with the use of <listen> in old scripts
                # It will be used the default value defined in config.py file
                language_for_listen = config.LANG_DEFAULT_SPEECH_RECOGNITION
            else:
                language_for_listen =  node.attrib["language"]
    
            if self.RUNNING_MODE == "EVA_ROBOT": 
                self.client.publish(self.topic_base + "/log", "EVA is listening...")
                self.EVA_ROBOT_STATE = "BUSY"
                self.ledAnimation("LISTEN")
                self.client.publish(self.topic_base + "/listen", language_for_listen)
    
                while (self.EVA_ROBOT_STATE != "FREE"):
                    pass
                
                if node.get("var") == None: # Maintains compatibility with the use of the $ variable
                    self.memory.var_dolar.append([self.EVA_DOLLAR, "<listen>"])
                    self.gui.terminal.insert(INSERT, "\nSTATE: Listening (language -> " + language_for_listen + "): var = $" + ", value = " + self.memory.var_dolar[-1][0])
                    self.tab_load_mem_dollar()
                    self.gui.terminal.see(tkinter.END)
                    self.ledAnimation("STOP")
                    
                else:
                    var_name = node.attrib["var"]
                    self.memory.vars[var_name] = self.EVA_DOLLAR
                    print("Eva ram => ", self.memory.vars)
                    self.gui.terminal.insert(INSERT, "\nSTATE: Listening (language -> " + language_for_listen + "): (using the user variable '" + var_name + "'): " + self.EVA_DOLLAR)
                    self.tab_load_mem_vars() # Enter data from variable memory into the var table
                    self.gui.terminal.see(tkinter.END)
                    print("Listen command USING VAR...")
                    self.ledAnimation("STOP")
    
            else:
                self.lock_thread_pop()
                self.ledAnimation("LISTEN")
                # Pop up window closing function for the <return> key)
                def fechar_pop_ret(s): 
                    print(var.get())
                    if node.get("var") == None: # Maintains compatibility with the use of the $ variable
                        self.memory.var_dolar.append([var.get(), "<listen>"])
                        self.gui.terminal.insert(INSERT, "\nSTATE: Listening (language -> " + language_for_listen + "): var = $" + ", value = " + self.memory.var_dolar[-1][0])
                        self.tab_load_mem_dollar()
                        self.gui.terminal.see(tkinter.END)
                        pop.destroy()
                        self.unlock_thread_pop() # Reactivate the script processing thread
                    else:
                        var_name = node.attrib["var"]
                        self.memory.vars[var_name] = var.get()
                        print("Eva ram => ", self.memory.vars)
                        self.gui.terminal.insert(INSERT, "\nSTATE: Listening (language -> " + language_for_listen + "): (using the user variable '" + var_name + "'): " + var.get())
                        self.tab_load_mem_vars() # Enter data from variable memory into the var table
                        self.gui.terminal.see(tkinter.END)
                        print("Listen command USING VAR...")
                        pop.destroy()
                        self.unlock_thread_pop() # Reactivate the script processing thread
                
                # Pop up window closing function for OK button
                def fechar_pop_bt(): 
                    print(var.get())
                    if node.get("var") == None: # Maintains compatibility with the use of the $ variable
                        self.memory.var_dolar.append([var.get(), "<listen>"])
                        self.gui.terminal.insert(INSERT, "\nSTATE: Listening (language -> " + language_for_listen + ">: var = $" + ", value = " + self.memory.var_dolar[-1][0])
                        self.tab_load_mem_dollar()
                        self.gui.terminal.see(tkinter.END)
                        pop.destroy()
                        self.unlock_thread_pop() # Reactivate the script processing thread
                    else:
                        var_name = node.attrib["var"]
                        self.memory.vars[var_name] = var.get()
                        print("Eva ram => ", self.memory.vars)
                        self.gui.terminal.insert(INSERT, "\nSTATE: Listening (language -> " + language_for_listen + "): (using the user variable '" + var_name + "'): " + var.get())
                        self.tab_load_mem_vars() # Enter data from variable memory into the var table
                        self.gui.terminal.see(tkinter.END)
                        print("Listen command USING VAR...")
                        pop.destroy()
                        self.unlock_thread_pop() # Reactivate the script processing thread
                    
                # Window (self.gui) creation
                var = StringVar()
                pop = Toplevel(self.gui)
                pop.title("Listen Command")
                # Disable the maximize and close buttons
                pop.resizable(False, False)
                pop.protocol("WM_DELETE_WINDOW", False)
                w = 450
                h = 150
                ws = self.gui.winfo_screenwidth()
                hs = self.gui.winfo_screenheight()
                x = (ws/2) - (w/2)
                y = (hs/2) - (h/2)  
                pop.geometry('%dx%d+%d+%d' % (w, h, x, y))
                label = Label(pop, text="Eva is listening (language -> " + language_for_listen + ")... Please, enter your answer!", font = ('Arial', 10))
                label.pack(pady=20)
                E1 = Entry(pop, textvariable = var, font = ('Arial', 10))
                E1.bind("<Return>", fechar_pop_ret)
                E1.pack()
                Button(pop, text="    OK    ", font = self.font1, command=fechar_pop_bt).pack(pady=20)
                # Wait for release, waiting for the user's response
                while self.thread_pop_pause: 
                    time.sleep(0.5)
                self.ledAnimation("STOP")
    
    
        elif node.tag == "talk": # Blocking function
            if node.text == None: # There is no text to speech
                print("There is no text to speech in the element <talk>.")
                self.gui.terminal.insert(INSERT, "\nError -> There is no text to speech in the element <talk>. Please, check your code.", "error")
                self.gui.terminal.see(tkinter.END)
                exit(1)
    
            texto = node.text
            # Replace variables throughout the text. variables must exist in memory
            if "#" in texto:
                # Checks if the robot's memory (vars) is empty
                if self.memory.vars == {}:
                    self.gui.terminal.insert(INSERT, "\nError -> No variables have been defined. Please, check your code.", "error")
                    self.gui.terminal.see(tkinter.END)
                    exit(1)
    
                var_list = re.findall(r'\#[a-zA-Z]+[0-9]*', texto) # Generate list of occurrences of vars (#...)
                for v in var_list:
                    if v[1:] in self.memory.vars:
                        texto = texto.replace(v, str(self.memory.vars[v[1:]]))
                    else:
                        # If the variable does not exist in the robot's memory, it disself.plays an error message
                        print("================================")
                        error_string = "\nError -> The variable #" + v[1:] + " has not been declared. Please, check your code."
                        self.gui.terminal.insert(INSERT, error_string, "error")
                        self.gui.terminal.see(tkinter.END)
                        exit(1)
    
            # This part replaces the $, or the $-1 or the $1 in the text
            if "$" in texto: # Check if there is $ in the text
                # Checks if var_dollar has any value in the robot's memory
                if (len(self.memory.var_dolar)) == 0:
                    self.gui.terminal.insert(INSERT, "\nError-> The variable $ has no value. Please, check your code.", "error")
                    self.gui.terminal.see(tkinter.END)
                    exit(1)
                else: # Find the patterns $ $n or $-n in the string and replace with the corresponding values
                    dollars_list = re.findall(r'\$[-0-9]*', texto) # Find dollar patterns and return a list of occurrences
                    dollars_list = sorted(dollars_list, key=len, reverse=True) # Sort the list in descending order of length (of the element)
                    for var_dollar in dollars_list:
                        if len(var_dollar) == 1: # Is the dollar ($)
                            texto = texto.replace(var_dollar, self.memory.var_dolar[-1][0])
                        else: # May be of type $n or $-n
                            if "-" in var_dollar: # $-n type
                                indice = int(var_dollar[2:]) # Var dollar is of type $-n. then just take n and convert it to int
                                texto = texto.replace(var_dollar, self.memory.var_dolar[-(indice + 1)][0]) 
                            else: # tipo $n
                                indice = int(var_dollar[1:]) # Var dollar is of type $n. then just take n and convert it to int
                                texto = texto.replace(var_dollar, self.memory.var_dolar[(indice - 1)][0])
                
            # This part implements the random text generated by using the / character
            texto = texto.split(sep="/") # Text becomes a list with the number of sentences divided by character. /
            print(texto)
            ind_random = rnd.randint(0, len(texto)-1)
            self.gui.terminal.insert(INSERT, '\nSTATE: Speaking: "' + texto[ind_random] + '"')
            self.gui.terminal.see(tkinter.END)
    
            if self.RUNNING_MODE == "EVA_ROBOT":
                self.client.publish(self.topic_base + "/log", "EVA will try to speak a text: " + texto[ind_random])
                self.ledAnimation("SPEAK")
                self.EVA_ROBOT_STATE = "BUSY" # Speech is a blocking function. the robot is busy
                if node.get("tone") == None: # Usuario não selecionou a voz no talk. A opção global será utilizada
                    self.client.publish(self.topic_base + "/talk", self.root.find("settings")[0].attrib["tone"] + "|" + texto[ind_random])
                else:
                    self.client.publish(self.topic_base + "/talk", node.attrib["tone"] + "|" + texto[ind_random]) # voz selecionado em talk será utilizada
                while(self.EVA_ROBOT_STATE != "FREE"):
                    pass
                self.ledAnimation("STOP")
            else:
                if not TTS_IBM_WATSON: # without IBM-Watson
                    self.gui.option_add('*Dialog.msg.width', 30)
                    self.gui.option_add('*Dialog.msg.font', 'Arial 14')
                    self.lock_thread_pop()
                    messagebox.showinfo("TTS - Message Box - EVA is speaking!", texto[ind_random])
                    self.unlock_thread_pop() # Reactivate the script processing thread
    
                elif TTS_IBM_WATSON:
                    # Using IBM Watson ################################
                    # Assume the default UTF-8 (Generates the hashing of the audio file)
                    # Also, uses the voice tone attribute in file hashing
                    if node.get("tone") == None: # Usuario não selecionou a voz no talk. A opção global será utilizada
                        tone_voice = self.root.find("settings")[0].attrib["tone"]
                    else:
                        tone_voice = node.attrib["tone"]
    
                    hash_object = hashlib.md5(texto[ind_random].encode())
                    file_name = "_audio_"  + tone_voice + hash_object.hexdigest()
    
                    # Checks if the speech audio already exists in the folder
                    if not (os.path.isfile("audio_cache_files/" + file_name + self.audio_ext)): # If it doesn't exist, call Watson
                        audio_file_is_ok = False
                        while(not audio_file_is_ok):
                            # Eva TTS functions
                            with open("audio_cache_files/" + file_name + self.audio_ext, 'wb') as audio_file:
                                try:
                                    res = self.tts.synthesize(texto[ind_random], accept = self.ibm_audio_ext, voice = tone_voice).get_result()
                                    audio_file.write(res.content)
                                    self.playsound("audio_cache_files/" + file_name + self.audio_ext, block = True) # self.play the audio of the speech
                                except:
                                    print("Voice exception")
                                    self.gui.terminal.insert(INSERT, "\nError when trying to select voice tone, please verify the tone atribute.\n", "error")
                                    self.gui.terminal.see(tkinter.END)
                                    exit(1)
                            file_size = os.path.getsize("audio_cache_files/" + file_name + self.audio_ext)
                            if file_size == 0: # Corrupted file
                                print("#### Corrupted file.. (It's necessary to use the same implementation like in tts-module in EVA robot!)")
                                os.remove("audio_cache_files/" + file_name + self.audio_ext)
                            else:
                                audio_file_is_ok = True
                    else:
                        self.playsound("audio_cache_files/" + file_name + self.audio_ext, block = True) # self.play the audio of the speech
                ##############################
    
    
        elif node.tag == "evaEmotion":
            emotion = node.attrib["emotion"]
            if self.RUNNING_MODE == "EVA_ROBOT":
                self.client.publish(self.topic_base + "/evaEmotion", emotion) # Command for physical EVA
            self.gui.terminal.insert(INSERT, "\nSTATE: Expressing an emotion => " + emotion)
            self.gui.terminal.see(tkinter.END)
            self.evaEmotion(emotion)
    
    
        elif node.tag == "audio":
            sound_file =  node.attrib["source"]
            block = False # Audio self.play does not block script execution
            if node.attrib["block"] == "TRUE":
                block = True
            message_audio = '\nSTATE: self.playing a sound: "' + "audio_files/" + sound_file + ".wav" + '", block=' + str(block)
    
            # Process Audio Effects settings
            if self.root.find("settings").find("audioEffects") != None:
                if self.root.find("settings").find("audioEffects").attrib["mode"] == "OFF":
                    # Mode off implies the use of MUTED-SOUND file 
                    sound_file = "my_sounds/MUTED-SOUND.wav"
                    message_audio = "\nSTATE: Audio Effects DISABLED."
    
            self.gui.terminal.insert(INSERT, message_audio)
            self.gui.terminal.see(tkinter.END)
    
            try:
                if block == True:
                    if self.RUNNING_MODE == "EVA_ROBOT":
                        self.client.publish(self.topic_base + "/log", "EVA will self.play a sound in blocking mode.")
                        self.EVA_ROBOT_STATE = "BUSY"
                        self.client.publish(self.topic_base + "/audio", sound_file + "|" + "TRUE")
                        while (self.EVA_ROBOT_STATE != "FREE"):
                            pass
                    else:
                        print(sound_file)
                        self.playsound("audio_files/" + sound_file + ".wav", block = block)
    
                else: # Block = False
                    if self.RUNNING_MODE == "EVA_ROBOT":
                        self.client.publish(self.topic_base + "/log", "EVA will self.play a sound in no-blocking mode.")
                        self.client.publish(self.topic_base + "/audio", sound_file + "|" + "FALSE")
                    else:
                        self.playsound("audio_files/" + sound_file + ".wav", block = block) 
            except Exception as e:
                # Handle an exception. I didn't find any exceptions in the library documentation
                error_string = "\nError -> " + str(e) + "."
                self.gui.terminal.insert(INSERT, error_string, "error")
                self.gui.terminal.see(tkinter.END)
                exit(1)
    
    
    ##########################################################
        elif node.tag == "case": 
            global valor
            self.memory.reg_case = 0 # Clear the case flag
            valor = node.attrib["value"]
            valor = valor.lower() # Comparisons are not case sensitive
            # Handles comparison types and operators
            # Case 1 (op = "exact")
            if node.attrib['op'] == "exact": # Exact é sempre uma comparação de STRINGS
                # Case in which a user variable was defined for a command: QRcode, random, userEmotion or userId
                if node.attrib['var'] != "$":
                    # It remains to check whether the variable exists in the robot's memory
                    # self.memory.vars[st_var_value[1:]
                    print("value: ", valor, type(valor), node.attrib['var'], self.memory.vars[node.attrib['var']])
                    if valor[0] == "#": # é uma referência a uma variável
                        valor = valor[1:] # remove o # da referência
                    if valor == str(self.memory.vars[node.attrib['var']]).lower(): # Comparação de STRINGS
                        print("case = true")
                        self.memory.reg_case = 1 # Turn on the reg case indicating that the comparison result was true
    
                # Checks if var_dollar memory has any value
                elif (len(self.memory.var_dolar)) == 0:
                    self.gui.terminal.insert(INSERT, "\nError -> The variable $ has no value. Please, check your code.", "error")
                    self.gui.terminal.see(tkinter.END)
                    exit(1)  
    
                
                elif valor == self.memory.var_dolar[-1][0].lower():
                    # Compare value with the top of the stack of the var_dollar variable
                    print("value: ", valor, type(valor))
                    print("case = true")
                    self.memory.reg_case = 1 # Turn on the reg_case indicating that the comparison result was true
            
            # Case 2 (op = "contain")
            elif node.attrib['op'] == "contain":      
                # Checa se a comparação é com o dollar
                if "$" == node.attrib['var'][0]:
                    if (len(self.memory.var_dolar)) == 0: # Checks if var_dollar memory has any value
                        self.gui.terminal.insert(INSERT, "\nError -> The variable $ has no value. Please, check your code.", "error")
                        self.gui.terminal.see(tkinter.END)
                        exit(1)  
                    else:
                        # Checks if the string in value is contained in $
                        print("value: ", valor, type(valor))
                        if valor in self.memory.var_dolar[-1][0].lower(): 
                            print("case = true")
                            self.memory.reg_case = 1 # Turn on the reg case indicating that the comparison result was true
                # se não é com dollar então é com uma var do usuário
                elif node.attrib['var'] in self.memory.vars: # verifica se a variável de usuário existe na memória
                    if "#" == valor[0]:
                        valor = valor[1:]
                        if str(self.memory.vars[valor]).lower() in str(self.memory.vars[node.attrib['var']]).lower():
                            print("case = true")
                            self.memory.reg_case = 1 # Turn on the reg case indicating that the comparison result was true
                    else:
                        if valor in self.memory.vars[node.attrib['var']]:
                            print("case = true")
                            self.memory.reg_case = 1 # Turn on the reg case indicating that the comparison result was true
                else:
                    self.gui.terminal.insert(INSERT, "\nError -> The variable '" + node.attrib['var'] + "' does no exist. Please, check your code.", "error")
                    self.gui.terminal.see(tkinter.END)
    ##########################################################
    
    
            # case 3 (MATHEMATICAL COMPARISON)
            else:
                # Function to obtain an operand from $, n, #n, or value
                def get_op(st_var_value):
                    # Is a constant?
                    if st_var_value.isnumeric():
                        return int(st_var_value)
    
                    # Is $?
                    if st_var_value == "$":
                        # Checks if var_dollar memory has any value
                        if (len(self.memory.var_dolar)) == 0:
                            self.gui.terminal.insert(INSERT, "\nError -> The variable $ has no value. Please, check your code.", "error")
                            self.gui.terminal.see(tkinter.END)
                            exit(1)
                        return int(self.memory.var_dolar[-1][0]) # Returns the value of $ converted for int
    
                    # Is a variable of type #n?
                    if "#" in st_var_value:
                        # Checks if var #... DOES NOT exist in memory
                        if (st_var_value[1:] not in self.memory.vars):
                            error_string = "\nError -> The variable #" + valor[1:] + " has not been declared. Please, check your code."
                            self.gui.terminal.insert(INSERT, error_string, "error")
                            self.gui.terminal.see(tkinter.END)
                            exit(1)
                        return int(self.memory.vars[st_var_value[1:]]) # Returns the value of #n converted for int
                    
                    # If it is not a number, nor a dollar, nor a #, then it is a variable of this type var = "x" in <switch>
                    # Checks if the variable exists in memory
                    if (st_var_value not in self.memory.vars):
                        error_string = "\nError -> The variable #" + valor[1:] + " has not been declared. Please, check your code."
                        self.gui.terminal.insert(INSERT, error_string, "error")
                        self.gui.terminal.see(tkinter.END)
                        exit(1)
                    return int(self.memory.vars[st_var_value]) # Returns the value of n converted for int
    
                # Obtains the operands to perform mathematical comparison operations
                # The restriction on not using constants in var of <switch> was guaranteed in the parser
                op1 = get_op(node.attrib['var'])
                op2 = get_op(valor)
    
                # Performs the operations ==, >, <, >=, <= and != to compare operands 1 and 2
                if node.attrib['op'] == "eq": # Equality
                    if op1 == op2: # It is needed to remove the # from the variable
                        print("case = true")
                        self.memory.reg_case = 1 # Turn on the reg_case indicating that the comparison result was true
    
                elif node.attrib['op'] == "lt": # Less than
                    if op1 < op2:
                        print("case = true")
                        self.memory.reg_case = 1 # Turn on the reg_case indicating that the comparison result was true
    
                elif node.attrib['op'] == "gt": # Greater than
                    if op1 > op2:
                        print("case = true")
                        self.memory.reg_case = 1 # Turn on the reg_case indicating that the comparison result was true
                
                elif node.attrib['op'] == "lte": # Less than or Equal
                    if op1 <= op2:
                        print("case = true")
                        self.memory.reg_case = 1 # Turn on the reg_case indicating that the comparison result was true
    
                elif node.attrib['op'] == "gte": # Greater than or Equal
                    if op1 >= op2:
                        print("case = true")
                        self.memory.reg_case = 1 # Turn on the reg_case indicating that the comparison result was true
    
                elif node.attrib['op'] == "ne": # Not equal
                    if op1 != op2:
                        print("case = true")
                        self.memory.reg_case = 1 # Turn on the reg_case indicating that the comparison result was true        
    
    
        elif node.tag == "default": # Default is always true
            print("Default = true")
            self.memory.reg_case = 1 # Turn on the reg_case indicating that the comparison result was true
    
    
        elif node.tag == "counter":
            var_name = node.attrib["var"]
            var_value = int(node.attrib["value"])
            op = node.attrib["op"]
            # Checks if the operation is different from assignment and checks if var ... DOES NOT exist in memory
            if op != "=":
                if (var_name not in self.memory.vars):
                    error_string = "\nError -> The variable " + var_name + " has not been declared. Please, check your code."
                    self.gui.terminal.insert(INSERT, error_string, "error")
                    self.gui.terminal.see(tkinter.END)
                    exit(1)
    
            if op == "=": # Perform the assignment
                self.memory.vars[var_name] = var_value
    
            if op == "+": # Perform the addition
                self.memory.vars[var_name] += var_value
    
            if op == "*": # Perform the product
                self.memory.vars[var_name] *= var_value
    
            if op == "/": # Performs the division (it was /=) but I changed it to //= (integer division)
                self.memory.vars[var_name] //= var_value
    
            if op == "%": # Calculate the module
                self.memory.vars[var_name] %= var_value
            
            print("Eva ram => ", self.memory.vars)
            self.gui.terminal.insert(INSERT, "\nSTATE: Counter: var = " + var_name + ", value = " + str(var_value) + ", op(" + op + "), result = " + str(self.memory.vars[var_name]))
            self.tab_load_mem_vars() # Enter data from variable memory into the variable table
            self.gui.terminal.see(tkinter.END)
    
    
        elif node.tag == "textEmotion":
            # Falta implementar o modo Simulador ###############
            if self.RUNNING_MODE == "EVA_ROBOT": 
                self.client.publish(self.topic_base + "/log", "EVA is analysing the text emotion...")
                self.EVA_ROBOT_STATE = "BUSY"
                self.ledAnimation("RAINBOW")
                if node.get("language") == None:
                    self.client.publish(self.topic_base + "/textEmotion", config.LANG_DEFAULT_GOOGLE_TRANSLATING + "|" + self.memory.var_dolar[-1][0])
                else:
                    self.client.publish(self.topic_base + "/textEmotion", node.attrib["language"] + "|" + self.memory.var_dolar[-1][0])
                    
    
                while (self.EVA_ROBOT_STATE != "FREE"):
                    pass
                
                if node.get("var") == None: # Maintains compatibility with the use of the $ variable
                    self.memory.var_dolar.append([self.EVA_DOLLAR, "<textEmotion>"])
                    self.gui.terminal.insert(INSERT, "\nSTATE: textEmotion: var=$" + ", value = " + self.memory.var_dolar[-1][0])
                    self.tab_load_mem_dollar()
                    self.gui.terminal.see(tkinter.END)
                    self.ledAnimation("STOP")
                else:
                    var_name = node.attrib["var"]
                    self.memory.vars[var_name] = self.EVA_DOLLAR
                    print("Eva ram => ", self.memory.vars)
                    self.gui.terminal.insert(INSERT, "\nSTATE: textEmotion (using the user variable '" + var_name + "'): " + str(self.memory.vars[var_name]))
                    self.tab_load_mem_vars() # Enter data from variable memory into the var table
                    self.gui.terminal.see(tkinter.END)
                    print("textEmotion command USING VAR...")
                self.ledAnimation("STOP")
            
            else:
            
                self.lock_thread_pop()
                self.ledAnimation("LISTEN")
                def fechar_pop(): # Pop up window closing function
                    print(var.get())
                    if node.get("var") == None: # Maintains compatibility with the use of the $ variable
                        self.memory.var_dolar.append([var.get(), "<textEmotion>"])
                        self.gui.terminal.insert(INSERT, "\nSTATE: textEmotion: var = $" + ", value = " + self.memory.var_dolar[-1][0])
                        self.tab_load_mem_dollar()
                        self.gui.terminal.see(tkinter.END)
                    else:
                        var_name = node.attrib["var"]
                        self.memory.vars[var_name] = var.get()
                        print("Eva ram => ", self.memory.vars)
                        self.gui.terminal.insert(INSERT, "\nSTATE: textEmotion (using the user variable '" + var_name + "'): " + str(self.memory.vars[var_name]))
                        self.tab_load_mem_vars() # Enter data from variable memory into the var table
                        self.gui.terminal.see(tkinter.END)
                        print("textEmotion command USING VAR...")
                    pop.destroy()
                    self.ledAnimation("STOP")
                    self.unlock_thread_pop() # Reactivate the script processing thread
    
                var = StringVar()
                var.set("NEUTRAL")
                img_neutral = PhotoImage(file = "images/img_neutral.png")
                img_happy = PhotoImage(file = "images/img_happy.png")
                img_angry = PhotoImage(file = "images/img_angry.png")
                img_sad = PhotoImage(file = "images/img_sad.png")
                img_surprise = PhotoImage(file = "images/img_surprise.png")
                img_fear = PhotoImage(file = "images/img_fear.png")
                img_disgust = PhotoImage(file = "images/img_disgust.png")
                pop = Toplevel(self.gui)
                pop.title("textEmotion Command")
                # Disable the maximize and close buttons
                pop.resizable(False, False)
                pop.protocol("WM_DELETE_WINDOW", False)
                w = 970
                h = 250
                ws = self.gui.winfo_screenwidth()
                hs = self.gui.winfo_screenheight()
                x = (ws/2) - (w/2)
                y = (hs/2) - (h/2)  
                pop.geometry('%dx%d+%d+%d' % (w, h, x, y))
                Label(pop, text="Eva is analysing the sentiment of your text. Please, choose one emotion!", font = ('Arial', 10)).place(x = 290, y = 10)
                # Images are disself.played using labels
                Label(pop, image=img_neutral).place(x = 10, y = 50)
                Label(pop, image=img_happy).place(x = 147, y = 50)
                Label(pop, image=img_angry).place(x = 284, y = 50)
                Label(pop, image=img_sad).place(x = 421, y = 50)
                Label(pop, image=img_surprise).place(x = 558, y = 50)
                Label(pop, image=img_fear).place(x = 695, y = 50)
                Label(pop, image=img_disgust).place(x = 832, y = 50)
                Radiobutton(pop, text = "Neutral", variable = var, font = self.font1, command = None, value = "NEUTRAL").place(x = 35, y = 185)
                Radiobutton(pop, text = "Happy", variable = var, font = self.font1, command = None, value = "HAPPY").place(x = 172, y = 185)
                Radiobutton(pop, text = "Angry", variable = var, font = self.font1, command = None, value = "ANGRY").place(x = 312, y = 185)
                Radiobutton(pop, text = "Sad", variable = var, font = self.font1, command = None, value = "SAD").place(x = 452, y = 185)
                Radiobutton(pop, text = "Surprise", variable = var, font = self.font1, command = None, value = "SURPRISE").place(x = 580, y = 185)
                Radiobutton(pop, text = "Fear", variable = var, font = self.font1, command = None, value = "FEAR").place(x = 725, y = 185)
                Radiobutton(pop, text = "Disgust", variable = var, font = self.font1, command = None, value = "DISGUST").place(x = 855, y = 185)
                Button(pop, text = "           OK          ", font = self.font1, command = fechar_pop).place(x = 430, y = 215)
                # Wait for release, waiting for the user's response
                while self.thread_pop_pause: 
                    time.sleep(0.5)
    
        elif node.tag == "userHandPose":
            global img_thumbsup, img_thumbsdown, img_peace, img_open, img_three
    
            if self.gui.chk_handpose_value.get() == 1:
                
                self.lock_thread_pop()
                self.ledAnimation("LISTEN")
                
                result_pose = hp.run()
    
    
                var = StringVar(value=result_pose)
    
                if node.get("var") == None: # mantém a compatibilidade com o uso da variável $
                    self.memory.var_dolar.append([var.get(), "<userHandPose>"])
                    self.gui.terminal.insert(INSERT, "\nSTATE: userHandPose : var=$" + ", value=" + self.memory.var_dolar[-1][0])
                    self.tab_load_mem_dollar()
                    self.gui.terminal.see(tkinter.END)
                else:
                    var_name = node.attrib["var"]
                    self.memory.vars[var_name] = var.get()
                    print("Eva ram => ", self.memory.vars)
                    self.gui.terminal.insert(INSERT, "\nSTATE: userHandPose : (using the user variable '" + var_name + "'): " + self.EVA_DOLLAR)
                    self.tab_load_mem_vars() # entra com os dados da memoria de variaveis na tabela de vars
                    self.gui.terminal.see(tkinter.END)
    
    
            elif self.gui.chk_handpose_value.get() == 0:    
                self.lock_thread_pop()
    
                def fechar_pop(): # função de fechamento da janela pop up
                        print(var.get())
                        if node.get("var") == None: # mantém a compatibilidade com o uso da variável $
                            self.memory.var_dolar.append([var.get(), "<userHandPose>"])
                            self.gui.terminal.insert(INSERT, "\nSTATE: userHandPose : var=$" + ", value=" + self.memory.var_dolar[-1][0])
                            self.tab_load_mem_dollar()
                            self.gui.terminal.see(tkinter.END)
                        else:
                            var_name = node.attrib["var"]
                            self.memory.vars[var_name] = var.get()
                            print("Eva ram => ", self.memory.vars)
                            self.gui.terminal.insert(INSERT, "\nSTATE: userHandPose : (using the user variable '" + var_name + "'): " + self.EVA_DOLLAR)
                            self.tab_load_mem_vars() # entra com os dados da memoria de variaveis na tabela de vars
                            self.gui.terminal.see(tkinter.END)
                            print("userHandPose command USING VAR...")
                        pop.destroy()
                        self.ledAnimation("STOP")
                        self.unlock_thread_pop() # reativa a thread de processamento do script
    
                var = StringVar()
                var.set("OPEN")
                img_thumbsup = PhotoImage(file = "images/img_thumbsup.png")
                img_thumbsdown = PhotoImage(file = "images/img_thumbsdown.png")
                img_peace = PhotoImage(file = "images/img_peace.png")
                img_open = PhotoImage(file = "images/img_open.png")
                img_three = PhotoImage(file = "images/img_three.png")
                pop = Toplevel(self.window)
                pop.title("userHandPose Command")
                # Disable the max and close buttons
                pop.resizable(False, False)
                pop.protocol("WM_DELETE_WINDOW", False)
                w = 697
                h = 250
                ws = self.gui.winfo_screenwidth()
                hs = self.gui.winfo_screenheight()
                x = (ws/2) - (w/2)
                y = (hs/2) - (h/2)  
                pop.geometry('%dx%d+%d+%d' % (w, h, x, y))
                pop.grab_set() # faz com que a janela receba todos os eventos
                Label(pop, text="Eva is analysing your hands. Please, choose one gesture!", font = ('Arial', 10)).place(x = 146, y = 10)
                # imagens são exibidas usando os lables
                Label(pop, image=img_thumbsup).place(x = 10, y = 50)
                Label(pop, image=img_thumbsdown).place(x = 147, y = 50)
                Label(pop, image=img_peace).place(x = 284, y = 50)
                Label(pop, image=img_open).place(x = 421, y = 50)
                Label(pop, image=img_three).place(x = 558, y = 50)
                Radiobutton(pop, text = "Thumbs_UP", variable = var, font = self.font1, command = None, value = "THUMBS_UP").place(x = 25, y = 185)
                Radiobutton(pop, text = "Thumbs_DOWN", variable = var, font = self.font1, command = None, value = "THUMBS_DOWN").place(x = 152, y = 185)
                Radiobutton(pop, text = "Peace", variable = var, font = self.font1, command = None, value = "PEACE").place(x = 302, y = 185)
                Radiobutton(pop, text = "Open", variable = var, font = self.font1, command = None, value = "OPEN").place(x = 442, y = 185)
                Radiobutton(pop, text = "Three", variable = var, font = self.font1, command = None, value = "THREE").place(x = 575, y = 185)
                Button(pop, text = "     OK     ", font = self.font1, command = fechar_pop).place(x = 310, y = 215)
                # espera pela liberacao, aguardando a resposta do usuario
                while self.thread_pop_pause: 
                    time.sleep(0.5)
                self.ledAnimation("STOP")
    
        elif node.tag == "userEmotion":
            # global img_neutral, img_happy, img_angry, img_sad, img_surprise, img_fear, img_desgust
            
            if self.RUNNING_MODE == "EVA_ROBOT": 
                self.client.publish(self.topic_base + "/log", "EVA is capturing the user emotion...")
                self.EVA_ROBOT_STATE = "BUSY"
                self.ledAnimation("LISTEN")
                self.client.publish(self.topic_base + "/userEmotion", " ")
    
                while (self.EVA_ROBOT_STATE != "FREE"):
                    pass
                
                if node.get("var") == None: # Maintains compatibility with the use of the $ variable
                    self.memory.var_dolar.append([self.EVA_DOLLAR, "<listen>"])
                    self.gui.terminal.insert(INSERT, "\nSTATE: userEmotion: var=$" + ", value = " + self.memory.var_dolar[-1][0])
                    self.tab_load_mem_dollar()
                    self.gui.terminal.see(tkinter.END)
                    self.ledAnimation("STOP")
                else:
                    var_name = node.attrib["var"]
                    self.memory.vars[var_name] = self.EVA_DOLLAR
                    print("Eva ram => ", self.memory.vars)
                    self.gui.terminal.insert(INSERT, "\nSTATE: userEmotion (using the user variable '" + var_name + "'): " + str(self.memory.vars[var_name]))
                    self.tab_load_mem_vars() # Enter data from variable memory into the variable table
                    self.gui.terminal.see(tkinter.END)
                    print("userEmotion command USING VAR...")
                    self.ledAnimation("STOP")
            else:
            
                ###############
                self.lock_thread_pop()
                self.ledAnimation("LISTEN")
    
                if self.gui.chk_emotion_value.get() == 1:
                    result_emotion = ue.run()
    
                    var = StringVar(value=result_emotion)
                    if node.get("var") == None: # mantém a compatibilidade com o uso da variável $
                        self.memory.var_dolar.append([var.get(), "<userEmotion>"])
                        self.gui.terminal.insert(INSERT, "\nSTATE: userEmotion : var=$" + ", value=" + self.memory.var_dolar[-1][0])
                        self.tab_load_mem_dollar()
                        self.gui.terminal.see(tkinter.END)
                    else:
                        var_name = node.attrib["var"]
                        self.memory.vars[var_name] = var.get()
                        print("Eva ram => ", self.memory.vars)
                        self.gui.terminal.insert(INSERT, "\nSTATE: userEmotion : (using the user variable '" + var_name + "'): " + self.EVA_DOLLAR)
                        self.tab_load_mem_vars() # entra com os dados da memoria de variaveis na tabela de vars
                        self.gui.terminal.see(tkinter.END)
               
                elif self.gui.chk_emotion_value.get() == 0:
                    def fechar_pop(): # função de fechamento da janela pop up
                        print(var.get())
                        if node.get("var") == None: # mantém a compatibilidade com o uso da variável $
                            self.memory.var_dolar.append([var.get(), "<userEmotion>"])
                            self.gui.terminal.insert(INSERT, "\nSTATE: userEmotion : var=$" + ", value=" + self.memory.var_dolar[-1][0])
                            self.tab_load_mem_dollar()
                            self.gui.terminal.see(tkinter.END)
                        else:
                            var_name = node.attrib["var"]
                            self.memory.vars[var_name] = var.get()
                            print("Eva ram => ", self.memory.vars)
                            self.gui.terminal.insert(INSERT, "\nSTATE: userEmotion : (using the user variable '" + var_name + "'): " + self.EVA_DOLLAR)
                            self.tab_load_mem_vars() # entra com os dados da memoria de variaveis na tabela de vars
                            self.gui.terminal.see(tkinter.END)
                            print("userEmotion command USING VAR...")
                        pop.destroy()
                        self.ledAnimation("STOP")
                        self.unlock_thread_pop() # reativa a thread de processamento do script
    
                    var = StringVar()
                    var.set("NEUTRAL")
                    img_neutral = PhotoImage(file = "images/img_neutral.png")
                    img_happy = PhotoImage(file = "images/img_happy.png")
                    img_angry = PhotoImage(file = "images/img_angry.png")
                    img_sad = PhotoImage(file = "images/img_sad.png")
                    img_surprise = PhotoImage(file = "images/img_surprise.png")
                    img_fear = PhotoImage(file = "images/img_fear.png")
                    img_disgust = PhotoImage(file = "images/img_disgust.png")
                    pop = Toplevel(self.gui)
                    pop.title("userEmotion Command")
                    # Disable the max and close buttons
                    pop.resizable(False, False)
                    pop.protocol("WM_DELETE_WINDOW", False)
                    w = 973
                    h = 250
                    ws = self.gui.winfo_screenwidth()
                    hs = self.gui.winfo_screenheight()
                    x = (ws/2) - (w/2)
                    y = (hs/2) - (h/2)  
                    pop.geometry('%dx%d+%d+%d' % (w, h, x, y))
                    # pop.grab_set() # faz com que a janela receba todos os eventos
                    Label(pop, text="Eva is analysing your face expression. Please, choose one emotion!", font = ('Arial', 10)).place(x = 246, y = 10)
                    # imagens são exibidas usando os lables
                    Label(pop, image=img_neutral).place(x = 10, y = 50)
                    Label(pop, image=img_happy).place(x = 147, y = 50)
                    Label(pop, image=img_angry).place(x = 284, y = 50)
                    Label(pop, image=img_sad).place(x = 421, y = 50)
                    Label(pop, image=img_surprise).place(x = 558, y = 50)
                    Label(pop, image=img_fear).place(x = 695, y = 50)
                    Label(pop, image=img_disgust).place(x = 832, y = 50)
                    Radiobutton(pop, text = "Neutral", variable = var, font = self.font1, command = None, value = "NEUTRAL").place(x = 35, y = 185)
                    Radiobutton(pop, text = "Happy", variable = var, font = self.font1, command = None, value = "HAPPY").place(x = 172, y = 185)
                    Radiobutton(pop, text = "Angry", variable = var, font = self.font1, command = None, value = "ANGRY").place(x = 312, y = 185)
                    Radiobutton(pop, text = "Sad", variable = var, font = self.font1, command = None, value = "SAD").place(x = 452, y = 185)
                    Radiobutton(pop, text = "Surprise", variable = var, font = self.font1, command = None, value = "SURPRISE").place(x = 575, y = 185)
                    Radiobutton(pop, text = "Fear", variable = var, font = self.font1, command = None, value = "FEAR").place(x = 715, y = 185)
                    Radiobutton(pop, text = "Disgust", variable = var, font = self.font1, command = None, value = "DISGUST").place(x = 852, y = 185)
                    Button(pop, text = "     OK     ", font = self.font1, command = fechar_pop).place(x = 440, y = 215)
                    # espera pela liberacao, aguardando a resposta do usuario
                    while self.thread_pop_pause: 
                        time.sleep(0.5)
    
        elif node.tag == "qrRead":
            if self.RUNNING_MODE == "EVA_ROBOT": 
                self.client.publish(self.topic_base + "/log", "EVA is capturing QR Code information...")
                self.EVA_ROBOT_STATE = "BUSY"
                self.client.publish(self.topic_base + "/qrRead", " ")
                self.ledAnimation("LISTEN")
                
    
                while (self.EVA_ROBOT_STATE != "FREE"):
                    pass
                
                
                if node.get("var") == None: # Maintains compatibility with the use of the $ variable
                    self.memory.var_dolar.append([self.EVA_DOLLAR, "<qrRead>"])
                    self.gui.terminal.insert(INSERT, "\nSTATE: QR Code reading: var = $" + ", value = " + self.memory.var_dolar[-1][0])
                    self.tab_load_mem_dollar()
                    self.gui.terminal.see(tkinter.END)
                    self.ledAnimation("STOP")
                else:
                    var_name = node.attrib["var"]
                    self.memory.vars[var_name] = self.EVA_DOLLAR
                    print("Eva ram => ", self.memory.vars)
                    self.gui.terminal.insert(INSERT, "\nSTATE: QR Code reading (using the user variable '" + var_name + "'): " + str(self.memory.vars[var_name]))
                    self.tab_load_mem_vars() # Enter data from variable memory into the var table
                    self.gui.terminal.see(tkinter.END)
                    print("qrRead command USING VAR...")
                self.ledAnimation("STOP")
    
            else:
            
                self.lock_thread_pop()
                self.ledAnimation("LISTEN")
                if self.gui.chk_qrRead_value.get() == 1:
                
                    result_qr = qr.main()
    
                    var = StringVar(value=result_qr)
    
                    if node.get("var") == None: # mantém a compatibilidade com o uso da variável $
                        self.memory.var_dolar.append([var.get(), "<qrRead>"])
                        self.gui.terminal.insert(INSERT, "\nSTATE: qrRead : var=$" + ", value=" + self.memory.var_dolar[-1][0])
                        self.tab_load_mem_dollar()
                        self.gui.terminal.see(tkinter.END)
                    else:
                        var_name = node.attrib["var"]
                        self.memory.vars[var_name] = var.get()
                        print("Eva ram => ", self.memory.vars)
                        self.gui.terminal.insert(INSERT, "\nSTATE: qrRead : (using the user variable '" + var_name + "'): " + self.EVA_DOLLAR)
                        self.tab_load_mem_vars() # entra com os dados da memoria de variaveis na tabela de vars
                        self.gui.terminal.see(tkinter.END)
    
                elif self.gui.chk_qrRead_value.get() == 0:
                
                    # Pop up window closing function for the <return> key
                    def fechar_pop_ret(s): 
                        print(var.get())
                        if node.get("var") == None: # Maintains compatibility with the use of the $ variable
                            self.memory.var_dolar.append([var.get(), "<qrRead>"])
                            self.gui.terminal.insert(INSERT, "\nSTATE: QR Code reading: var = $" + ", value = " + self.memory.var_dolar[-1][0])
                            self.tab_load_mem_dollar()
                            self.gui.terminal.see(tkinter.END)
                            pop.destroy()
                            self.unlock_thread_pop() # Reactivate the script processing thread
                        else:
                            var_name = node.attrib["var"]
                            self.memory.vars[var_name] = var.get()
                            print("Eva ram => ", self.memory.vars)
                            self.gui.terminal.insert(INSERT, "\nSTATE: QR Code reading (using the user variable '" + var_name + "'): " + str(self.memory.vars[var_name]))
                            self.tab_load_mem_vars() # Enter data from variable memory into the var table
                            self.gui.terminal.see(tkinter.END)
                            print("qrRead command USING VAR...")
                            pop.destroy()
                            self.unlock_thread_pop() # Reactivate the script processing thread
                    
                    # Pop up window closing function for OK button
                    def fechar_pop_bt(): 
                        print(var.get())
                        if node.get("var") == None: # Maintains compatibility with the use of the $ variable
                            self.memory.var_dolar.append([var.get(), "<qrRead>"])
                            self.gui.terminal.insert(INSERT, "\nSTATE: QR Code reading: var = $" + ", value = " + self.memory.var_dolar[-1][0])
                            self.tab_load_mem_dollar()
                            self.gui.terminal.see(tkinter.END)
                            pop.destroy()
                            self.unlock_thread_pop() # Reactivate the script processing thread
                        else:
                            var_name = node.attrib["var"]
                            self.memory.vars[var_name] = var.get()
                            print("Eva ram => ", self.memory.vars)
                            self.gui.terminal.insert(INSERT, "\nSTATE: QR Code reading (using the user variable '" + var_name + "'): " + str(self.memory.vars[var_name]))
                            self.tab_load_mem_vars() # Enter data from variable memory into the var table
                            self.gui.terminal.see(tkinter.END)
                            print("qrRead command USING VAR...")
                            pop.destroy()
                            self.unlock_thread_pop() # Reactivate the script processing thread
                        
                    # Window (self.gui) creation
                    img_qr = PhotoImage(file = "images/img_qr.png")
                    var = StringVar()
                    pop = Toplevel(self.gui)
                    pop.title("qrRead Command")
                    # Disable the maximize and close buttons
                    pop.resizable(False, False)
                    pop.protocol("WM_DELETE_WINDOW", False)
                    w = 350
                    h = 200
                    ws = self.gui.winfo_screenwidth()
                    hs = self.gui.winfo_screenheight()
                    x = (ws/2) - (w/2)
                    y = (hs/2) - (h/2)  
                    pop.geometry('%dx%d+%d+%d' % (w, h, x, y))
                    label = Label(pop, text="Eva is reading a QR Code... \nPlease, enter the information contained in the QRCode!", font = ('Arial', 10))
                    label.pack(pady=20)
                    Label(pop, image=img_qr).place(x = 260, y = 110)
                    E1 = Entry(pop, textvariable = var, font = ('Arial', 10))
                    E1.bind("<Return>", fechar_pop_ret)
                    E1.pack()
                    Button(pop, text="    OK    ", font = self.font1, command=fechar_pop_bt).pack(pady=20)
                    # Wait for release, waiting for the user's response
                    while self.thread_pop_pause: 
                        time.sleep(0.5)
                    self.ledAnimation("STOP")
    
        elif node.tag == "userID":
            if self.RUNNING_MODE == "EVA_ROBOT": 
                EVA_ROBOT_STATE = "BUSY"
                self.client.publish(self.topic_base + "/userID", " ")
                self.ledAnimation("LISTEN")
                
    
                while (EVA_ROBOT_STATE != "FREE"):
                    pass
                
                if node.get("var") == None: # Maintains compatibility with the use of the $ variable
                    self.memory.var_dolar.append([self.EVA_DOLLAR, "<userID>"])
                    self.gui.terminal.insert(INSERT, "\nSTATE: userID: var = $" + ", value = " + self.memory.var_dolar[-1][0])
                    self.tab_load_mem_dollar()
                    self.gui.terminal.see(tkinter.END)
    
                else:
                    var_name = node.attrib["var"]
                    self.memory.vars[var_name] = self.EVA_DOLLAR
                    print("Eva ram => ", self.memory.vars)
                    self.gui.terminal.insert(INSERT, "\nSTATE: userID (using the user variable '" + var_name + "'): " + str(self.memory.vars[var_name]))
                    self.tab_load_mem_vars() # Enter data from variable memory into the var table
                    self.gui.terminal.see(tkinter.END)
                    print("userID command USING VAR...")
                
                self.ledAnimation("STOP")
    
            else:
            
                self.lock_thread_pop()
                self.ledAnimation("LISTEN")
                if self.gui.chk_userid_value.get() == 1:
                
                    result_recognition = fr.main()
    
                    var = StringVar(value=result_recognition)
    
                    if node.get("var") == None: # mantém a compatibilidade com o uso da variável $
                        self.memory.var_dolar.append([var.get(), "<userID>"])
                        self.gui.terminal.insert(INSERT, "\nSTATE: userID : var=$" + ", value=" + self.memory.var_dolar[-1][0])
                        self.tab_load_mem_dollar()
                        self.gui.terminal.see(tkinter.END)
                    
                    else:
                        var_name = node.attrib["var"]
                        self.memory.vars[var_name] = var.get()
                        print("Eva ram => ", self.memory.vars)
                        self.gui.terminal.insert(INSERT, "\nSTATE: userID : (using the user variable '" + var_name + "'): " + self.EVA_DOLLAR)
                        self.tab_load_mem_vars() # entra com os dados da memoria de variaveis na tabela de vars
                        self.gui.terminal.see(tkinter.END)
    
                elif self.gui.chk_userid_value.get() == 0:
                # Pop up window closing function for the <return> key
                    def fechar_pop_ret(s): 
                        print(var.get())
                        if node.get("var") == None: # mantém a compatibilidade com o uso da variável $
                            self.memory.var_dolar.append([var.get(), "<userID>"])
                            self.gui.terminal.insert(INSERT, "\nSTATE: userID: var = $" + ", value = " + self.memory.var_dolar[-1][0])
                            self.tab_load_mem_dollar()
                            self.gui.terminal.see(tkinter.END)
                            pop.destroy()
                            self.unlock_thread_pop() # Reactivate the script processing thread
                        else:
                            var_name = node.attrib["var"]
                            self.memory.vars[var_name] = var.get()
                            print("Eva ram => ", self.memory.vars)
                            self.gui.terminal.insert(INSERT, "\nSTATE: userID reading (using the user variable '" + var_name + "'): " + str(self.memory.vars[var_name]))
                            self.tab_load_mem_vars() # Enter data from variable memory into the var table
                            self.gui.terminal.see(tkinter.END)
                            print("userID command USING VAR...")
                            pop.destroy()
                            self.unlock_thread_pop() # Reactivate the script processing thread
                    
                    # Pop up window closing function for OK button
                    def fechar_pop_bt(): 
                        print(var.get())
                        if node.get("var") == None: # Maintains compatibility with the use of the $ variable
                            self.memory.var_dolar.append([var.get(), "<userID>"])
                            self.gui.terminal.insert(INSERT, "\nSTATE: userID: var = $" + ", value = " + self.memory.var_dolar[-1][0])
                            self.tab_load_mem_dollar()
                            self.gui.terminal.see(tkinter.END)
                            pop.destroy()
                            self.unlock_thread_pop() # Reactivate the script processing thread
                        else:
                            var_name = node.attrib["var"]
                            self.memory.vars[var_name] = var.get()
                            print("Eva ram => ", self.memory.vars)
                            self.gui.terminal.insert(INSERT, "\nSTATE: userID (using the user variable '" + var_name + "'): " + str(self.memory.vars[var_name]))
                            self.tab_load_mem_vars() # Enter data from variable memory into the var table
                            self.gui.terminal.see(tkinter.END)
                            print("userID command USING VAR...")
                            pop.destroy()
                            self.unlock_thread_pop() # Reactivate the script processing thread
                        
                    # Window (self.gui) creation
                    img_userID = PhotoImage(file = "images/img_userID.png")
                    var = StringVar()
                    pop = Toplevel(self.gui)
                    pop.title("userID Command")
                    # Disable the maximize and close buttons
                    pop.resizable(False, False)
                    pop.protocol("WM_DELETE_WINDOW", False)
                    w = 350
                    h = 200
                    ws = self.gui.winfo_screenwidth()
                    hs = self.gui.winfo_screenheight()
                    x = (ws/2) - (w/2)
                    y = (hs/2) - (h/2)  
                    pop.geometry('%dx%d+%d+%d' % (w, h, x, y))
                    label = Label(pop, text="Eva is recognizing a face... \nPlease, enter the user name!", font = ('Arial', 10))
                    label.pack(pady=20)
                    Label(pop, image=img_userID).place(x = 260, y = 110)
                    E1 = Entry(pop, textvariable = var, font = ('Arial', 10))
                    E1.bind("<Return>", fechar_pop_ret)
                    E1.pack()
                    Button(pop, text="    OK    ", font = self.font1, command=fechar_pop_bt).pack(pady=20)
                    # Wait for release, waiting for the user's response
                    while self.thread_pop_pause: 
                        time.sleep(0.5)
                    self.ledAnimation("STOP")


    def busca_commando(self, key : str): # The keys are strings
        # Search in settings. This is because "voice" is in settings and voice is always the first element
        for elem in self.root.find("settings").iter():
            if elem.get("key") != None: # Check if node has key attribute
                if elem.attrib["key"] == key:
                    return elem
        # Search within the script
        for elem in self.root.find("script").iter(): # Go through all nodes in the script
            if elem.get("key") != None: # Check if node has key attribute
                if elem.attrib["key"] == key:
                    return elem
    
    
    # Search and insert links in the list that have "att_from" equal to the "from" attribute of the link
    def busca_links(self, att_from):
        achou_link = False
        for i in range(len(self.links_node)):
            if att_from == self.links_node[i].attrib["from"]:
                self.fila_links.append(self.links_node[i])
                achou_link = True
        return achou_link


    # Execute commands in the link stack
    def link_process(self, anterior = -1):
        print("self.play state............", self.play)
        self.gui.terminal.insert(INSERT, "\n---------------------------------------------------")
        self.gui.terminal.insert(INSERT, "\nSTATE: Starting the script: " + self.root.attrib["name"] + "_EvaML.xml")
        self.gui.terminal.see(tkinter.END)

        if self.RUNNING_MODE == "EVA_ROBOT":
            self.client.publish(self.topic_base + "/log", "Starting the script: " + self.root.attrib["name"] + "_EvaML.xml")

        while (len(self.fila_links) != 0) and (self.play == True):
            from_key = self.fila_links[0].attrib["from"] # Key of the command to execute
            to_key = self.fila_links[0].attrib["to"] # Key of next command
            print("from:", from_key, ", to_key:", to_key)
            comando_from = self.busca_commando(from_key).tag # Tag of the command to be executed

            # Prevents the same node from running consecutively. This happens with the node that precedes the "cases"
            if anterior != from_key:
                self.exec_comando(self.busca_commando(from_key))
                anterior = from_key
                print("ant: ", anterior, ", from: ", from_key)


            if (comando_from == "case") or (comando_from == "default"): # If the command executed was a case or a default
                if self.memory.reg_case == 1: # Check the flag to see if the "case" was true
                    self.fila_links = [] # Empty the queue, as the flow will continue from this "case" onwards
                    print("Jumping the command = ", comando_from)
                    # Follows the flow of the success "case" looking for the "prox. link"
                    if not(self.busca_links(to_key)): # If there is no longer a link, the command indicated by "to_key" is the last one in the flow
                        self.exec_comando(self.busca_commando(to_key))
                        print("End of block.")

                else:
                    print("The element:", comando_from, " will be removed from queue.")
                    self.fila_links.pop(0) # If the "case" failed, it is removed from the queue and consequently its flow is discarded
                    print("false")
            else: # If the command was not a "case"
                print("The element:", comando_from, " will be removed from queue.")
                self.fila_links.pop(0) # Remove the link from the queue
                if not(self.busca_links(to_key)): # As previously mentioned
                    self.exec_comando(self.busca_commando(to_key))
                    print("End of block.")
        self.gui.terminal.insert(INSERT, "\nSTATE: End of script.")
        self.gui.terminal.see(tkinter.END)
        # Restore the buttons states (run and stop)
        self.gui.bt_run_sim['state'] = NORMAL
        self.gui.bt_run_sim.bind("<Button-1>", self.setSimMode)
        if ROBOT_MODE_ENABLED: self.gui.bt_run_robot['state'] = NORMAL
        self.gui.bt_run_robot.bind("<Button-1>", self.setEVAMode)
        self.gui.bt_import['state'] = NORMAL
        self.gui.bt_reload['state'] = NORMAL
        self.gui.bt_import.bind("<Button-1>", self.importFileThread)
        self.gui.bt_stop['state'] = DISABLED
        self.gui.bt_stop.unbind("<Button1>")

if __name__ == "__main__":
    e = EvaSim()