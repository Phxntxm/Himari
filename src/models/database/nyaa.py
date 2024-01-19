import typing

from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.database import Base

if typing.TYPE_CHECKING:
    from src.models.database.nyaa_follower import NyaaFollower


class Nyaa(Base):
    __tablename__ = "nyaa"

    id: Mapped[int] = mapped_column(primary_key=True)
    match: Mapped[str] = mapped_column(nullable=False)
    latest: Mapped[str | None] = mapped_column(nullable=True)
    name: Mapped[str] = mapped_column(nullable=False)
    channel_id: Mapped[int] = mapped_column(nullable=False)
    guild_id: Mapped[int] = mapped_column(nullable=False)
    creator_id: Mapped[int] = mapped_column(nullable=False)

    followers: Mapped[list["NyaaFollower"]] = relationship(
        "NyaaFollower", back_populates="seed"
    )
