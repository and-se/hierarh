import sys
from peewee import Model, fn, AutoField, TextField, BooleanField, IntegerField

from parsers.episkop import parse_episkop_name_in_cafedra
from parsers.fail import ParseFail

from edit.text_view import EpiskopView

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from edit.storage import HierarhEditStorage

import logging


class EpiskopIndex:
    LOG_NAME = 'hierarh.EpiskopIndex'

    def __init__(self, db: 'HierarhEditStorage'):
        self.db = db
        self.log = logging.getLogger(self.LOG_NAME)
        
    def find_by_fields(self, name, surname=None, begin_year=None, end_year=None) -> list['EpiskopIndexOrm']:
        if not name and not surname:
            return []
        if not name:
            raise ValueError('name must be not empty!')
        if name == 'NN' and not surname:
            return []  # NN is unknown man, so two NNs are different
        #cond = fn.LOWER_PY(EpiskopIndexOrm.name) == name.lower()  # точное совпадение
        cond = fn.INSTR(fn.LOWER_PY(EpiskopIndexOrm.name), name.lower())  # по подстроке
        # cond = fn.INSTR(fn.LOWER_PY(EpiskopIndexOrm.name), name.lower()) == 1 # с начала строки
        if surname:
            #cond = cond & (fn.LOWER_PY(EpiskopIndexOrm.surname) == surname.lower())  # точное совпадение
            cond = cond & (fn.INSTR(fn.LOWER_PY(EpiskopIndexOrm.surname), surname.lower()))  # по подстроке
            #cond = cond & (fn.INSTR(fn.LOWER_PY(EpiskopIndexOrm.surname), surname.lower()) == 1) # с начала строки
        else:
            cond = cond & EpiskopIndexOrm.surname.is_null()

        if begin_year or end_year:
            if not begin_year:
                begin_year = end_year
            elif not end_year:
                end_year = begin_year
            
            if begin_year > end_year:
                raise ValueError("begin_year must be <= end_year")
            # разрешаем зазор в 5 лет от означенного интервала
            # кроме приблизительного совпадения это позволяет
            # обработать интервалы в индексе, где начало=конец
            begin_year -= 5
            end_year += 5

            cond = cond & (
                # BAD: если в индексе у епископа лет нет, просто берём его в результат
                #(EpiskopIndexOrm.min_year.is_null() & EpiskopIndexOrm.max_year.is_null()) |

                # требуем пересечение между запрошенным отрезком лет и годами епископа в индексе
                # если у епископа нету лет, он не попадёт в результат
                ((EpiskopIndexOrm.min_year <= end_year) & (EpiskopIndexOrm.max_year >= begin_year))
                )

        ep_qq = EpiskopIndexOrm.select().where(cond).limit(10).namedtuples()

        #from storage import EditDb
        #print(ep_qq, "PLAN:", EditDb.execute_sql(f'EXPLAIN QUERY PLAN {ep_qq}').fetchall(), '\n\n\n')
        #raise ValueError()

        return list(ep_qq)

    def rebuild(self):
        self.log.info("Start rebuild episkop index")
        EpiskopIndexOrm.drop_table()
        EpiskopIndexOrm.create_table()
        self.log.info("schema recreated")
        with self.db.atomic():
            for i, c in enumerate(self.db.episkop.iterate(), 1):
                c = EpiskopView(c)
                header = c.header
                parsed = parse_episkop_name_in_cafedra(header)

                name, surname, saint_title = None, None, None

                if not isinstance(parsed, ParseFail):
                    name = parsed.name
                    surname = parsed.surname
                    saint_title = parsed.saint_title
                else:
                    self.log.warning(f"Can't parse {header}")
                    ...

                years = list(x.begin_year for x in c.cafedras if x.begin_year) + \
                        list(x.end_year for x in c.cafedras if x.end_year)
                
                min_year = min(years, default=None)
                max_year = max(years, default=None)

                # Либо никаких лет, либо должны быть оба конца (пусть и равные)
                assert (min_year is not None and max_year is not None) or \
                       (min_year is None and max_year is None)
                
                EpiskopIndexOrm.insert(doc_key = c.key, 
                            saint_title=saint_title,
                            header=header, name=name, surname=surname,
                            min_year = min_year,
                            max_year = max_year,
                            is_obn = c.is_obn
                ).execute()

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
    is_obn = BooleanField(null=False)
    min_year = IntegerField(null=True)
    max_year = IntegerField(null=True)

    doc_key = IntegerField(null=False)

#EpiskopIndexOrm.add_index(EpiskopIndexOrm.name, EpiskopIndexOrm.surname, name="IDX_episkop")

EpiskopIndexOrm.add_index(fn.LOWER_PY(EpiskopIndexOrm.name), fn.LOWER_PY(EpiskopIndexOrm.surname), name="IDX_episkop_name")
EpiskopIndexOrm.add_index(EpiskopIndexOrm.max_year, name="IDX_episkop_max_year")
EpiskopIndexOrm.add_index(EpiskopIndexOrm.min_year, name="IDX_episkop_min_year")
