from fastapi import FastAPI
from app.database.connection import database
from app.middlewares.cors import add_cors
from app.api import users, music

<<<<<<< HEAD
=======

class UserLogin(BaseModel):
    name: str
    password: str

class UserRegister(BaseModel):
    name: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)

>>>>>>> 1d5c4d5 (temp)
app = FastAPI()
add_cors(app)


@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


app.include_router(users.router, prefix="/users")
app.include_router(music.router, prefix="/music")