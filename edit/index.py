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

# Держим постоянное соединение с БД в памяти, чтобы данные на памяти не исчезли
import sqlite3
__sqlite_mem_holder = sqlite3.connect('file:/indx?vfs=memdb', uri=True)

@MEM_CACHE.func('LOWER_PY', deterministic=True)
def lower(s):
    return s.lower() if isinstance(s, str) else None

MEM_LOCK = threading.Lock()

class EpiskopIndex:
    LOG_NAME = 'hierarh.EpiskopIndex'

    def __init__(self, db: 'HierarhEditStorage', copy_to_ram=True):
        self.db = db
        self.log = logging.getLogger(self.LOG_NAME)
        # self.log.setLevel(logging.INFO)
        # self.log.addHandler(logging.StreamHandler())
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
                       is_obn: bool | None = None) -> list[tuple]:
        if not name and not surname:
            return []
        if not name:
            raise ValueError('name must be not empty!')
        if name == 'NN' and not surname:
            return []  # NN is unknown man, so two NNs are different
        
        query = self.get_builder() \
                    .where_name(name, surname) \
                    .where_obn(is_obn) \
                    .where_saint_title(saint_title) \
                    .where_years(begin_year, end_year) \
                    .where_cafedra(cafedra) \
                    .limit(10)

        return list(query.run())
        
    def find_by_header(self, query, clear_input=True):
        """
        Поиск по заголовку на основе вхождения слов из запроса

        query - что ищем
        clear_input - очистить входной запрос от обычно мешающих поиску слов и знаков препинания
        - сейчас остаются только слова с большой буквы, за исключением римских номеров и чинов святости.
        """
        q = self.get_builder() \
            .where_header(query, clear_input) \
            .order_by(self.orm_model.header) \
            .limit(10)
        
        return list(q.run())
    
    def get_by_dockey(self, key):
        return self.orm_model.get_or_none(self.orm_model.doc_key == key)

    
    def get_builder(self):
        return EpiskopQueryBuilder(self.orm_model)
    
    def rebuild(self, progress_sender = lambda x: None):
        self.log.info("Start rebuild episkop index")
        progress_sender('Start rebuild episkop index')

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
                    progress_sender(f"Processed {i} items")
        
        total = i

        if self.mem_cache:
            with MEM_LOCK:
                progress_sender("Update in-memory index")
                self._init_in_memory()
                progress_sender("in-memory index updated")

        progress_sender(f"Episkop index built. Total records {total}")
        self.log.info(f"Episkop index built. Total records {total}")
        



class EpiskopQueryBuilder:
    def __init__(self, orm: 'EpiskopIndexOrm'):
        self.orm = orm
        self.cond = True
        self._offset = None
        self._limit = None
        self._sort = (self.orm.header, )

    def append_cond(self, condition):
        self.cond = self.cond & condition

    
    def where_name(self, name, surname=None) -> 'EpiskopQueryBuilder':
        """
        Поиск по имени и фамилии

        Если имя не задано, оно не учитывается.
        Если фамилия не задана, ищуется записи с пустой фамилией
        """
        if not name and not surname:
            raise ValueError("Name and surname can't be None together!")
        
        if name:
            self.append_cond(fn.INSTR(fn.LOWER_PY(self.orm.name), name.lower()))

        if surname:
            self.append_cond(fn.INSTR(fn.LOWER_PY(self.orm.surname), surname.lower()))            
        else:
            self.append_cond(self.orm.surname.is_null())
        
        return self
    
    def where_obn(self, is_obn: bool | None):
        """
        Фильтр по признаку обновленчества
        """
        if is_obn is not None:
            self.append_cond(self.orm.is_obn == is_obn)
        return self

    def where_saint_title(self, saint_title):
        if saint_title:
            self.append_cond(fn.LOWER_PY(self.orm.saint_title) == fn.LOWER_PY(saint_title.strip()))
        return self
    
    def where_cafedra(self, cafedra):
        if cafedra:
            self.append_cond(fn.INSTR(fn.LOWER_PY(self.orm.cafedras), cafedra.lower()))
        return self

    def where_years(self, begin_year, end_year):
        if not begin_year and not end_year:
            return self
        
        if not begin_year:
            begin_year = end_year
        elif not end_year:
            end_year = begin_year
        
        if begin_year > end_year:
            raise ValueError("begin_year must be <= end_year")
        
        self.append_cond(                
                # требуем пересечение между запрошенным отрезком лет и годами епископа в индексе
                # если у епископа нету лет, он не попадёт в результат
                ((self.orm.min_year <= end_year) & (self.orm.max_year >= begin_year))
        )
        return self
    
    def where_header(self, query, clear_input=True):
        if clear_input:
            # Оставляем только слова с большой буквы (за исключением некоторых)
            words = [x for x in re.split('[^а-яёa-z-]+', query, flags=re.I) 
                    if x and x[0].isupper() and x not in ('I', 'II', 'III', 'IV', 'V', 'Святой', 'Святитель')]
            query = ' '.join(words)
        
        if query:
            self.append_cond(orm_all_words_search_condition(query, self.orm.header))

        return self

    def order_by(self, *columns):
        self._sort = columns
        return self

    def offset(self, skip):
        self._offset = skip
        return self

    def limit(self, count):
        self._limit = count
        return self

    def run(self):
        q = self.orm.select().where(self.cond)
        if self.offset:
            q = q.offset(self._offset)
        if self.limit:
            q = q.limit(self._limit)
        
        if self._sort:
            q.order_by(*self._sort)
        
        #from storage import EditDb
        #print(q, "PLAN:", EditDb.execute_sql(f'EXPLAIN QUERY PLAN {q}').fetchall(), '\n\n\n')
        #raise ValueError()

        return q.namedtuples()


class EpiskopIndexOrm(Model):
    class Meta:
        table_name = 'EpiskopIndex'
    
    index_item_id = AutoField()
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
