from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from .weekly import Weekly as Weekly
from .club import Club as Club
from .club_member import ClubMember as ClubMember
from .countdown import Countdown as Countdown
from .countdown_image import CountdownImage as CountdownImage
from .failure import Failure as Failure
from .j_novel import JNovel as JNovel
from .manga import Manga as Manga
from .manga_followers import MangaFollower as MangaFollower
from .nyaa import Nyaa as Nyaa
from .nyaa_follower import NyaaFollower as NyaaFollower
from .success import Success as Success
from .daily import Daily as Daily
