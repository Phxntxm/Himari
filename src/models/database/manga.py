import typing

from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.database import Base

if typing.TYPE_CHECKING:
    from src.models.database.manga_followers import MangaFollower


class Manga(Base):
    __tablename__ = "manga"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(nullable=True)
    mangadex_id: Mapped[str] = mapped_column(nullable=False)
    cover: Mapped[str | None] = mapped_column(nullable=True)
    latest_chapter_id: Mapped[str] = mapped_column(nullable=True)
    guild_id: Mapped[int] = mapped_column(nullable=False)
    channel_id: Mapped[int] = mapped_column(nullable=False)

    followers: Mapped[list["MangaFollower"]] = relationship(
        "MangaFollower", back_populates="manga"
    )
