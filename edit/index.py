import sys
from peewee import Model, fn, AutoField, TextField, BooleanField, IntegerField

from parsers.episkop import parse_episkop_name_in_cafedra
from parsers.fail import ParseFail

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from edit.storage import HierarhEditStorage


import logging

class EpiskopIndex:
    def __init__(self, db: 'HierarhEditStorage'):
        self.db = db
        self.log = logging.Logger('EpiskopIndex')
        self.log.addHandler(logging.StreamHandler(sys.stdout))

    def find_episkops(self, name, surname=None) -> list['EpiskopIndexOrm']:
        if not name and not surname:
            return []
        if not name:
            raise ValueError('name must be not empty!')
        if name == 'NN' and not surname:
            return []  # NN is unknown man, so two NNs are different
        cond = fn.LOWER_PY(EpiskopIndexOrm.name) == name.lower()
        if surname:
            cond = cond & (fn.LOWER_PY(EpiskopIndexOrm.surname) == surname.lower())
        else:
            cond = cond & EpiskopIndexOrm.surname.is_null()

        ep_qq = EpiskopIndexOrm.select().where(cond).limit(10).namedtuples()

        # print(ep_qq,
        #       _Db.execute_sql(f'EXPLAIN QUERY PLAN {ep_qq}').fetchall())

        return list(ep_qq)

    def rebuild(self):
        self.log.info("Start rebuild episkop index")
        EpiskopIndexOrm.drop_table()
        EpiskopIndexOrm.create_table()
        self.log.info("schema recreated")
        with self.db.atomic():
            for i, c in enumerate(self.db.episkop.iterate(), 1):
                header = c.header()
                parsed = parse_episkop_name_in_cafedra(header)

                name, surname, saint_title = None, None, None

                if not isinstance(parsed, ParseFail):
                    name = parsed.name
                    surname = parsed.surname
                    saint_title = parsed.saint_title
                else:
                    self.log.warn(f"Can't parse {header}: {parsed.text}")
                    # todo log it
                    ...
                EpiskopIndexOrm.insert(doc_key = c.key, header=header, name=name, surname=surname, saint_title=saint_title).execute()

                if i%100 == 0:
                    self.log.info(f"Processed {i} items") 
            
        self.log.info(f"Episkop index built. Total records {i}")



class EpiskopIndexOrm(Model):
    class Meta:
        table_name = 'EpiskopIndex'
    
    id = AutoField()
    header = TextField()
    name = TextField(null=True)
    surname = TextField(null=True)
    saint_title = TextField(null=True, default=None)
    # is_obn = BooleanField(null=False)
    doc_key = IntegerField(null=False)

EpiskopIndexOrm.add_index(EpiskopIndexOrm.name, EpiskopIndexOrm.surname)
