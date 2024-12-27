from fastapi import FastAPI, HTTPException, UploadFile, File
from app.database import database
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import exc
import os
import mido
import subprocess


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
        raise HTTPException(status_code=400, detail="Invalid username or password")

    if db_user['password'] != user.password: 
        raise HTTPException(status_code=400, detail="Invalid username or password")

    return {"message": "Login successful", "name": db_user["name"], "id": db_user["id"]}

@app.post("/music_converter")
async def convert_music(file: UploadFile = File(...)):
    contents = await file.read()
    
    with open(file.filename, 'wb') as f:
        f.write(contents)

    output_format = 'mp3' 
    output_filename = f"{os.path.splitext(file.filename)[0]}.{output_format}"

    midi_file = file.filename
    soundfont = "path/to/your/soundfont.sf2" 

    subprocess.run(['fluidsynth', '-ni', soundfont, midi_file, '-F', output_filename, '-n', 'audio.file-format=wav'])

    os.remove(file.filename)
    return {"filename": output_filename}

    