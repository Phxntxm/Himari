import typing

from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.database import Base

if typing.TYPE_CHECKING:
    from src.models.database import Failure, Success


class Weekly(Base):
    __tablename__ = "weekly"

    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[int] = mapped_column(index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(index=True, nullable=False)
    timestamp: Mapped[int] = mapped_column(nullable=False)
    lookup: Mapped[str] = mapped_column(nullable=False)

    success_gifs: Mapped[list["Success"]] = relationship(
        "Success", back_populates="weekly"
    )
    failure_gifs: Mapped[list["Failure"]] = relationship(
        "Failure", back_populates="weekly"
    )
