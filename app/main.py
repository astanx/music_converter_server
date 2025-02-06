from fastapi import FastAPI
import os
import uvicorn
from app.database.connection import database
from app.middlewares.cors import add_cors
from app.api import users, music

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

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080)) 
    uvicorn.run(app, host="0.0.0.0", port=port)