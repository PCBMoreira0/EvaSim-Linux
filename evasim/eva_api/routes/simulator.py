from datetime import datetime
from fastapi import APIRouter, HTTPException
import uuid

from fastapi.responses import FileResponse, StreamingResponse
from fastapi import UploadFile
from fastapi import UploadFile
from eva_sim import EvaSim
from controllers.api_sim_controller import API_SIMController
from controllers.sim_api_controller import SIM_APIController

from ..users.users import add_new_intance, get_dict, remove_dict, get_value
from task_queue import put_to_queue
from pydantic import BaseModel

from concurrent.futures import ThreadPoolExecutor
import asyncio

from io import BytesIO


import speech_recognition

import os

class InputModel(BaseModel):
    input : str

executor = ThreadPoolExecutor(max_workers=4)

router = APIRouter(prefix="/sim", tags=["Simulator"])

@router.post("/init")
def init():
    sim_id = uuid.uuid1()
    add_new_intance(str(sim_id))
    return {"uuid": sim_id}

@router.post("/import/{id}")
def import_file(id : str, path : str):
    from experiences.experiences import get_path

    if not os.path.exists(get_path(path)):
        raise HTTPException(status_code=404, detail="File not found")
    
    c = get_value(id)
    c.api_sim.importFile(c.eva_sim, path)
    return {"status":"success"}

@router.post("/start/{id}")
def start(id : str):
    if id not in get_dict():
        return {"status":"key not found"}
    
    c = get_value(id)

    if c.eva_sim.play:
        return {"status":"script is already playing"}
    
    if not c.api_sim.startSim(c.eva_sim):
        return {"error":"no file imported"}
    return {"status":"success"}

@router.post("/next/{id}")
async def next(id:str):
    if id not in get_dict():
        return {"status":"key not found"}
    
    s = {}
    
    c = get_value(id)

    if c.eva_sim.isWaitingInput:
            return {"status":"waiting input"}
    
    while not s:
        if not c.api_sim.next_step(c.eva_sim):
            return {"status":"script is not playing"}

        s = await c.sim_api.get_result()

    return s

@router.post("/send/{id}")
def send_input(id:str, input : InputModel):
    c = get_value(id)
    
    if c.eva_sim.isWaitingInput:
        c.api_sim.send_input(c.eva_sim, input.input)
        return {"status": "success"}
    else:
        return {"status":"not waiting input"}

@router.post("/stop/{id}")
def stop(id : str):
    if id not in get_dict():
        return {"status":"key not found"}
    
    c = get_value(id)
    if not c.eva_sim.play: return {"status":"script not playing"}
    
    c.api_sim.stopSim(c.eva_sim)
    return {"status": "success"}

@router.delete("/delete/{id}")
def delete_sim(id : str):
    if id not in get_dict():
        return {"status":"key not found"}
    
    remove_dict(id).eva_sim.window.destroy()

    return {"status": "success"}

@router.get("/audio/{name}", response_class=FileResponse)
def get_audio(name : str):
    audio_path= "../evasim/audio_files/" + name + ".wav"
    if os.path.exists(audio_path):
        return FileResponse(audio_path, media_type="audio/wav")
    else:
        raise HTTPException(status_code=404, detail="File not found")

@router.get("/dicts")
def dicts():
    return get_dict()


#TTS
def inference_tts(text : str):
    import numpy as np
    from onnxruntime import InferenceSession
    import json

    # You can generate token ids as follows:
    #   1. Convert input text to phonemes using https://github.com/hexgrad/misaki
    #   2. Map phonemes to ids using https://huggingface.co/hexgrad/Kokoro-82M/blob/785407d1adfa7ae8fbef8ffd85f34ca127da3039/config.json#L34-L148
 
    # Carregar JSON de mapeamento
    with open("../evasim/tts/phoemes.json", "r", encoding="utf-8") as f:
        phoneme_to_id = json.load(f)

    from misaki import en

    g2p = en.G2P(trf=False, british=False, fallback=None) # no transformer, American English

    phonemes, tokens = g2p(text)
    tokens = [phoneme_to_id["vocab"].get(p, 0) for p in phonemes]

    # Context length is 512, but leave room for the pad token 0 at the start & end
    assert len(tokens) <= 510, len(tokens)

    # Style vector based on len(tokens), ref_s has shape (1, 256)
    voices = np.fromfile('../evasim/tts/voices/af.bin', dtype=np.float32).reshape(-1, 1, 256)
    ref_s = voices[len(tokens)]

    # Add the pad ids, and reshape tokens, should now have shape (1, <=512)
    tokens = [[0, *tokens, 0]]

    model_name = 'model_q8f16.onnx' # Options: model.onnx, model_fp16.onnx, model_quantized.onnx, model_q8f16.onnx, model_uint8.onnx, model_uint8f16.onnx, model_q4.onnx, model_q4f16.onnx
    sess = InferenceSession(os.path.join('../evasim/tts/onnx', model_name))

    audio = sess.run(None, dict(
        input_ids=tokens,
        style=ref_s,
        speed=np.array([0.8], dtype=np.float32),
    ))[0]

    import scipy.io.wavfile as wavfile
    buffer = BytesIO()
    wavfile.write(buffer, 24000, audio[0])
    buffer.seek(0)
    return buffer

@router.post("/tts/inference")
async def get_tts(input : InputModel):
    loop = asyncio.get_event_loop()
    audio = await loop.run_in_executor(executor, inference_tts, input.input)
    return StreamingResponse(audio, media_type="audio/wav")


def process_stt(file):
    r = speech_recognition.Recognizer()

    audio_data = BytesIO(file)

    with speech_recognition.AudioFile(audio_data) as source:
        audio = r.record(source)

    # recognize speech using Google Speech Recognition
    try:
        # for testing purposes, we're just using the default API key
        # to use another API key, use `r.recognize_google(audio, key="GOOGLE_SPEECH_RECOGNITION_API_KEY")`
        # instead of `r.recognize_google(audio)` 
        result = r.recognize_google(audio)
        if result is None: 
            return {"error":"Could not transcribe the audio"}
        return {"result":result}
    except speech_recognition.UnknownValueError:
        {"error":"Google Speech Recognition could not understand audio"}
    except speech_recognition.RequestError as e:
        {"error":"Could not request results from Google Speech Recognition service; {0}".format(e)}


#STT
@router.post("/stt")
async def get_stt(file : UploadFile):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, process_stt, await file.read())
    
    return result