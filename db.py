from chain import Chain, ChainLink

from book_parser import CafedraArticlesFromJson
from article_parser import CafedraArticleParser, ParsedCafedraFixer

import models
from models import CafedraOrm, EpiskopOrm, EpiskopCafedraOrm
from models import Cafedra, ArticleNote
from models import CafedraDto, EpiskopDto, \
                   EpiskopOfCafedraDto, CafedraOfEpiskopDto


import json
import os
import re
from collections import Counter
from typing import Tuple


class HistHierarhStorageBase:
    def get_cafedra_names(self, query: str = '') -> Tuple[int, str]:
        """
        returns tuples (cafedra id, cafedra header)
        """
        raise NotImplementedError()

    def get_episkop_names(self, query: str = '') -> Tuple[int, str]:
        """
        return tuples (episkop id, episkop name)
        """
        raise NotImplementedError()

    def get_cafedra_data(self, key: int) -> CafedraDto:
        raise NotImplementedError()

    def get_episkop_data(self, key: int) -> EpiskopDto:
        raise NotImplementedError()

    def count_cafedra(self, query: str = '') -> int:
        raise NotImplementedError()

    def count_episkop(self, query: str = '') -> int:
        raise NotImplementedError()

    def begin_transaction(self):
        raise NotImplementedError()

    def commit(self):
        raise NotImplementedError()

    def rollback(self):
        raise NotImplementedError()


# ----------------- Peewee ORM Db ----------------

from peewee import fn, SqliteDatabase  # noqa: E402


def get_db(db_name: str):
    db = SqliteDatabase(db_name, {
        'journal_mode': 'wal',
        'cache_size': -1 * 10000,  # 10MB
        'foreign_keys': 1,
        # 'ignore_check_constraints': 0,
        # 'synchronous': 0
    })

    @db.func('LOWER_PY', deterministic=True)
    def lower(s):
        return s.lower() if s else None

    return db

# Global db settings


DbName = 'hierarh.sqlite3'
_Db = get_db(DbName)
_Db.bind(models.AllOrmModels)


class PeeweeHistHierarhStorage(HistHierarhStorageBase):
    @staticmethod
    def create_new_sqlite_db(remove_if_exists):
        db_name = DbName

        if os.path.exists(db_name):
            if remove_if_exists:
                os.remove(db_name)
            else:
                raise Exception(f"Db {db_name} exists")

        db = _Db

        with db.bind_ctx(models.AllOrmModels):
            db.create_tables(models.AllOrmModels)
            # FIXME peewee now doesn't support DETERMINISTIC flag for sqlite functions, so we can't use thim in index on expression.  # noqa: E501
            # But it already fixed on trunk - see https://github.com/coleifer/peewee/issues/2782  # noqa: E501
            _Db.execute_sql('create index if not exists '
                            'EpiskopsLowerPy on episkop(LOWER_PY(name))')

        db.close()

    # Now we use global _Db object bound to AllOrmModels, so all
    # PeeweeHistHierarhStorage objects are automatically connected
    # to one sqlite Db named DbName.
    # If you want manage db connection manually (and possible use
    # different dbs), uncomment this code and use 'with self.ctx():'
    # for all db operations in this class
    # def __init__(self, db: peewee.Database):
    #     self.db = db
    # def ctx(self):
    #     return self.db.bind_ctx(models.AllOrmModels)

    def begin_transaction(self):
        _Db.begin()

    def commit(self):
        _Db.commit()

    def rollback(self):
        _Db.rollback()

    @staticmethod
    def _build_search_condition(query, column):
        words = tuple(x.lower() for x in query.split())

        def word_cond(w):
            return fn.INSTR(fn.LOWER_PY(column), w)

        if words:
            cond = word_cond(words[0])
            for w in words[1:]:
                cond = cond & word_cond(w)
        else:
            cond = None

        return cond

    def _cafedra_q(self, query):
        cond = self._build_search_condition(query, CafedraOrm.header)
        # with self.ctx():
        q = CafedraOrm.select(CafedraOrm.id, CafedraOrm.header)\
            .where(cond).order_by(CafedraOrm.header)
        # print(q, _Db.execute_sql(f'EXPLAIN QUERY PLAN {q}').fetchall())
        return q

    def get_cafedra_names(self, query: str = ''):
        q = self._cafedra_q(query).tuples()
        for r in q:
            yield r

    def count_cafedra(self, query: str = ''):
        q = self._cafedra_q(query).count()
        return q

    def _episkop_q(self, query):
        cond = self._build_search_condition(query, EpiskopOrm.name)
        q = EpiskopOrm.select(EpiskopOrm.id, EpiskopOrm.name) \
                      .where(cond).order_by(EpiskopOrm.name)
        return q

    def get_episkop_names(self, query: str = ''):
        q = self._episkop_q(query)
        for r in q.tuples():
            yield r

    def count_episkop(self, query: str = ''):
        q = self._episkop_q(query)
        return q.count()

    def get_cafedra_data(self, key: int) -> CafedraDto:
        c = CafedraOrm.select(CafedraOrm.article_json) \
                      .where(CafedraOrm.id == key).get_or_none()
        if c:
            return CafedraDto.from_dict(json.loads(c.article_json))

    def get_episkop_data(self, key: int) -> EpiskopDto:
        ep = EpiskopOrm.get(key)

        epv = EpiskopDto(name=ep.name)

        cnt = Counter()
        for caf in ep.cafedras.order_by(EpiskopCafedraOrm.begin_year):
            cnt.update([caf.cafedra.id])
            ecv: CafedraOfEpiskopDto = caf.to_cafedra_of_episkop_dto(
                                            cnt[caf.cafedra.id]
                                       )
            epv.cafedras.append(ecv)

        return epv

    def upsert_cafedra(self, caf: Cafedra):
        caf_orm = CafedraOrm.create(
            header=caf.header, is_obn=caf.is_obn,
            is_link=caf.is_link,  # text=caf.text,
            article_json="TODO")

        # TODO use Cafedra object, don't use Dto
        cafjson = models.CafedraDto(
            header=caf.header,
            is_obn=caf.is_obn, is_link=caf.is_link,
            text=caf.text
        )

        cnt = Counter()
        for i, ep in enumerate(caf.episkops, 1):
            if isinstance(ep, str):
                cafjson.episkops.append(ep)
                continue  # TODO now table subheaders are skipped in db...

            ep_orm = EpiskopOrm.select(EpiskopOrm.id, EpiskopOrm.name) \
                               .where(
                                     fn.LOWER_PY(EpiskopOrm.name) ==
                                     ep.episkop.lower()
                                ) \
                               .get_or_none()
            if not ep_orm:
                ep_orm = EpiskopOrm.create(name=ep.episkop)

            cnt.update([ep_orm.id])

            epcaf = EpiskopCafedraOrm.create(
                            episkop=ep_orm, cafedra=caf_orm,
                            begin_dating=null_if_empty(ep.begin_dating),
                            begin_year=try_extract_year(ep.begin_dating),
                            end_dating=null_if_empty(ep.end_dating),
                            temp_status=ep.temp_status,
                            episkop_num=i,
                            inexact=ep.inexact
            )

            epjson: EpiskopOfCafedraDto = \
                epcaf.to_episkop_of_cafedra_dto(cnt[ep.episkop_id])

            if ep.notes:
                epjson.episkop += ' '.join([
                        f'<span class="note" data-note="{i}">{i}</span>'
                        for i in ep.notes
                ])

            cafjson.episkops.append(epjson)

        cafjson.notes = [ArticleNote(num=x.num, text=x.text)
                         for x in caf.notes]  # TODO now no notes in db

        caf_orm.article_json = json.dumps(cafjson.to_dict(),
                                          ensure_ascii=False, indent=4)
        caf_orm.save()


# -------------- End Peewee -------------


class CafedraDbImporter(ChainLink):
    def __init__(self, db: HistHierarhStorageBase):
        self.db = db
        self.db.begin_transaction()

    def process(self, s: Cafedra):
        self.db.upsert_cafedra(s)

    def finish(self):
        self.db.commit()


def null_if_empty(s):
    return s if s else None


def try_extract_year(s):
    if s:
        m = re.match(r'.*\b(\d{3,4})$', s)
        if m:
            return int(m.group(1))


if __name__ == "__main__":
    PeeweeHistHierarhStorage.create_new_sqlite_db(remove_if_exists=True)
    db = PeeweeHistHierarhStorage()

    ch = Chain(CafedraArticlesFromJson()) \
        .add(CafedraArticleParser()) \
        .add(ParsedCafedraFixer()) \
        .add(CafedraDbImporter(db))

    ch.process('articles.json')

    print("Created cafedras:", db.count_cafedra())
    print("Created episkops:", db.count_episkop())

    # build_db(db_name = DbName, remove_if_exists=True)
    # print("Created cafedras:", models.Cafedra.select().count())
    # print("Created episkops:", models.Episkop.select().count())
