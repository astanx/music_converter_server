from pydantic import BaseModel, Field

class UserLogin(BaseModel):
       name: str
       password: str
class UserRegister(BaseModel):
    name: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)