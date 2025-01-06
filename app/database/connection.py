from sqlalchemy import MetaData, create_engine, Table, Column, Integer, String, LargeBinary, ForeignKey
from databases import Database

DATABASE_USER_NAME = "postgres"
DATABASE_PASSWORD = "qxHDUgHHzDebSLmLVzxCSZbHuBmKOYdI"
DATABASE_HOST = "autorack.proxy.rlwy.net"
DATABASE_PORT = "35590"
DATABASE_NAME = "railway"

DATABASE_URL = f"postgresql://{DATABASE_USER_NAME}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"
ENGINE_URL = f"postgresql://{DATABASE_USER_NAME}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"
database = Database(DATABASE_URL)
engine = create_engine(ENGINE_URL)
metadata = MetaData()

users_metadata = Table("users", metadata,
    Column("id", Integer(), primary_key=True, autoincrement=True),
    Column("name", String(255), nullable=False),
    Column("password", String(128),  nullable=False),
)

request_metadata = Table("history", metadata,
    Column("id", Integer(), primary_key=True, autoincrement=True),
    Column("userid", Integer(), ForeignKey("users.id"), nullable=False),
    Column("music", LargeBinary(), nullable=False),
    Column("url", String())
)

metadata.create_all(engine)