from pyparsing import Literal, Regex, Opt, ParseException
from dataclasses import dataclass
import re

try:
    from parsers.fail import ParseFail
except ImportError:
    from fail import ParseFail


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
    '''.split('\n')

    for t in tests:
        if not t.strip():
            continue
        p = parse_dating(t)

        warn = '!!!' if isinstance(p, ParseFail) else ''
        print(warn, t, p)
