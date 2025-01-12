from fastapi import APIRouter, HTTPException
from app.database.connection import database
from app.models.user import UserLogin, UserRegister
from sqlalchemy import exc

router = APIRouter()

@router.get("")
async def read_users():
    query = "SELECT * FROM users"
    users = await database.fetch_all(query=query)
    return users

import bcrypt

@router.post("")
async def register_user(user: UserRegister):
    query_check = "SELECT * FROM users WHERE name = :name"
    existing_user = await database.fetch_one(query=query_check, values={"name": user.name})

    if existing_user is not None:
        raise HTTPException(status_code=400, detail="User already exists")
    if len(user.name) < 6 or len(user.password) < 6:
        return {"message": "Minimal length - 6", "error": True}
    
    
    hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
    
    query = "INSERT INTO users (name, password) VALUES (:name, :password)"
    try:
        await database.execute(query=query, values={"name": user.name, "password": hashed_password})
        existing_user = await database.fetch_one(query=query_check, values={"name": user.name})
    except exc.IntegrityError:
        return {"message": "Failed to create user", "error": True}

    return {"message": "User registered successfully", "name": user.name, "id": existing_user.id, "error": False}

@router.post("/login")
async def login_user(user: UserLogin):
    query = "SELECT * FROM users WHERE name = :name"
    db_user = await database.fetch_one(query=query, values={"name": user.name})

    if db_user is None:
        return {"message": "Invalid username", "error": True}

    # Convert the password from bytes to a string
    hashed_password_bytes = db_user['password']

    # Check if the raw password matches the hashed password
    if not bcrypt.checkpw(user.password.encode('utf-8'), hashed_password_bytes):
        return {"message": "Invalid password", "error": True}

    return {"message": "Login successful", "name": db_user["name"], "id": db_user["id"], "error": False}