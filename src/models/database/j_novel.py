from sqlalchemy.orm import Mapped, mapped_column

from src.models.database import Base


class JNovel(Base):
    __tablename__ = "j_novel"

    id: Mapped[int] = mapped_column(primary_key=True)
    series: Mapped[str] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    latest: Mapped[str | None] = mapped_column(nullable=True)
    channel_id: Mapped[int] = mapped_column(nullable=False)
    guild_id: Mapped[int] = mapped_column(nullable=False)
    creator_id: Mapped[int] = mapped_column(nullable=False)
