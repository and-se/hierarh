from dataclasses import dataclass, field, asdict
from typing import Union, List, Dict, Tuple, Union

# Models for book parser of chapter 'Списки иерархов по кафедрам'

@dataclass
class CafedraArticle:
    header: str = None
    is_obn: bool = False
    is_link: bool = False
    start_line: int = None

    text: str = None
    # episkops in cafedra table - list of ArticleEpiskopRow objects.
    # subheaders like 'Архиепископы и митрополиты Московские;' stored as str.
    episkops: List[Union['ArticleEpiskopRow', str]] = field(default_factory = list)
    notes: List['ArticleNote'] = field(default_factory = list)

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
class ArticleEpiskopRow:  # TODO save here only unparsed_data and parse fields on DB import?
    #begin_dating: str = None
    #end_dating: str = None
    #who: str = None
    text: str = None


@dataclass
class ArticleNote:
    num: int
    text: str


# Db models using Peewee ORM

from peewee import Model, AutoField, TextField, BooleanField, ForeignKeyField, IntegerField

class Cafedra(Model):
    id = AutoField()
    header = TextField(index=True)
    is_obn = BooleanField()
    is_link = BooleanField()
    # text = TextField(null=True)  # ?? for links
    article_json = TextField()


class Episkop(Model):
    id = AutoField()
    name = TextField(index=True)


class EpiskopCafedra(Model):
    class Meta:
        legacy_table_names = False

    id = AutoField()
    episkop = ForeignKeyField(Episkop, backref='cafedras', index=True)
    cafedra = ForeignKeyField(Cafedra, backref='episkops', index=True)

    # sequence number of episkop for self.cafedra
    episkop_num = IntegerField()

    # sequence number of cafedra for self.episkop
    # cafedra_num = IntegerField()

    begin_dating = TextField(null=True)
    begin_year = IntegerField(null=True)
    end_dating = TextField(null=True)

    temp_status = TextField(null=True)  # в/у в/у?

class Note(Model):
    """
    Note linked to cafedra article
    """
    id = AutoField()
    text = TextField()

    cafedra_id = ForeignKeyField(Cafedra, backref='text_notes', index=True)
    text_position = IntegerField(null=True)
    """Optional position of note in cafedra article text"""

    episkop_cafedra_id = ForeignKeyField(EpiskopCafedra, backref='notes', null=True, index=True)
    """For notes linked to episkops table of cafedra article"""



AllDbModels = (Cafedra, Episkop, EpiskopCafedra, Note)

############ Presentation models for flask templates ########

@dataclass
class CafedraDto:
    header: str

    is_obn: bool = False
    is_link: bool = False

    text: str = None

    # subheaders like 'Архиепископы и митрополиты Московские;' stored as str.
    episkops: List[Union['EpiskopCafedraDto', str]] = field(default_factory = list)
    notes: List['ArticleNote'] = field(default_factory = list)

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
    cafedras: List['EpiskopOfCafedraDto'] = field(default_factory = list)

@dataclass
class CafedraOfEpiskopDto:
    cafedra: str
    cafedra_id: int

    begin_dating: str
    end_dating: str

    @staticmethod
    def from_db_model(data: EpiskopCafedra, again_num: int = None):
        return CafedraOfEpiskopDto(
                cafedra = build_title(data.cafedra.header, data.temp_status, again_num),
                cafedra_id = data.cafedra.id,
                begin_dating = data.begin_dating,
                end_dating = data.end_dating
            )


@dataclass
class EpiskopOfCafedraDto:
    episkop: str
    episkop_id: str

    begin_dating: str
    end_dating: str

    @staticmethod
    def from_db_model(data: EpiskopCafedra, again_num: int = None):
        return EpiskopOfCafedraDto(
                episkop = build_title(data.episkop.name, data.temp_status, again_num),
                episkop_id = data.episkop.id,
                begin_dating = data.begin_dating,
                end_dating = data.end_dating
            )


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
