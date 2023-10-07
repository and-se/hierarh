from chain import ChainLink, Chain
from models import CafedraArticle
from models import Cafedra, EpiskopOfCafedra, Note

import re
from dataclasses import dataclass
from typing import Tuple
from pyparsing import Literal, Regex, Opt, ParseException


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

            pp = parse_episkop_row_old(aep.text)
            if not pp:
                # TODO - we LOOSE this articles data!
                print(f'SKIP EPISKOP {caf.header}:\t{aep.text.strip()}')
                continue

            begin_dating, end_dating, who, inexact = pp

            vy, who, paki, notes = parse_episkop_name_old(who)
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


def parse_episkop_row_old(row):
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


def parse_episkop_name_old(s):
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


# ------------ Parser for Episkop row in table of cafedra article -------


@dataclass
class ParsedDating:
    dating: str
    year: int
    month: int = None
    day: int = None
    prefix: str = None


@dataclass
class ParsedEpiskopName:
    text: str
    name: str
    number_after_name: str
    surname: str
    number_after_surname: str

    dating_in_brackets: str


@dataclass
class ParseFail:
    text: str
    code: str
    error: any


@dataclass
class ParsedEpiskopRow:
    begin: ParsedDating
    end: ParsedDating
    who: ParsedEpiskopName
    inexact: bool

    def has_fails(self):
        return True in map(lambda x: isinstance(x, ParseFail), [self.begin, self.end, self.who])


def parse_episkop_row(s) -> ParsedEpiskopRow | ParseFail:
    div = divide_episkop_row(s)
    if isinstance(div, ParseFail):
        return div

    begin, end, who, inexact = div
    who, notes = extract_notes(who)

    begin = parse_dating(begin) if begin else None
    end = parse_dating(end) if end else None
    who = parse_episkop_name(who)

    return ParsedEpiskopRow(begin, end, who, inexact)


def divide_episkop_row(s) -> Tuple[str, str, str, bool]:
    s = s.strip()
    inexact = False
    if s.startswith('(') and s.endswith(')'):
        inexact = True
        s = s[1:-1]
    l = re.split(r'[–—]\s', s)  # noqa: E741

    if len(l) != 3:
        return ParseFail(s, 'DivideFail', f"Expected 3 items, but got {len(l)} for '{s}'")
    return l[0].strip(), l[1].strip(), l[2].strip(), inexact


note_re = re.compile(
                r'<span\s+class="note"[^>]*>\s*(?P<note_num>\d+)\s*</span>')


def extract_notes(s) -> Tuple[str, list]:
    # remove note
    all_notes = [x.group('note_num') for x in note_re.finditer(s)]
    s = note_re.sub('', s)
    return s, all_notes


brackets = (Literal('(') + ... + ')').suppress()
dot_or_brackets = (Literal('.') | (brackets + Opt('.'))).suppress()

Day = Regex(r'30 | 31 | ([12]\d) | (0?[1-9])', flags=re.X)('day')
Month = Regex(r'1[012] | (0?[1-9])', flags=re.X)('month')
Year = Regex(r'(2[01]\d\d) | (1\d{3}) | \d{2,3} ', flags=re.X)('year')


for t in (Day, Month, Year):
    t.set_parse_action(lambda tok: int(tok[0]))

dating_prefix = Regex(r'(не\s+)?[а-я]+(\.?)')('prefix')

Dating = Opt(dating_prefix) + (\
             # weird pyparsing Opt()!!!
             (Day + dot_or_brackets + Month + dot_or_brackets + Year) | \
             (Month + dot_or_brackets + Year) | Year
         ) + Opt(brackets).suppress()


def parse_dating(s) -> ParsedDating | ParseFail:
    try:
        d = Dating.parse_string(s, parse_all=True).as_dict()
        return ParsedDating(dating=s, **d)
    except ParseException as ex:
        return ParseFail(s, 'DatingFail', ex)



def parse_episkop_name(s) -> ParsedEpiskopName:
    return None
    ...


# -------------- Test ---------------------------
class EpiskopRowsSaver(ChainLink):
    def __init__(self, filename):
        self.filename = filename
        self.rows = set()

    def process(self, s: CafedraArticle):
        for r in s.episkops:
            if isinstance(r, str):
                continue
            self.rows.add(r.text.strip())

    def finish(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            for r in sorted(self.rows):
                f.write(r + '\n')


if __name__ == '__main__':
    from book_parser import CafedraArticlesFromJson
    import sys

    f = 'episkop_rows.txt'

    if 'rows' in sys.argv:
        print(f'Save rows to file {f}')
        rs = EpiskopRowsSaver(f)
        ch = Chain(CafedraArticlesFromJson()).add(rs)
        ch.process('articles.json')
        print(f'Total episkop rows: {len(rs.rows)}')
        sys.exit(0)

    test = '''
31.10.1859	–	09.11.1866	–	Антоний Амфитеатров
(01.10.1917	–	10(23)11.1921	–	Давид Качахидзе)
02.1378	–	1380	–	в/у Герасим<span class="note" data-note="45">45</span>
754	–		–	Св. Иоанн I
2.1930	–	19.06(02.07)1930	–	в/у Михаил II Бирюков, паки
1929	–	1929	–	Константин Смирнов
(	–		–	Авраамий (1271) )
кон. 1927	–	05.1928	–	в/у Антоний Гончаревский<span class="note" data-note="4">4</span>
лето 1931	–	03.1937	–	Василий Ратмиров<span class="note" data-note="3">3</span>
не позднее 01(14)09.1921	–	не ранее 07.1922	–	Нифонт Фомин<span class="note" data-note="3">3</span>
после 01(14)09.1921	–	05.1922	–	Борис Соколов<span class="note" data-note="2">2</span>
ок. 348 – 349	–	до 370	–	Улфила<span class="note" data-note="2">2</span>

(	–	18(28)08.1596	–	Ираклий Северицкий)<span class="note" data-note="1">1</span>
(1471	–	1471	–	Амфилохий)
(15(28)11.1918	–	29.05(11.06)1921	–	Леонид Окропиридзе<span class="note" data-note="16">16</span>)
06(19)10.1955	–	19.09(02.10)1961	–	Андрей Сухенко<span class="note" data-note="65">65</span>
01.07.1912	–	09(22)02.1918	–	Назарий Андреев
01.1928	–	09.1928	–	в/у Александр Чекановский<span class="note" data-note="3">3</span
03. 1968	–	15(28)11.1968	–	в/у Питирим Нечаев<span class="note" data-note="28">28</span>
лето 1925	–	кон. 1925	–	Стефан Белопольский<span class="note" data-note="2">2</span>

–	23.04.? г.	–	Иоанн II
(1570 ?) 1571	–	1586	–	Варлаам
(Разумовский?)<span class="note" data-note="13">13</span>
        '''.split('\n')

    show_ok = True
    if 'bigtest' in sys.argv:
        test = open(f).read().split('\n')
        show_ok = False


    test = [x for x in test if x.strip()]
    fail_cnt = 0
    skip_cnt = 0
    for s in test:
        if show_ok:
            print(s)
            p = parse_episkop_row(s)
            if isinstance(p, ParseFail):
                if p.code == 'DivideFail':
                    skip_cnt += 1
                    print('>>>>> Skip')
                    print('------------\n')
                    continue
                else:
                    print(p.error)
                    print('------------\n')
                    fail_cnt += 1
            else:
                if p.has_fails():
                    print('!!!', p)
                    fail_cnt += 1
                else:
                    print(p)
                print('------------\n')
        else:
            p = parse_episkop_row(s)
            if isinstance(p, ParseFail):
                if p.code == 'DivideFail':
                    skip_cnt += 1
                    continue
                else:
                    print(s)
                    print(p.error)
                    print('------------\n')
                    fail_cnt += 1
            elif p.has_fails():
                print(s)
                print('!!!!!', p)
                print('------------\n')
                fail_cnt += 1


    print("Total", len(test), "Failed", fail_cnt, "Skipped", skip_cnt)

