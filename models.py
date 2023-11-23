from dataclasses import dataclass, field, asdict
from typing import Union, List, Optional, Literal
from datetime import date, datetime
from lib.roman_num import to_roman


import pydantic


class _HHModel(pydantic.BaseModel):
    class Config:
        extra = 'forbid'  # options: allow | forbid | ignore
        validate_assignment = True  # validate assignment of fields in code

# ----------- Models for HistHierarchyStorage - these are main models


class Cafedra(_HHModel):
    id: int | None = None
    header: str
    is_obn: bool = False
    is_link: bool = False
    text: str
    # subheaders like 'Архиепископы и митрополиты Московские;' stored as str.
    episkops: List[Union['EpiskopOfCafedra', str]] = []
    notes: List['Note'] = []


class Dating(_HHModel):
    dating: str
    estimated_date: date | None


class _EpiskopCafedraBase(_HHModel):
    begin_dating: Dating | None
    end_dating: Dating | None

    temp_status: Optional[str]
    inexact: bool = False


class EpiskopInfo(_HHModel):
    id: Optional[int] = None
    name: str
    surname: str | None
    saint_title: str | None = None
    world_title: str | None = None
    comment: str | None = None

    def get_header(self, is_obn):
        r = self.name
        if self.saint_title:
            r = self.saint_title + ' ' + r
        if self.world_title:
            r = r + ' ' + self.world_title
        if self.surname:
            if is_obn:
                r = r + ' ' + self.surname
            else:
                r = r + ' (' + self.surname + ')'
        # if self.number_after_surname:
        #     r  += ' ' + self.number_after_surname

        return r


class EpiskopOfCafedra(_EpiskopCafedraBase):
    episkop: EpiskopInfo
    # Два епископа с одинковым именем без фамилии - второму припишут номер
    namesake_num: int | None = None

    notes: List[int] = []

    def to_episkop_of_cafedra_dto(self, again_num: int = None, is_obn=False)\
            -> 'EpiskopOfCafedraDto':

        episkop = build_title(self.episkop.get_header(is_obn),
                              self.temp_status, again_num,
                              namesake_num=self.namesake_num)
        if self.episkop.comment:
            episkop += ' (' + self.episkop.comment + ')'

        return EpiskopOfCafedraDto(
                episkop=episkop,
                episkop_id=self.episkop.id,
                begin_dating=getattr(self.begin_dating, 'dating', None),
                end_dating=getattr(self.end_dating, 'dating', None),
                inexact=self.inexact,
                notes=self.notes
            )


class Note(_HHModel):
    num: int
    text: str


class Episkop(_HHModel):
    id: Optional[int] = None
    header: str  # full episkop naming
    name: str
    surname: Optional[str]
    saint_title: str | None = None
    is_obn: bool

    cafedras: List['CafedraOfEpiskop'] = []


class CafedraOfEpiskop(_EpiskopCafedraBase):
    cafedra: str
    cafedra_id: Optional[int]

    notes: List[str] = []


class UserComment(_HHModel):
    id: int | None = None
    who: str
    contacts: str = None
    comment: str

    object_type: Literal['cafedra', 'episkop']
    object_id: int
    object_title: str

    timestamp: datetime | None = None


#   ------ Models for book parser of chapter 'Списки иерархов по кафедрам'


@dataclass
class CafedraArticle:
    header: str = None
    is_obn: bool = False
    is_link: bool = False
    start_line: int = None

    text: str = None
    # episkops in cafedra table - list of ArticleEpiskopRow objects.
    # subheaders like 'Архиепископы и митрополиты Московские;' stored as str.
    episkops: List[Union['ArticleEpiskopRow', str]] = \
        field(default_factory=list)
    notes: List['ArticleNote'] = field(default_factory=list)

    @staticmethod
    def from_dict(d):
        res = CafedraArticle(**d)
        for i in range(len(res.episkops)):
            ep = res.episkops[i]
            if isinstance(ep, dict):
                res.episkops[i] = ArticleEpiskopRow(**ep)

        for i in range(len(res.notes)):
            nt = res.notes[i]
            if isinstance(nt, dict):
                res.notes[i] = ArticleNote(**nt)

        return res

    def to_dict(self):
        return asdict(self)


@dataclass
class ArticleEpiskopRow:
    text: str = None


@dataclass
class ArticleNote:
    num: int
    text: str


# ------------ Presentation models for flask templates

@dataclass
class CafedraDto:
    header: str

    is_obn: bool = False
    is_link: bool = False

    text: str = None

    # subheaders like 'Архиепископы и митрополиты Московские;' stored as str.
    episkops: List[Union['EpiskopOfCafedraDto', str]] = field(default_factory=list)  # noqa: E501
    notes: List['ArticleNote'] = field(default_factory=list)

    id: int = None

    @staticmethod
    def from_dict(d):
        res = CafedraDto(**d)
        for i in range(len(res.episkops)):
            ep = res.episkops[i]
            if isinstance(ep, dict):
                res.episkops[i] = EpiskopOfCafedraDto(**ep)

        for i in range(len(res.notes)):
            nt = res.notes[i]
            if isinstance(nt, dict):
                res.notes[i] = ArticleNote(**nt)

        return res

    def to_dict(self):
        return asdict(self)


@dataclass
class EpiskopDto:
    header: str
    is_obn: bool
    cafedras: List['CafedraOfEpiskopDto'] = field(default_factory=list)
    id: int = None


@dataclass
class CafedraOfEpiskopDto:
    cafedra: str
    cafedra_id: int
    is_obn: bool

    begin_dating: str
    end_dating: str

    inexact: bool = False

    notes: List['ArticleNote'] = field(default_factory=list)


@dataclass
class EpiskopOfCafedraDto:
    episkop: str
    episkop_id: str

    begin_dating: str
    end_dating: str

    inexact: bool = False

    notes: List['ArticleNote'] = field(default_factory=list)


def build_title(header, temp_status: str, again_num: int,
                namesake_num: int = None):
    if temp_status:
        header = temp_status + ' ' + header
    if namesake_num:
        header += ' ' + to_roman(namesake_num)
    if again_num is not None and again_num > 1:
        if again_num == 2:
            t = 'паки'
        else:
            t = f'в {again_num}-й раз'
        header += ", " + t
    return header


# Db models using Peewee ORM

from peewee import Model, AutoField, TextField, BooleanField, \
                   ForeignKeyField, IntegerField, \
                   DateField, TimestampField, SQL  # noqa: E402


class CafedraOrm(Model):
    class Meta:
        table_name = 'Cafedra'

    id = AutoField()
    header = TextField(index=True)
    is_obn = BooleanField()
    is_link = BooleanField()
    # text = TextField(null=True)  # ?? for links
    article_json = TextField()

    go_to = ForeignKeyField('self', null=True, index=False)


class EpiskopOrm(Model):
    class Meta:
        table_name = 'Episkop'

    id = AutoField()
    header = TextField()
    name = TextField()
    surname = TextField(null=True)
    saint_title = TextField(null=True, default=None)
    is_obn = BooleanField(null=False)


EpiskopOrm.add_index(
    SQL('create index if not exists EpiskopsLowerPy '
        'on episkop(LOWER_PY(name), LOWER_PY(surname))')
)


class EpiskopCafedraOrm(Model):
    class Meta:
        table_name = 'EpiskopCafedra'

    id = AutoField()
    episkop = ForeignKeyField(EpiskopOrm, backref='cafedras', index=True)
    cafedra = ForeignKeyField(CafedraOrm, backref='episkops', index=True)

    # sequence number of episkop for self.cafedra
    episkop_num = IntegerField()

    # sequence number of cafedra for self.episkop
    # cafedra_num = IntegerField()

    begin_dating = TextField(null=True)
    estimated_begin_date = DateField(null=True)

    end_dating = TextField(null=True)

    temp_status = TextField(null=True)  # в/у в/у?

    inexact = BooleanField(default=False)  # information is inexact

    # Два епископа с одинковым именем без фамилии - второму припишут номер
    namesake_num = IntegerField(null=True)

    def to_cafedra_of_episkop_dto(self, again_num: int = None):
        return CafedraOfEpiskopDto(
                cafedra=build_title(self.cafedra.header,
                                    self.temp_status, again_num),
                cafedra_id=self.cafedra.id,
                begin_dating=self.begin_dating,
                end_dating=self.end_dating,
                inexact=self.inexact,
                notes=self.notes,
                is_obn = self.cafedra.is_obn
            )


class NoteOrm(Model):
    """
    Note linked to cafedra article
    """

    class Meta:
        table_name = 'Note'

    id = AutoField()
    text = TextField()

    cafedra_id = ForeignKeyField(CafedraOrm, backref='text_notes', index=True)
    text_position = IntegerField(null=True)
    """Optional position of note in cafedra article text"""

    episkop_cafedra_id = ForeignKeyField(EpiskopCafedraOrm,
                                         backref='notes', null=True,
                                         index=True)
    """For notes linked to episkops table of cafedra article"""


class UserCommentOrm(Model):
    class Meta:
        table_name = 'UserComment'

    id = AutoField()
    who = TextField()
    contacts = TextField(null=True)
    comment = TextField()

    object_type = TextField()
    object_id = IntegerField()
    object_title = TextField()

    timestamp = TimestampField()


HierarhOrmModels = (CafedraOrm, EpiskopOrm, EpiskopCafedraOrm, NoteOrm)
CommentOrmModels = (UserCommentOrm, )
