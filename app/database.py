from sqlalchemy import MetaData, create_engine, Table, Column, Integer, String, Boolean, Text, ForeignKey
from databases import Database

DATABASE_USER_NAME = "postgres"
DATABASE_PASSWORD = "password"
DATABASE_URL = "postgresql+asyncpg://" + DATABASE_USER_NAME + ":" + DATABASE_PASSWORD + "@localhost/music_converter_db"
ENGINE_URL = "postgresql+psycopg2://" + DATABASE_USER_NAME + ":" + DATABASE_PASSWORD + "@localhost/music_converter_db"

database = Database(DATABASE_URL)
engine = create_engine(ENGINE_URL)
metadata = MetaData()

users_metadata = Table("users", metadata,
    Column("id", Integer(), primary_key=True, autoincrement=True),
    Column("name", String(255), nullable=False),
    Column("password", String(128),  nullable=False),
    Column("admin", Boolean(), default=False)
)

request_metadata = Table("request", metadata,
    Column("id", Integer(), primary_key=True, autoincrement=True),
    Column("user_id", Integer(), ForeignKey("users.id"), nullable=False),
    Column("source_file_path", Text()),
    Column("result_file_path", Text())
)

metadata.create_all(engine)