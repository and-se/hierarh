from pyparsing import Literal, Regex, Opt, ParseException, Located
from dataclasses import dataclass
import re

try:
    from parsers.fail import ParseFail
except ImportError:
    from fail import ParseFail


@dataclass
class ParsedDating:
    dating: str  # original dating text
    year: int
    month: int = None
    day: int = None
    prefix: str = None  # около, лето, не ранее и т.д.


def parse_dating(s) -> ParsedDating | ParseFail:
    try:
        d = Dating.parse_string(s, parse_all=True).as_dict()
        return ParsedDating(dating=s, **d)
    except ParseException as ex:
        return ParseFail(s, 'DatingFail', ex)

MAYBE_NOT_DATING = 'DatingFail.MayBeIsNotDating'

DATING_DIVIDERS = ('-', '–')

def parse_start_end_dating(s, divider = DATING_DIVIDERS) -> tuple[ParsedDating | None, ParsedDating | None] | ParseFail:
    """
    Разбирает интервал из двух датировок, разделённых тире.
    divider - кортеж с допустимыми разделителями датировок (или строка с одним)

    @returns кортеж из разобранных начальной и конечной датировки
    Если одной из датировок нет, в кортеже будет None. Но хотя бы одна датировка в нём будет!
    
    В остальных случаях возвращает ParseFail. Если есть сомнения, что в переданной строке вообще 
    есть какая-либо датировка, то ParseFail.code = MAYBE_NOT_DATING

    """
    origin_s = s
    s = s.strip()
    only_end = False  # есть только дата окончания
    if s.startswith(divider):
        only_end = True
        s = s[1:].strip()
    # Добавляем положение разобранного в строке
    # locn_start, locn_end, наш разбор вложен в value
    parser = Located(Dating)
    try:
        pr1 = parser.parse_string(s, parse_all=False)
        date1 = s[:pr1.locn_end].strip()
        date1 = ParsedDating(date1, **pr1.value.as_dict())
    except ParseException as ex:
        return ParseFail(origin_s, MAYBE_NOT_DATING, f'Не удалось разобрать "{s}"')
    
    tail = s[pr1.locn_end:].strip()
    if not tail:
        if only_end:
            return None, date1
        else:
            return date1, None
    
    if not tail.startswith(divider):
        return ParseFail(origin_s, 'DatingFail.NoDividerBeforeTail', 
                         f'нет тире перед второй датировкой "{tail}"')
    tail = tail[1:].strip()

    try:
        pr2 = parser.parse_string(tail, parse_all=True)
        date2 = ParsedDating(tail, **pr2.value.as_dict())
    except ParseException as ex:
        return ParseFail(origin_s, 'DatingFail.TailFail', f'Не удалось разобрать "{tail}"')
    
    if date2.year < date1.year:
        return ParseFail(origin_s, 'DatingFail.FailYearCheck', 'Год даты окончания меньше года даты начала')
    
    return (date1, date2)
    
    



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
         ) + (Opt(brackets) + Opt(Literal('?'))).suppress()


if __name__ == '__main__':
    tests = '''
31.10.1859
10(23)11.1921
02.1378
1380
754
2.1930
19.06(02.07)1930
кон. 1927
лето 1931
не позднее 01(14)09.1921
не ранее 07.1922
после 01(14)09.1921
ок. 348 – 349
до 370
29.05(11.06)1921
лето 1925
кон. 1925
23.04.? г.
(1570 ?) 1571
31.03.1873 - 25.05.1877
1458–1459
- 29.07.1681
– около 1459
1925?

1925 (и что)
1925 (и что)?
1925 ? (лишнее)

30.05.1917 - 02.191

    '''.split('\n')

    for t in tests:
        if not t.strip():
            continue
        p = parse_start_end_dating(t)

        warn = '\n!!!' if isinstance(p, ParseFail) else ''
        print(warn, t, p, "\n")
