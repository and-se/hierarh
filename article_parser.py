from chain import ChainLink
from models import CafedraArticle
from models import Cafedra, EpiskopOfCafedra, Note

import re


class CafedraArticleParser(ChainLink):
    @staticmethod
    def parse_article(art: CafedraArticle) -> Cafedra:
        caf = Cafedra(
                header=art.header,
                is_obn=art.is_obn, is_link=art.is_link,
                text=art.text or ''
        )

        for aep in art.episkops:
            if isinstance(aep, str):
                caf.episkops.append(aep)
                continue

            pp = parse_episkop_row(aep.text)
            if not pp:
                # TODO - we LOOSE this articles data!
                print(f'SKIP EPISKOP {caf.header}:\t{aep.text.strip()}')
                continue

            begin_dating, end_dating, who, inexact = pp

            vy, who, paki, notes = parse_episkop_name(who)
            if not who:
                print(f'\n##########\t\t\tEMPTY EPISKOP {caf.header}:\t{aep.text}\n')  # noqa: E501  TODO
                who = '?'

            epcaf = EpiskopOfCafedra(
                            episkop=who,
                            begin_dating=null_if_empty(begin_dating),
                            end_dating=null_if_empty(end_dating),
                            temp_status=vy,
                            inexact=inexact
                    )
            if notes:
                epcaf.notes = [int(x) for x in notes]

            caf.episkops.append(epcaf)

        caf.notes = [Note(num=x.num, text=x.text) for x in art.notes]
        return caf

    def process(self, s: CafedraArticle):
        pp: Cafedra = self.parse_article(s)
        self.send(pp)


class ParsedCafedraFixer(ChainLink):
    def __init__(self):
        self._moscow_done = False
        self._stashed_caf = None

    def process(self, s: Cafedra):
        # Список сносок общий для статей про Митрополию всея Руссии,
        # которая затем стала Московским патриархатом
        # Проверяем корректность и правим список сносок
        if s.header == 'ВСЕРОССИЙСКАЯ Митрополия Киевская и всея Руссии ' \
                       '(«Митрополия России»), Митрополия Московская ' \
                       'и всея Руссии':
            assert not s.notes, 'У статьи про Митрополию всея Руссии ' \
                                'не должно быть списка сносок'
            assert s.episkops[-1].notes[-1] == 67, \
                'Последняя ссылка на сноску в статье про Митрополию ' \
                'всея Русси должна иметь номер 67'
            self._stashed_caf = s
            return
        elif s.header == 'Московский и всея России Патриархат':
            assert self._stashed_caf is not None, \
                'Есть статья про Московский Патриархат, ' \
                'но не встречена про Митрополия всея Руссии'
            i = 67-1
            assert s.notes[i].num == 67, 'Граница между сносками статей ' \
                                         'определена неверно'

            self._stashed_caf.notes = s.notes[0: i+1]
            assert self._stashed_caf.notes[-1].num == 67
            self.send(self._stashed_caf)

            s.notes = s.notes[i+1:]
            self._stashed_caf = None
            self._moscow_done = True

        self.send(s)

    def finish(self):
        if not self._moscow_done:
            raise Exception('Не обработаны сноски двух статей про Московский '
                            'Патриархат (aka Митрополия Руссии)')


# 10(23)10.1926	–	08(21)04.1932	–	Петр Данилов, паки
episkop_row_parser = re.compile(r'''
    ^(?P<begin>[^\t]*) (\t|–|—)+ (?P<end>[^\t]*) (\t|–|—)+ \s*
    (?P<who>\(?\s*[А-Яа-яЁёN][^\t]+)$''', re.X)


def parse_episkop_row(row):
    row = row.strip()
    if row.startswith('(') and row.endswith(')'):
        inexact = True
        row = row[1:-1]
    else:
        inexact = False
    m = episkop_row_parser.match(row)
    if m:
        return m.group('begin').strip(), m.group('end').strip(), \
               m.group('who').strip(), inexact


def parse_episkop_name(s):
    # remove note
    note = re.compile(
                r'<span\s+class="note"[^>]*>\s*(?P<note_num>\d+)\s*</span>')
    all_notes = [x.group('note_num') for x in note.finditer(s)]
    s = note.sub('', s)

    s = re.match(r'''^\s*(?P<vy> \(?\s* в\s*/\s*у \s* \(?\s*\??\s*\)? \s*\)? )?
                    (?P<who>.*?)
                    (,\s*  (?P<paki>(паки)|(в\s+\d-й\s+раз))   )?
                    \s*$
                  ''', s, re.I | re.X)

    vy = s.group('vy')
    if vy:
        if '?' in vy:
            vy = 'в/y?'
        else:
            vy = 'в/y'

    return (vy, s.group('who').strip(), s.group('paki'), all_notes)


def null_if_empty(s):
    return s if s else None
