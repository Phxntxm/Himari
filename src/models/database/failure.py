import typing

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.database import Base

if typing.TYPE_CHECKING:
    from src.models.database import Weekly


class Failure(Base):
    __tablename__ = "failure_gif"

    id: Mapped[int] = mapped_column(primary_key=True)
    weekly_id: Mapped[int] = mapped_column(
        ForeignKey("weekly.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(nullable=False)

    weekly: Mapped["Weekly"] = relationship("Weekly", back_populates="failure_gifs")
