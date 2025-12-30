import re
from peewee import Model, fn, AutoField, TextField, BooleanField, IntegerField

from db import orm_all_words_search_condition
from parsers.episkop import parse_episkop_name_in_cafedra
from parsers.fail import ParseFail

from edit.text_view import EpiskopView

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from edit.storage import HierarhEditStorage

import logging

import threading

from peewee import SqliteDatabase
MEM_CACHE = SqliteDatabase('file:/indx?vfs=memdb', uri=True)

@MEM_CACHE.func('LOWER_PY', deterministic=True)
def lower(s):
    return s.lower() if isinstance(s, str) else None

MEM_LOCK = threading.Lock()

class EpiskopIndex:
    LOG_NAME = 'hierarh.EpiskopIndex'

    def __init__(self, db: 'HierarhEditStorage', copy_to_ram=True):
        self.db = db
        self.log = logging.getLogger(self.LOG_NAME)
        self.mem_cache = copy_to_ram

        with MEM_LOCK:
            if self.mem_cache:
                self._init_in_memory()

    def _init_in_memory(self):
        #logger = logging.getLogger('peewee')
        #logger.setLevel(logging.DEBUG)
        #logger.addHandler(logging.StreamHandler())
            
        if not MemItem.table_exists():
            self.log.info("Start copy EpiskopIndex into memory")
            MemItem.create_table()
            with MEM_CACHE.atomic():
                for c in EpiskopIndexOrm.select().dicts():
                    MemItem.create(**c)
            
            self.log.info(f"In-memory index created. Total records {MemItem.select().count()}")

    @property
    def orm_model(self):
        return MemItem if self.mem_cache else EpiskopIndexOrm
    

    def find_by_fields(self, name=None, surname=None, 
                       begin_year=None, end_year=None,
                       cafedra: str | None = None,
                       saint_title=None,
                       is_obn: bool | None = None) -> list['EpiskopIndexOrm']:
        OrmModel = self.orm_model
        if not name and not surname:
            return []
        if not name:
            raise ValueError('name must be not empty!')
        if name == 'NN' and not surname:
            return []  # NN is unknown man, so two NNs are different
        #cond = fn.LOWER_PY(EpiskopIndexOrm.name) == name.lower()  # точное совпадение
        cond = fn.INSTR(fn.LOWER_PY(OrmModel.name), name.lower())  # по подстроке
        # cond = fn.INSTR(fn.LOWER_PY(EpiskopIndexOrm.name), name.lower()) == 1 # с начала строки
        if surname:
            #cond = cond & (fn.LOWER_PY(EpiskopIndexOrm.surname) == surname.lower())  # точное совпадение
            cond = cond & (fn.INSTR(fn.LOWER_PY(OrmModel.surname), surname.lower()))  # по подстроке
            #cond = cond & (fn.INSTR(fn.LOWER_PY(EpiskopIndexOrm.surname), surname.lower()) == 1) # с начала строки
        else:
            cond = cond & OrmModel.surname.is_null()

        if is_obn is not None:
            cond = cond & (OrmModel.is_obn == is_obn)
        
        if saint_title:
            cond = cond & (fn.LOWER_PY(OrmModel.saint_title) == fn.LOWER_PY(saint_title.strip()))

        if begin_year or end_year:
            if not begin_year:
                begin_year = end_year
            elif not end_year:
                end_year = begin_year
            
            if begin_year > end_year:
                raise ValueError("begin_year must be <= end_year")
            
            # OLD - фактически качество поиска только ухудшало
            # разрешаем зазор в 5 лет от означенного интервала
            # кроме приблизительного совпадения это позволяет
            # обработать интервалы в индексе, где начало=конец
            #begin_year -= 5
            #end_year += 5

            cond = cond & (
                # BAD: если в индексе у епископа лет нет, просто берём его в результат
                #(EpiskopIndexOrm.min_year.is_null() & EpiskopIndexOrm.max_year.is_null()) |

                # требуем пересечение между запрошенным отрезком лет и годами епископа в индексе
                # если у епископа нету лет, он не попадёт в результат
                ((OrmModel.min_year <= end_year) & (OrmModel.max_year >= begin_year))
                )

        if cafedra:
            cond = cond & (fn.INSTR(fn.LOWER_PY(OrmModel.cafedras), cafedra.lower()))

        ep_qq = OrmModel.select().where(cond).limit(10).namedtuples()

        return list(ep_qq)
    
        #from storage import EditDb
        #print(ep_qq, "PLAN:", EditDb.execute_sql(f'EXPLAIN QUERY PLAN {ep_qq}').fetchall(), '\n\n\n')
        #raise ValueError()

        #res = list(ep_qq)
        #if cafedra:
        #    res = [c for c in res if cafedra.lower() in c.cafedras.lower()]

        #return res[:10]
    
    def find_by_header(self, query, clear_input=True):
        """
        Поиск по заголовку на основе вхождения слов из запроса

        query - что ищем
        clear_input - очистить входной запрос от обычно мешающих поиску слов и знаков препинания
        - сейчас остаются только слова с большой буквы, за исключением римским номеров и чинов святости.
        """
        OrmModel = self.orm_model
        if clear_input:
            # Оставляем только слова с большой буквы (и исключением некоторых)
            words = [x for x in re.split('[^а-яёa-z-]+', query, flags=re.I) 
                    if x and x[0].isupper() and x not in ('I', 'II', 'III', 'IV', 'V', 'Святой', 'Святитель')]
            query = ' '.join(words)

        r = OrmModel.select() \
            .where(orm_all_words_search_condition(query, OrmModel.header)) \
            .order_by(OrmModel.header).limit(10).namedtuples()
        
        return r

    def rebuild(self):
        self.log.info("Start rebuild episkop index")
        EpiskopIndexOrm.drop_table()
        if self.mem_cache:
            MemItem.drop_table()
        EpiskopIndexOrm.create_table()
        self.log.info("schema recreated")
        with self.db.atomic():
            for i, c in enumerate(self.db.episkop.iterate(), 1):
                c = EpiskopView(c)
                header = c.header
                parsed = parse_episkop_name_in_cafedra(header)
                caf_names = set()

                name, surname, saint_title = None, None, None

                if not isinstance(parsed, ParseFail):
                    name = parsed.name
                    surname = parsed.surname
                    saint_title = parsed.saint_title
                else:
                    self.log.warning(f"Can't parse {header}")
                    ...
                
                years = []
                for caf in c.cafedras:
                    for year in caf.get_min_max_year():
                        if year:
                            years.append(year)
                    caf_names.add(caf.name.strip())

                min_year = min(years, default=None)
                max_year = max(years, default=None)

                # Либо никаких лет, либо должны быть оба конца (пусть и равные)
                assert (min_year is not None and max_year is not None) or \
                       (min_year is None and max_year is None)
                
                if min_year and max_year:
                    if abs(max_year - min_year) > 100:
                        self.log.warning(f'Слишком большой интервал лет {min_year, max_year} в статье епископа {c}', )
                else:
                    assert min_year is None and max_year is None, \
                    'Должно быть либо оба года, либо ни одного'
                
                EpiskopIndexOrm.insert(doc_key = c.key, 
                            saint_title=saint_title,
                            header=header, name=name, surname=surname,
                            min_year = min_year,
                            max_year = max_year,
                            is_obn = c.is_obn,
                            cafedras = ' | '.join(sorted(caf_names))
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
    min_year = IntegerField(null=True, index=True)
    max_year = IntegerField(null=True, index=True)
    cafedras = TextField()

    doc_key = IntegerField(null=False)

class MemItem(EpiskopIndexOrm):
    class Meta:
        database = MEM_CACHE

#EpiskopIndexOrm.add_index(EpiskopIndexOrm.name, EpiskopIndexOrm.surname, name="IDX_episkop")

EpiskopIndexOrm.add_index(fn.LOWER_PY(EpiskopIndexOrm.name), fn.LOWER_PY(EpiskopIndexOrm.surname), name="IDX_episkop_name")
MemItem.add_index(fn.LOWER_PY(MemItem.name), fn.LOWER_PY(MemItem.surname), name="IDX_episkop_name")
