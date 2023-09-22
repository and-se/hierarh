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
    # episkops in cafedra table - list of EpiskopInCafedra objects.
    # subheaders like 'Архиепископы и митрополиты Московские;' stored as str.
    episkops: List[Union['EpiskopInCafedra', str]] = field(default_factory = list)
    notes: List['ArticleNote'] = field(default_factory = list)

    @staticmethod
    def from_dict(d):
        res = CafedraArticle(**d)
        for i in range(len(res.episkops)):
            ep = res.episkops[i]
            if isinstance(ep, dict):
                res.episkops[i] = EpiskopInCafedra(**ep)

        for i in range(len(res.notes)):
            nt = res.notes[i]
            if isinstance(nt, dict):
                res.notes[i] = ArticleNote(**nt)

        return res

    def to_dict(self):
        return asdict(self)
                

@dataclass
class EpiskopInCafedra:
    begin_dating: str = None
    end_dating: str = None
    who: str = None
    unparsed_data: str = None


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
    id = AutoField()
    episkop = ForeignKeyField(Episkop, backref='cafedras', index=True)
    cafedra = ForeignKeyField(Cafedra, backref='episkops', index=True)
    
    begin_dating = TextField(null=True)
    begin_year = IntegerField(null=True)           
    end_dating = TextField(null=True)

    temp_status = TextField(null=True)  # в/у в/у?
    again_status = TextField(null=True)  # паки, в 3-й раз и т.д.
    # TODO вообще говоря опираться здесь на текст смысла нет, т.к. там не всегда это корректно заполнено. Лучше считать самим.

    def build_cafedra_of_episkop_title(self):
        res = self.cafedra.header
        if self.temp_status:
            res = self.temp_status + ' ' + res
        if self.again_status:
            res += ', ' + self.again_status

        return res
    


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
class EpiskopView:
    name: str
    cafedras: List['CafedraOfEpiskopView'] = field(default_factory = list)

@dataclass
class CafedraOfEpiskopView:
    cafedra: str
    cafedra_id: int
    
    begin_dating: str
    end_dating: str


