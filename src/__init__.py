from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models.database import Base


engine = create_engine("sqlite:///database.db")
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine, autoflush=True)


# Ordering matters here due to circular imports
from .bot import bot as bot
