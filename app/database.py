from sqlalchemy import MetaData
from databases import Database

DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost/music_converter_db"

database = Database(DATABASE_URL)
metadata = MetaData()