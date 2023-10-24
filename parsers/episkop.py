import re
from dataclasses import dataclass
from pyparsing import Regex, Opt, Word, Char, nested_expr, \
                      ParseException, srange, Combine, original_text_for

try:
    from parsers.fail import ParseFail
except ImportError:
    from fail import ParseFail


@dataclass
class ParsedEpiskopInCafedra:
    text: str

    name: str
    number_after_name: str = None

    surname: str = None
    number_after_surname: str = None

    saint_title: str = None  # <Сщмч.> Вениамин Воскресенский
    world_title: str = None  # Антоний <кн.> Туркестанов

    temp_status: str = None  # в/у
    paki: str = None  # паки, в 3-й раз

    brackets_content: str = None


def parse_episkop_name_in_cafedra(s) -> ParsedEpiskopInCafedra:
    try:
        d = EpiskopInCafedra.parse_string(s, parse_all=True).as_dict()
        if '?' in d.get('temp_status', ''):
            d['temp_status'] = 'в/у?'
        for k in d:
            d[k] = d[k].strip()
        return ParsedEpiskopInCafedra(text=s, **d)
    except ParseException as ex:
        return ParseFail(s, 'EpiskopNameFail', ex)


CapitalizedWord = Word(srange("[А-ЯЁ]"), srange("[а-яё]"), min=2)
RimNumber = Regex(r'((I{1,3})|(I?VI?))\b')
Question = Char("?") | nested_expr("(", ")", Char("?"))
Brackets = Char('(') + Regex(r'[^)]+')('brackets_content') + ')'

Name = CapitalizedWord + Opt(Char('(') + Regex(r'[^)0-9]+') + ')')
Name = original_text_for(Name | 'NN')('name')

Surname = Combine(CapitalizedWord + Opt('-' + CapitalizedWord))
Surname = original_text_for(Surname + Opt(CapitalizedWord))("surname")

SaintTitle = Regex(r'(Св\.(\s+муч\.)?)|(Сщмч\.)|(Блаж\.)',
                   flags=re.I)('saint_title')
Temp = Char('в') + '/' + 'у' + Opt(Question)
Temp |= Char('(') + Temp + ')'
Temp = original_text_for(Temp)('temp_status')

NumberAferName = RimNumber('number_after_name')
NumberAferSurnname = RimNumber('number_after_surname')

Paki = Char(',') + Regex(r'паки|(в\s+\d+-й\s+раз)')('paki')


WorldTitle = Opt(Char(',')) + Regex(r'кн\.')('world_title')


EpiskopInCafedra = Opt(Temp) + Opt(SaintTitle) + \
                        Name + Opt(NumberAferName) + \
                        Opt(WorldTitle) + \
                        Opt(Surname + Opt(NumberAferSurnname)) + \
                        Opt(Brackets) + Opt(Paki) + Opt(Brackets) + \
                        Opt('.')


if __name__ == '__main__':
    tests = """
Вассиан
Ираклий Северицкий
Св. Амвросий Хелая

Сщмч. Кирион Садзегели
в/у Мефодий Филимонович
Иоанн II
(в/у ?) Василий III
Николай II Гиляровский
Иоанн Соколов II

Димитрий Поспелов, паки
Феофилакт Лопатинский, в 3-й раз

Трифон кн. Туркестанов

Авраамий (1271)
Андрей (1117 ?)

Антоний Герасимов-Зыбелин (Забелин?)

Евфимий (1447–1451)
Вассиан III (02.1540)
NN (I пол. XI в.)

Евфимий (1447–1451)
Вассиан III (02.1540)

Иоаким (Иоанн, Иов)

Серафим (в сх. Сергий)

Антоний VI (?)

Григорий, кн. Чиковани

Сергий (Алексий) Лавров
Дионисий (в сх. Димитрий) Ушаков
Св. Феодор Грек, паки (1010–1014)

Варсонофий IV Гриневич

Св. муч. Ефрем I

NN (кон. XII в.)

Христофор Сулима Грек

Харитон Обрынский-Угровецкий.
    """.split('\n')
    for t in tests:
        if not t.strip():
            continue
        p = parse_episkop_name_in_cafedra(t)

        warn = '!!!' if isinstance(p, ParseFail) else ''
        print(warn, t, p)
