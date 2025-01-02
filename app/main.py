from fastapi import FastAPI, HTTPException, UploadFile, File
from app.database import database
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import exc
import os
import mido
import subprocess
from fastapi.responses import FileResponse
from typing import List
from pydub import AudioSegment
from fastapi import Request
import base64


class UserLogin(BaseModel):
       name: str
       password: str
class UserRegister(BaseModel):
    name: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()
@app.get("/users")
async def read_users():
    query = "SELECT * FROM users"
    users = await database.fetch_all(query=query)
    return users

@app.post("/users")
async def register_user(user: UserRegister):
    query_check = "SELECT * FROM users WHERE name = :name" 
    existing_user = await database.fetch_one(query=query_check, values={"name": user.name})

    if existing_user is not None:
        raise HTTPException(status_code=400, detail="User already exists")

    query = "INSERT INTO users (name, password) VALUES (:name, :password)"
    try:
        await database.execute(query=query, values={"name": user.name, "password": user.password})
        existing_user = await database.fetch_one(query=query_check, values={"name": user.name})
    except exc.IntegrityError:
        raise HTTPException(status_code=500, detail="Failed to create user")

    return {"message": "User registered successfully", "name": user.name, "id": existing_user.id}


@app.post("/login")
async def login_user(user: UserLogin):
    query = "SELECT * FROM users WHERE name = :name"
    db_user = await database.fetch_one(query=query, values={"name": user.name})
    
    if db_user is None:
        raise HTTPException(status_code=400, detail="Invalid username")

    if db_user['password'] != user.password: 
        raise HTTPException(status_code=400, detail="Invalid password")

    return {"message": "Login successful", "name": db_user["name"], "id": db_user["id"]}
index = 0
@app.post("/music_converter/{userId}")
async def convert_music( userId: int, request: Request, files: List[UploadFile] = File(...)):
    global index
    output_files = []
    soundfont_path = os.path.join(os.path.dirname(__file__), 'GeneralUser-GS.sf2')
    wav_files = []

    output_directory = "output"
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    for file in files:
        contents = await file.read()
        
        with open(file.filename, 'wb') as f:
            f.write(contents)

        output_format = 'wav'
        wav_filename = f"{os.path.splitext(file.filename)[0]}.{output_format}"
        midi_file = file.filename
        
        subprocess.run(['fluidsynth', '-ni', soundfont_path, midi_file, '-F', wav_filename, '-n', 'audio.file-format=wav'])
        
        os.remove(file.filename)
        wav_files.append(wav_filename) 

    combined = AudioSegment.empty()
    for wav_file in wav_files:
        audio_segment = AudioSegment.from_wav(wav_file)
        combined += audio_segment 

    output_filename = f"combined_output{index}.wav"
    output_path = os.path.join(output_directory, output_filename)

    try:
        combined.export(output_path, format="wav")
    except Exception as e:
        return {"error": str(e)}

    for wav_file in wav_files:
        os.remove(wav_file)
    with open(output_path, 'rb') as f:
        music_data = f.read()

    query = "INSERT INTO history (userId, music) VALUES (:userId, :music)"
    await database.execute(query=query, values={"userId": userId, "music": music_data})
    
    file_url = f"{request.url.scheme}://{request.url.hostname}:{request.url.port}/output/{output_filename}"
    index += 1
    return {"url": file_url}
@app.get("/output/{filename}")
async def get_file(filename: str):
    return FileResponse(path=os.path.join("output", filename), media_type='audio/wav', filename=filename)