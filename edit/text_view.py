
from lxml import html
import re
from functools import cached_property

from parsers.dating import DATING_DIVIDERS, MAYBE_NOT_DATING, ParsedDating, parse_dating, parse_start_end_dating
from parsers.episkop import ParsedEpiskopInCafedra, parse_episkop_name_in_cafedra
from parsers.fail import ParseFail

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from edit.storage import TextCafedra, TextEpiskop

import logging

TEXT_VIEW_LOG_NAME = 'hierarh.text_view' 
_L = logging.getLogger(TEXT_VIEW_LOG_NAME)

# разделители в интервале дат
DATING_DIVIDERS_EXT = DATING_DIVIDERS + ('/', ',')

class EpiskopView:
    """
    Структурированное представление html данных епископа
    """
    def __init__(self, data: 'TextEpiskop'):
        self._text = data
        self._tree = html.fragment_fromstring(data.html)

    @property
    def key(self):
        return self._text.key
    
    @property
    def text(self) -> 'TextEpiskop':
        return self._text

    @cached_property
    def header(self):
        return self._text.header()

    @cached_property
    def is_obn(self):
        return self._text.is_obn()
    
    @property
    def cafedras(self) -> list['RowCafedraView']:
        # отбираем строки таблицы епископов, которые не являются заголовками
        rows = self._tree.xpath("""//table[contains(@class, 'cafedras')]/tbody/tr[not(contains(@class, 'header-row'))]""")
        return [RowCafedraView(r) for r in rows]


    def __repr__(self):
        return f'EpiskopView({self.__str__()})'
    
    def __str__(self):
        return f'{self.header} #{self.key}'


from edit.init_db_creator import CAFEDRA_MAP_FILE
import json


class RowCafedraView:    
    """
    Структурированное представление строки таблицы кафедр в html епископа
    """
    def __init__(self, tr: html.HtmlElement):
        self.d = tr
        self.caf = tr[0]
        assert self.caf.tag == 'td'

        self._name = None

        self._parsed_begin = None
        self._parsed_end = None
 
    @property
    def name(self):
        if not self._name:
            self._name = self.build_cafedra_name(self.caf.text_content())
        return self._name
    
    @property
    def link(self):
        return None  # TODO now no links

    @property
    def begin_dating(self) -> str:
        return self.d[1].text_content().strip()
    
    @property
    def parsed_begin_dating(self) -> ParsedDating | ParseFail | None:
        if not self.begin_dating:
            return None
        if not self._parsed_begin:
            self._parsed_begin = parse_dating(remove_brackets(self.begin_dating))
            if isinstance(self._parsed_begin, ParseFail):
                _L.warning(f"fail parse begin dating: {self.begin_dating} in {self}")
        return self._parsed_begin
    
    @property
    def begin_year(self) -> int | None:
        if self.parsed_begin_dating and not isinstance(self.parsed_begin_dating, ParseFail):
            return self.parsed_begin_dating.year
    
    @property
    def end_dating(self):
        return self.d[2].text_content().strip()

    @property    
    def parsed_end_dating(self) -> ParsedDating | ParseFail | None:
        if not self.end_dating:
            return None
        if not self._parsed_end:
            self._parsed_end = parse_dating(remove_brackets(self.end_dating))
            if isinstance(self._parsed_end, ParseFail):
                _L.warning(f"fail parse end dating: {self.end_dating} in {self}")
        
        return self._parsed_end
    
    @property
    def end_year(self) -> int | None:
        if self.parsed_end_dating and not isinstance(self.parsed_end_dating, ParseFail):
            return self.parsed_end_dating.year
        
    def get_min_max_year(self) -> tuple[int, int] | tuple[None, None]:
        """
        Извлекает минимальный и максимальный год из записи о кафедре.

        Углбулённо изучает поля с датировкой начала и окончания (begin_dating, end_dating),
        а именно готово к наличию двух датировок в одном поле.

        @returns
        Кортеж из двух чисел (минимальный и максимальный год - возможно равные)
        либо два None, если данных нет совсем
        """
        r = []
        for dating in (self.begin_dating, self.end_dating):
            if not dating.strip():
                continue            
            dating2 = remove_brackets(dating)
            parsed2 = parse_start_end_dating(dating2, divider=DATING_DIVIDERS_EXT)
            if not isinstance(parsed2, ParseFail):
                for date in parsed2:
                    if date:
                        r.append(date.year)
            else:
                _L.warning(f"fail parse dating: {dating} in {self}")


        if not r:
            return None, None
        return min(r), max(r)
        
    def __repr__(self):
        return f"RowCafedraView({self.name} ({self.begin_dating} - {self.end_dating})"
    
    def __str__(self):
        return f"{self.name} ({self.begin_dating} - {self.end_dating})"
    
    with open(CAFEDRA_MAP_FILE, encoding='utf8') as f:
        Cafedra_name_map = json.load(f)

    @classmethod
    def build_cafedra_name(cls, caf_td: str):
        caf_td = caf_td.replace('?', '')        
        caf_td = re.sub(r'^\s*\(?\s*в\s*/\s*у\s*\)?\s*', '', caf_td)            
        caf_td = caf_td.replace('()', '')
        caf_td = re.sub(r',\s*((паки)|(в \d-й раз))\s*$', '', caf_td)
        caf_td = caf_td.strip()

        res = cls.Cafedra_name_map.get(caf_td)
        if not res:
            caf_td = re.sub(r',\s*обн\.?\s*$', ', обновленческая', caf_td)
            caf_td = re.sub(r',\s*григ\.?\s*$', ', григорианская', caf_td)
            caf_td = re.sub(r',\s*\(ПАПЦ\)\.?\s*$', ', (Польская автокефальная православная церковь)', caf_td)
            res = caf_td

        return res


class CafedraView:
    """
    Структурированное представление html данных кафедры
    """
    def __init__(self, data: 'TextCafedra'):
        self._text = data
        self._tree = html.fragment_fromstring(data.html)

    @property
    def key(self):
        return self._text.key
    
    @property
    def text(self) -> 'TextCafedra':
        return self._text

    @cached_property
    def header(self):
        return self._text.header()
    
    @cached_property
    def is_obn(self):
        return self._text.is_obn()

    def has_name(self, name: str):
        return name.lower().strip() == self.header
        # TODO other names...

    @property
    def episkops(self) -> list['RowEpiskopView']:
        # отбираем строки таблицы епископов, которые не являются заголовками
        rows = self._tree.xpath("""//table[contains(@class, 'episkops')]/tbody/tr[not(contains(@class, 'header-row'))]""")
        return [RowEpiskopView(r) for r in rows]
    
    def __repr__(self):
        return f'CafedraView({self.__str__()})'
    
    def __str__(self):
        return f'{self.header} #{self.key}'
    

class RowEpiskopView:
    """
    Структурированное представление строки таблицы епископов в html кафедры
    """
    def __init__(self, tr: html.HtmlElement):
        self.d = tr
        self.ep = tr[-1]
        assert self.ep.tag == 'td'

        self._ep = None
        self._parsed_ep = None

        self._parsed_begin = None
        self._parsed_end = None
 
    @property
    def episkop(self) -> str:
        if not self._ep:
            # берем только текстовые узлы, все теги игнорируем
            # todo игнорировать только span fnote
            text = ''.join(self.ep.xpath('text()'))
            #from parsers.episkop import parse_episkop_name_in_cafedra
            self._ep = text
        return self._ep
    
    @property
    def parsed_episkop(self) -> ParsedEpiskopInCafedra | ParseFail:
        if not self._parsed_ep:
            self._parsed_ep = parse_episkop_name_in_cafedra(self.episkop)
        return self._parsed_ep

    @property
    def begin_dating(self) -> str:
        return self.d[0].text_content().strip()
    
    @property
    def parsed_begin_dating(self) -> ParsedDating | ParseFail | None:
        if not self.begin_dating:
            return None
        if not self._parsed_begin:
            self._parsed_begin = parse_dating(self.begin_dating)
            if isinstance(self._parsed_begin, ParseFail):
                _L.warning(f"fail parse begin dating: {self.begin_dating} in {self}")
        
        return self._parsed_begin
    
    @property
    def begin_year(self) -> int | None:
        if self.parsed_begin_dating and not isinstance(self.parsed_begin_dating, ParseFail):
            return self.parsed_begin_dating.year
    
    @property
    def end_dating(self):
        return self.d[1].text_content().strip()

    @property    
    def parsed_end_dating(self) -> ParsedDating | ParseFail | None:
        if not self.end_dating:
            return None
        if not self._parsed_end:
            self._parsed_end = parse_dating(self.end_dating)
            if isinstance(self._parsed_end, ParseFail):
                _L.warning(f"fail parse end dating: {self.end_dating} in {self}")
        return self._parsed_end
    
    @property
    def end_year(self) -> int | None:
        if self.parsed_end_dating and not isinstance(self.parsed_end_dating, ParseFail):
            return self.parsed_end_dating.year
        
    @property
    def brackets_text(self) -> str | None:
        """
        Содержимое скобок в конце текста,
        например Антоний Герасимов-Зыбелин (<Забелин?>)
        """
        if not isinstance(self.parsed_episkop, ParseFail):
            return self.parsed_episkop.brackets_content
        
    def get_brackets_dating(self) -> tuple[ParsedDating | None, ParsedDating | None] | ParseFail | None:
        """
        Попытка распознать скобки как одну или две датировки,
        например Евфимий (<1447–1451>)
        """
        br = self.brackets_text
        if br:
            r = parse_start_end_dating(br, divider = DATING_DIVIDERS_EXT)
            if isinstance(r, ParseFail) and r.code == MAYBE_NOT_DATING:
                return None
            return r
        
    def get_min_max_year(self) -> tuple[int, int] | tuple[None, None]:
        """
        Извлекает минимальный и максимальный год из записи о епископе.

        Просматривает поля с датировкой начала и окончания (begin_dating, end_dating),
        а также содержимое скобок (brackets_text --> get_brackets_dating())

        @returns
        Кортеж из двух чисел (минимальный и максимальный год - возможно равные)
        либо два None, если данных нет совсем
        """
        r = []

        def add(year):
            if year is not None:
                r.append(year)
        
        add(self.begin_year)
        add(self.end_year)

        if len(r) == 2 and r[0] > r[1]:
            _L.warning(f"begin_year > end_year for {self}")

        inaccurate_dating = self.get_brackets_dating()
        if inaccurate_dating:
            if isinstance(inaccurate_dating, ParseFail):
                _L.warning('Не разобрана дата в скобках %s', inaccurate_dating)
            else:
                d1, d2 = inaccurate_dating
                if d1:
                    r.append(d1.year)
                if d2:
                    r.append(d2.year)
        
        if not r:
            return None, None

        return min(r), max(r)
    
    
    @property
    def link(self):
        return None  # TODO now no links
    
    def __repr__(self):
        return f"RowEpiskopView({self.begin_dating} - {self.end_dating} {self.episkop})"
    
    def __str__(self):
        return f"{self.episkop} ({self.begin_dating} - {self.end_dating})"
    
def remove_brackets(s):
    """
    Если всё содержимое строки заключено в скобки, убирает их.
    Но учитывая вложенность скобок.

    Например, '(abc (def) ek)' --> 'abc (def) ek'
    но '(ab) c (de)' --> '(ab) c (de)'
    'wrong )' --> 'wrong )'

    @returns
    входной текст без скобок и пробелов на концах (strip).
    Либо исходную строку.
    """
    s = s.strip()
    level, i = 0, 0
    length = len(s)
    for i in range(length):
        if s[i] == '(':
            level+=1
        elif s[i] == ')':
            level-=1
        if level<=0:
            break
    if level==0 and i>0 and i == length-1:
        return s[1:-1]
    else:
        return s

