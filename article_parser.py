from chain import ChainLink, Chain
from models import CafedraArticle
from models import Cafedra, EpiskopOfCafedra, Note, EpiskopInfo, Dating

from parsers.fail import ParseFail
from parsers.dating import parse_dating, ParsedDating
from parsers.episkop import parse_episkop_name_in_cafedra, \
                            ParsedEpiskopInCafedra

from lib.date_intervals_builder import DateIntervalsBuilder
from lib.roman_num import from_roman

import human

import re
from dataclasses import dataclass
from typing import Tuple, List


class CafedraArticleParser(ChainLink):
    @staticmethod
    @human.show_exception
    def parse_article(art: CafedraArticle) -> Cafedra:
        caf = Cafedra(
                header=art.header,
                is_obn=art.is_obn, is_link=art.is_link,
                text=art.text or ''
        )

        for aep in art.episkops:
            if isinstance(aep, str):
                # subheaders like 'Архиепископы и митрополиты Московские;'
                caf.episkops.append(aep)
                continue

            pp: ParsedEpiskopRow = parse_episkop_row(aep.text)

            if isinstance(pp, ParseFail):
                human.send("Can't parse this - save as header", aep.text, pp)
                caf.episkops.append("#unparsed# " + aep.text)
                continue

            if pp.error:
                if isinstance(pp.who, ParseFail):
                    human.send('Fail episkop!!!', aep.text, pp)
                else:
                    human.send('Fail dating', aep.text, pp)

            if not isinstance(pp.who, ParseFail):
                if not pp.who.name or pp.who.name == '?':
                    human.send("Empty episkop name", aep.text, pp.who)
                temp_status = pp.who.temp_status
            else:
                temp_status = None

            epcaf = EpiskopOfCafedra(
                            episkop=to_episkop_info(pp.who),
                            begin_dating=to_dating(pp.begin),
                            end_dating=to_dating(pp.end),
                            temp_status=temp_status,
                            inexact=pp.inexact,
                            namesake_num=get_namesake_num(pp.who)
                    )

            epcaf._original_text = aep.text

            if pp.notes:
                epcaf.notes = [int(x) for x in pp.notes]

            caf.episkops.append(epcaf)

        caf.notes = [Note(num=x.num, text=x.text) for x in art.notes]
        return caf

    def process(self, s: CafedraArticle):
        pp: Cafedra = self.parse_article(s)
        self.send(pp)


def to_episkop_info(parsed: ParsedEpiskopInCafedra) -> EpiskopInfo:
    if parsed is None:
        raise ValueError("parsed episkop info can't be None")
    if isinstance(parsed, ParseFail):
        return EpiskopInfo(name=parsed.text, surname=None)  # fixme

    surname = parsed.surname
    # Глобальный номер для однофамильцев-одноимёнцев включаем в фамилию
    if parsed.number_after_surname:
        surname += ' ' + parsed.number_after_surname

    return EpiskopInfo(name=parsed.name,
                       surname=surname,
                       saint_title=parsed.saint_title,
                       world_title=parsed.world_title,
                       comment=parsed.brackets_content)


def to_dating(parsed: ParsedDating) -> Dating:
    if parsed is None:
        return None
    if isinstance(parsed, ParseFail):
        return Dating(dating=parsed.text, estimated_date=None)
    else:
        b = DateIntervalsBuilder()
        try:
            b.add_date(parsed.year, parsed.month, parsed.day)
            items = b.build()
        except ValueError as ex:
            if 'day is out of range' in str(ex):
                human.send(str(ex), parsed)
                items = []

        if len(items) != 1:
            if len(items) == 0:
                msg = 'No date intervals for dating'
            else:
                msg = 'Many date intervals, expected single'
            human.send(msg, parsed)

        est = items[0].begin if len(items) else None
        return Dating(dating=parsed.dating, estimated_date=est)


def get_namesake_num(parsed: ParsedEpiskopInCafedra) -> int | None:
    if not parsed or isinstance(parsed, ParseFail):
        return None
    if parsed.number_after_name and not parsed.surname:
        return from_roman(parsed.number_after_name)

    ...  # TODO

# ------------ Parser for Episkop row in table of cafedra article -------


@dataclass
class ParsedEpiskopRow:
    begin: ParsedDating
    end: ParsedDating
    who: ParsedEpiskopInCafedra
    inexact: bool
    notes: List[int]

    @property
    def error(self):
        for x in [self.begin, self.end, self.who]:
            if isinstance(x, ParseFail):
                return x


def parse_episkop_row(s) -> ParsedEpiskopRow | ParseFail:
    s, notes = extract_notes(s)
    div = divide_episkop_row(s)
    if isinstance(div, ParseFail):
        return div

    begin, end, who, inexact = div

    begin = parse_dating(begin) if begin else None
    end = parse_dating(end) if end else None
    who = parse_episkop_name_in_cafedra(who)

    return ParsedEpiskopRow(begin, end, who, inexact, notes)


def divide_episkop_row(s) -> Tuple[str, str, str, bool]:
    # 10(23)10.1926	–	08(21)04.1932	–	Петр Данилов, паки
    s = s.strip()
    inexact = False
    if s.startswith('(') and s.endswith(')'):
        inexact = True
        s = s[1:-1]
    l = re.split(r'[–—]\s', s)  # noqa: E741

    if len(l) != 3:
        return ParseFail(s, 'DivideFail',
                         f"Expected 3 items, but got {len(l)} for '{s}'")
    return l[0].strip(), l[1].strip(), l[2].strip(), inexact


note_re = re.compile(
                r'<span\s+class="note"[^>]*>\s*(?P<note_num>\d+)\s*</span>')


def extract_notes(s) -> Tuple[str, list]:
    # remove note
    all_notes = [x.group('note_num') for x in note_re.finditer(s)]
    s = note_re.sub('', s)
    return s, all_notes


class WholeRussiaCafedraFixer(ChainLink):
    def __init__(self):
        self._moscow_done = False
        self._stashed_caf = None
        self._mitropol_done = False

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
        elif s.header == '«МИТРОПОЛИЯ РОССИИ» (см. Всероссийская)':
            s.header = "МИТРОПОЛИЯ РОССИИ (см. Всероссийская)"
            self._mitropol_done = True

        self.send(s)

    def finish(self):
        if not self._moscow_done:
            raise Exception('Не обработаны сноски двух статей про Московский '
                            'Патриархат (aka Митрополия Руссии)')
        if not self._mitropol_done:
            raise Exception('Не обработана «МИТРОПОЛИЯ РОССИИ» - '
                            'надо убрать кавычки')


class UnparsedCafedraFixer(ChainLink):
    # TODO Сейчас только лишь сохраняет неразобранные строки о епископах вместе с контекстом в указанный файл
    def __init__(self, patch_file):
        self.patch_file = patch_file
        self.stream = open(self.patch_file, 'w', encoding='utf8')

    def process(self, s: Cafedra):
        l = list(filter(lambda x: isinstance(x, str) and
                                  x.startswith('#unparsed#'),
                 s.episkops)
        )


        if l:
            self.stream.write('#header# ' + s.header + '\n')
            printed = []
            for i, e in enumerate(s.episkops):
                if isinstance(e, str) and e.startswith('#unparsed#'):
                    if i-1 not in printed and i-1 >= 0:
                        prev = s.episkops[i-1]
                        if isinstance(prev, str):
                            self.stream.write(prev + '\n')
                        else:
                            self.stream.write(prev._original_text + '\n')

                    self.stream.write(e + '\n')
                    printed += [i-1, i]

            self.stream.write('\n\n')

        self.send(s)

            # print("Unparsed data here: ", s.model_dump_json(indent=4))

    def finish(self):
        self.stream.close()

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
01.1928	–	09.1928	–	в/у Александр Чекановский<span class="note" data-note="3">3</span>
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
                if p.error:
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
