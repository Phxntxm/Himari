import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models.database import Base

url = os.getenv("DATABASE_URL")

if not url:
    raise ValueError("DATABASE_URL is not set")

engine = create_engine(url, echo=True)
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine, autoflush=True)


# Ordering matters here due to circular imports
from .bot import bot as bot
