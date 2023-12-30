from sqlalchemy.orm import Mapped, mapped_column

from src.models.database import Base


class Daily(Base):
    __tablename__ = "daily"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(index=True, nullable=False)
    timestamp: Mapped[int] = mapped_column(nullable=False)
