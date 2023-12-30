import typing

from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.database import Base

if typing.TYPE_CHECKING:
    from src.models.database import CountdownImage


class Countdown(Base):
    __tablename__ = "countdown"

    id: Mapped[int] = mapped_column(primary_key=True)
    guild_id: Mapped[int] = mapped_column(index=True, nullable=False)
    creator_id: Mapped[int] = mapped_column(index=True, nullable=False)
    timestamp: Mapped[int] = mapped_column(nullable=False)
    lookup: Mapped[str] = mapped_column(nullable=False)

    images: Mapped[list["CountdownImage"]] = relationship(
        "CountdownImage", back_populates="countdown"
    )
