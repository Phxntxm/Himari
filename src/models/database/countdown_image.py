import typing

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.database import Base

if typing.TYPE_CHECKING:
    from src.models.database import Countdown


class CountdownImage(Base):
    __tablename__ = "countdown_image"

    id: Mapped[int] = mapped_column(primary_key=True)
    countdown_id: Mapped[int] = mapped_column(
        ForeignKey("countdown.id"), nullable=False
    )
    url: Mapped[str] = mapped_column(nullable=False)

    countdown: Mapped["Countdown"] = relationship("Countdown", back_populates="images")
