import typing

from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.database import Base

if typing.TYPE_CHECKING:
    from src.models.database import ClubMember


class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(index=True, nullable=False)
    guild_id: Mapped[int] = mapped_column(index=True, nullable=False)
    creator_id: Mapped[int] = mapped_column(index=True, nullable=False)

    members: Mapped[typing.List["ClubMember"]] = relationship(
        "ClubMember", back_populates="club"
    )
