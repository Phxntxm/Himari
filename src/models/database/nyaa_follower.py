import typing

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.database import Base

if typing.TYPE_CHECKING:
    from src.models.database.nyaa import Nyaa


class NyaaFollower(Base):
    __tablename__ = "nyaa_follower"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(nullable=False)
    nyaa_id: Mapped[str] = mapped_column(ForeignKey("nyaa.id"), nullable=False)

    seed: Mapped["Nyaa"] = relationship("Nyaa", back_populates="followers")
