import re
from dataclasses import dataclass

from parsers.fail import ParseFail


@dataclass
class ParsedEpiskopName:
    text: str

    name: str
    number_after_name: str
    surname: str
    number_after_surname: str
    saint_title: str

    temp_status: str  # в/у
    paki: str  # паки, в 3-й раз

    dating_in_brackets: str


def parse_episkop_name_in_cafedra(s) -> ParsedEpiskopName:
    orig = s
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

    return ParsedEpiskopName(
        text=orig,
        name=s.group('who').strip() or '?',
        number_after_name=None,  # todo
        surname=None,  # todo
        number_after_surname=None,  # todo
        saint_title=None,  # todo

        temp_status=vy,
        paki=s.group('paki'),
        dating_in_brackets=None  # todo
    )
