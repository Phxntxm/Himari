import typing

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.database import Base

if typing.TYPE_CHECKING:
    from src.models.database.manga import Manga


class MangaFollower(Base):
    __tablename__ = "manga_follower"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(nullable=False)
    manga_id: Mapped[int] = mapped_column(ForeignKey("manga.id"), nullable=False)

    manga: Mapped["Manga"] = relationship("Manga", back_populates="followers")
