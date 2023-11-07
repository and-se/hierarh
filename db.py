from chain import Chain, ChainLink

from book_parser import CafedraArticlesFromJson
from article_parser import CafedraArticleParser, ParsedCafedraFixer

import models
from models import CafedraOrm, EpiskopOrm, EpiskopCafedraOrm, NoteOrm
from models import Cafedra, ArticleNote, EpiskopInfo
from models import CafedraDto, EpiskopDto, \
                   EpiskopOfCafedraDto, CafedraOfEpiskopDto

import human


import json
import os
from collections import Counter
from typing import Tuple, Iterable


class HistHierarhStorageBase:
    def get_cafedra_names(self, query: str = '') \
                -> Iterable[Tuple[int, str, bool]]:
        """
        returns tuples (cafedra id, cafedra header, is obn)
        """
        raise NotImplementedError()

    def get_episkop_names(self, query: str = '') \
            -> Iterable[Tuple[int, str, bool]]:
        """
        returns tuples (episkop id, episkop name, is obn)
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
        q = CafedraOrm.select(CafedraOrm.id,
                              CafedraOrm.header,
                              CafedraOrm.is_obn) \
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
        cond = self._build_search_condition(query, EpiskopOrm.header)
        q = EpiskopOrm.select(EpiskopOrm.id,
                              EpiskopOrm.header,
                              EpiskopOrm.is_obn) \
                      .where(cond) \
                      .order_by(EpiskopOrm.name, EpiskopOrm.surname)
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

        epv = EpiskopDto(header=ep.header, is_obn=ep.is_obn)

        cnt = Counter()
        for caf in ep.cafedras.order_by(
                            EpiskopCafedraOrm.estimated_begin_date):
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

            ep.episkop: EpiskopInfo
            is_obn = caf.is_obn

            # fixme: now we possibly merge people with same name+surname
            ep_orm = self.find_episkop(ep.episkop.name, ep.episkop.surname)
            if not ep_orm:
                ep_orm = EpiskopOrm.create(header=ep.episkop
                                           .get_header(is_obn),
                                           name=ep.episkop.name,
                                           surname=ep.episkop.surname,
                                           saint_title=ep.episkop.saint_title,
                                           # todo check is it always correct?
                                           is_obn=is_obn
                                           )

            ep.episkop.id = ep_orm.id
            # Отдельно считаем количество раз для в/у и "настоящего"
            cnt[(ep.episkop.id, bool(ep.temp_status))] += 1

            beg = ep.begin_dating
            end = ep.end_dating

            EpiskopCafedraOrm.create(
                episkop=ep_orm, cafedra=caf_orm,
                begin_dating=beg.dating if beg else None,
                estimated_begin_date=beg.estimated_date if beg
                else None,
                end_dating=end.dating if end else None,
                temp_status=ep.temp_status,
                episkop_num=i,
                inexact=ep.inexact
            )

            epjson: EpiskopOfCafedraDto = \
                ep.to_episkop_of_cafedra_dto(cnt[(ep.episkop.id,
                                             bool(ep.temp_status))], is_obn)

            if ep.notes:
                epjson.episkop += ' '.join([
                        f'<span class="note" data-note="{i}">{i}</span>'
                        for i in ep.notes
                ])

            epjson.notes = [ArticleNote(num=note.num, text=note.text) 
                            for note in caf.notes 
                            if note.num in ep.notes]
            caf.notes = [note for note in caf.notes if note.num not in ep.notes]

            cafjson.episkops.append(epjson)

        cafjson.notes = [ArticleNote(num=x.num, text=x.text)
                         for x in caf.notes]  # TODO now no notes in db

        caf_orm.article_json = json.dumps(cafjson.to_dict(),
                                          ensure_ascii=False, indent=4)
        caf_orm.save()

        for note in caf.notes:
            note_orm = NoteOrm.create(
                text=note.text,
                cafedra_id=caf_orm.id,
                #TODO episkop_cafedra_id= 
            )
            note_orm.save()


    def find_episkop(self, name, surname=None) -> EpiskopOrm | None:
        if not name:
            raise ValueError('name must be not empty!')
        if name == 'NN' and not surname:
            return None  # NN is unknown man, so two NNs are different
        cond = fn.LOWER_PY(EpiskopOrm.name) == name.lower()
        if surname:
            cond = cond & (fn.LOWER_PY(EpiskopOrm.surname) == surname.lower())
        else:
            cond = cond & EpiskopOrm.surname.is_null()

        ep_qq = EpiskopOrm.select().where(cond)

        # print(ep_qq,
        #       _Db.execute_sql(f'EXPLAIN QUERY PLAN {ep_qq}').fetchall())

        return ep_qq.get_or_none()


# -------------- End Peewee -------------


class CafedraDbImporter(ChainLink):
    def __init__(self, db: HistHierarhStorageBase):
        self.db = db
        self.db.begin_transaction()

    @human.show_exception
    def process(self, s: Cafedra):
        self.db.upsert_cafedra(s)

    def finish(self):
        self.db.commit()


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
