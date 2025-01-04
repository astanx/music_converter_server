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
        return {"message": "Failed to create user", "error": True}

    return {"message": "User registered successfully", "name": user.name, "id": existing_user.id, "error": False}


@app.post("/login")
async def login_user(user: UserLogin):
    query = "SELECT * FROM users WHERE name = :name"
    db_user = await database.fetch_one(query=query, values={"name": user.name})
    
    if db_user is None:
        return {"message": "Invalid username", "error": True}

    if db_user['password'] != user.password: 
        return {"message": "Invalid password", "error": True}

    return {"message": "Login successful", "name": db_user["name"], "id": db_user["id"], "error": False}

@app.post("/music_converter/{userId}")
async def convert_music(userId: int, files: List[UploadFile] = File(...)):
    soundfont_path = os.path.join(os.path.dirname(__file__), 'GeneralUser-GS.sf2')
    wav_files = []

    output_directory = "output"
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    for file in files:
        contents = await file.read()
        
        temp_midi_path = os.path.join(output_directory, file.filename)
        with open(temp_midi_path, 'wb') as f:
            f.write(contents)

        output_format = 'wav'
        wav_filename = f"{os.path.splitext(file.filename)[0]}.{output_format}"
        wav_file_path = os.path.join(output_directory, wav_filename)

       
        try:
            subprocess.run(['fluidsynth', '-ni', soundfont_path, temp_midi_path, '-F', wav_file_path, '-n', 'audio.file-format=wav'], check=True)
            wav_files.append(wav_file_path) 
        except subprocess.CalledProcessError as e:
            return {"message": str(e), "error": True}
        finally:
            os.remove(temp_midi_path)  

    combined = AudioSegment.empty()
    for wav_file in wav_files:
        audio_segment = AudioSegment.from_wav(wav_file)
        combined += audio_segment 

    output_filename = f"combined_output.wav"
    output_path = os.path.join(output_directory, output_filename)

    try:
        combined.export(output_path, format="wav")
    except Exception as e:
        return {"message": str(e), "error": True}

    for wav_file in wav_files:
        os.remove(wav_file)

    with open(output_path, 'rb') as f:
        music_data = f.read()
    encoded_music_data = base64.b64encode(music_data).decode('utf-8')
    
    query = "INSERT INTO history (userId, music) VALUES (:userId, :music)"
    await database.execute(query=query, values={"userId": userId, "music": encoded_music_data})
    os.remove(output_path)
    return {"music": encoded_music_data, "error": False, "message": "Convert successful"}

@app.get("/history/{userId}")
async def get_file(userId: int):
    query = "SELECT id, music FROM history WHERE userId = :userId"
    history = await database.fetch_all(query=query, values={"userId": userId})
    
    result = [{"id": item["id"], "music": item["music"]} for item in history]
    return {"music": result, "error": False, "message": "Successful"}
@app.delete("/history/{id}")
async def delete_file(id: int): 
    query = "DELETE FROM history WHERE id = :id"
    result = await database.execute(query=query, values={"id": id})
    
    if result == 0:
        return {"error": True, "message": "Record not found"}
    
    return {"error": False, "message": "Successful"}