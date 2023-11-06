from dataclasses import dataclass, field, asdict
from typing import Union, List, Optional

import pydantic


class _HHModel(pydantic.BaseModel):
    class Config:
        extra = 'forbid'  # options: allow | forbid | ignore
        validate_assignment = True  # validate assignment of fields in code


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


# Db models using Peewee ORM

from peewee import Model, AutoField, TextField, BooleanField, \
                   ForeignKeyField, IntegerField  # noqa: E402


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
    name = TextField(index=True)


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
    begin_year = IntegerField(null=True)
    end_dating = TextField(null=True)

    temp_status = TextField(null=True)  # в/у в/у?

    inexact = BooleanField(default=False)  # information is inexact

    def to_episkop_of_cafedra_dto(self, again_num: int = None):
        return EpiskopOfCafedraDto(
                episkop=build_title(self.episkop.name,
                                    self.temp_status, again_num),
                episkop_id=self.episkop.id,
                begin_dating=self.begin_dating,
                end_dating=self.end_dating,
                inexact=self.inexact,
                notes=self.notes
            )

    def to_cafedra_of_episkop_dto(self, again_num: int = None):
        return CafedraOfEpiskopDto(
                cafedra=build_title(self.cafedra.header,
                                    self.temp_status, again_num),
                cafedra_id=self.cafedra.id,
                begin_dating=self.begin_dating,
                end_dating=self.end_dating,
                inexact=self.inexact,
                notes=self.notes
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


AllOrmModels = (CafedraOrm, EpiskopOrm, EpiskopCafedraOrm, NoteOrm)

# ----------- Models for HistHierarchyStorage - these are main models


class Cafedra(_HHModel):
    id: Optional[int] = None
    header: str
    is_obn: bool = False
    is_link: bool = False
    text: str
    # subheaders like 'Архиепископы и митрополиты Московские;' stored as str.
    episkops: List[Union['EpiskopOfCafedra', str]] = []
    notes: List['Note'] = []


class _EpiskopCafedraBase(_HHModel):
    begin_dating: Optional[str]
    end_dating: Optional[str]

    temp_status: Optional[str]
    inexact: bool = False


class EpiskopOfCafedra(_EpiskopCafedraBase):
    episkop_id: Optional[int] = None
    episkop: str

    notes: List[int] = []


class Note(_HHModel):
    num: int
    text: str


class Episkop(_HHModel):
    id: Optional[int] = None
    name: str

    cafedras: List['CafedraOfEpiskop'] = []


class CafedraOfEpiskop(_EpiskopCafedraBase):
    cafedra: str
    cafedra_id: Optional[int]

    notes: List[str] = []


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
    name: str
    cafedras: List['CafedraOfEpiskopDto'] = field(default_factory=list)


@dataclass
class CafedraOfEpiskopDto:
    cafedra: str
    cafedra_id: int

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


def build_title(header, temp_status: str, again_num: int):
    if temp_status:
        header = temp_status + ' ' + header
    if again_num is not None and again_num > 1:
        if again_num == 2:
            t = 'паки'
        else:
            t = f'в {again_num}-й раз'
        header += ", " + t
    return header
