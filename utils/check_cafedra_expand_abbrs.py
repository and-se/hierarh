'''
Скрипт сравнивает json данных о кафедрах, построенные на основе xml вёрстки книги и полученный прогоном черзе ChatGPT с раскрытием сокращений (см. utils/expand_abbreviations).

Сейчас скрипт соотносит названия, а также проверяет наличие html кода сносок (есть прецедент, что потерялись в json от ChatGPT)
и их согласованность со списком сносок в конце статьи.
'''




"""
== Ошибки и победы ChatGPT (+ручная правка Жени) при сравнении названий кафедр ==

+ исправила опечатку: Северомериканская стала Северо!а!мериканская

Яропольскую заменила на Ярославская - ИСПРАВЛЕНО (И В СТАТЬЯХ ТОЖЕ)
// ВЛАДИМИРСКАЯ (Владимирская и !!!Ярославская --> надо Яропольская!!!), Владимирская и Муромская)

Гдовская написала маленькими - ИСПРАВЛЕНО

падежи путает - ПОПРАВИЛ В НАЗВАНИЯХ

григорианский в названиях кафедр (так в списке сокращений), хотя надо бы "григорианская" - ИСПРАВЛЕНО

== по сноскам ==

+ в Мцхетской кафедре убрала дублирующуюся сноску:
    17 "Патриарх-католикос самопровозглашенной Грузинской автокефалии. II дата – скончался."

Потеряны сноски в тексте татьи (поле text) - ИСПРАВЛЕНО:
* ПЕРЕМЫШЛЬСКАЯ
* ПЕРЕЯСЛАВ-ХМЕЛЬНИЦКАЯ
* СМОЛЕНСКАЯ
* ТАЛЛИНСКАЯ
* ФЕОДОСИЙСКАЯ - здесь вообще все сноски были утеряны

TODO Много несогласованностей между список сносок статьи и ссылками на сноски и статьи
        - надо раскомментировать # check_notes_integrity(e['header'], e['notes'], eni)
    ! но это проблемы исходной книги, а не процесса раскрытия сокращений.


== Прочие проблемы ==

(см.) раскрывает (смотри) - так в списке сокращений, но так непонятно. ИСПРАВЛЕНО НА (смотри статью)


портит цитаты ЦС - НЕ ПРАВИЛ, непонятно как это всё отследить:
<
стало:
Этому есть косвенное подтверждение в Воскресенской летописи под 1390 годом, где сказано: «приидоша съ нимъ епископи Русии, киждо на свою епископию: … на Чернигов и на Брянеск Исаакий епископъ» («Пришли с ним (с митрополитом – Составитель) епископы русские, каждый в свою епархию, на Чернигов и на Брянеск епископ Исаакий».) (Полное собрание русских летописей. Том 8. Страница 60).

оригинал:
Этому есть косвенное подтверждение в Воскр. лет. под 1390 г., где сказано: «прiидоша съ нимъ епископи Рустiи, кiйждо на свою епископiю: … на Чернигов и на Брянеск Исакiй епископъ» («Пришли с ним (с митр. – Сост.) епископы русские, каждый в свою епархию, на Чернигов и на Брянск еп. Исаакий».) (ПСРЛ. Т. 8. С. 60).
>

Всего строчек с подстрокой  "летопис" в книге 132, найденные среди них несколько ЦС цитат вроде бы не поломались, но глазами тяжело заметить такой подвох.

!!! ещё даты то как в книге (всё номерами), то с заменой номеров месяцев на слова

!!! Св. везде сейчас раскрыт как Святой, а надо Святитель иногда.



"""



import json
import re
from pprint import pprint

caf_origin_file = '../data/cafedra_articles.json'
caf_expand_file = '../data/cafedra_articles_expand_abbrs.json'

def main():
    origin, expand = load_data(caf_origin_file, caf_expand_file)

    assert len(origin) == len(expand)

    not_eq = 0
    for i in range(len(origin)):
        o, e = origin[i]['header'], expand[i]['header']

        if not header_like(o, e):
            print(f'NOT LIKE: {o}  <-> {e}')
            not_eq += 1

    print('Расхождения в названиях:', not_eq)

    for i in range(len(origin)):
        o, e = origin[i], expand[i]

        # убираем дублирующуюся сноску из оригинала
        if o['header'] == 'МЦХЕТСКАЯ':
            assert o['notes'][17] == o['notes'][16]
            del o['notes'][17]

        if len(o['notes']) != len(e['notes']):
            print(f'''Разное колич. сносок {o['header']} / {e['header']}: {len(o['notes'])} <-> {len(e['notes'])}''')

        oni = build_note_index(o)
        eni = build_note_index(e)

        if oni != eni:
            skip_check = ['ФЕОДОСИЙСКАЯ', 'НИЖНЕУДИНСКАЯ, обновленческая', 'САРАПУЛЬСКАЯ, обновленческая']
            print(f'''Разная расстановка сносок {o['header']} / {e['header']}''')
            if e['header'] in skip_check:
                print('\t - проверь вручную или пропусти, т.к. были ручные правки и номера сносок поехали')
                continue

            print('Origin:')
            print(oni)
            print('Expand:')
            print(eni)
            print()

        # TODO находится много несогласованностей между список сносок статьи и ссылками на сноски и статьи
        # check_notes_integrity(o['header'], o['notes'], oni)
        # check_notes_integrity(e['header'], e['notes'], eni)


def header_like(origin_header, expanded_header):
    e1 = re.sub(r'[^а-яА-ЯёЁ]', '', expanded_header)
    o1 = re.sub(r'[^а-яА-ЯёЁ]', '', origin_header)

    if e1.startswith(o1): return True

    # Вручную обработанные случаи
    manual = {
        # исправлена опечатка в книге Северо!мериканская
        'АЛЕУТСКАЯ, обн. (см. Северомериканская, обн.)':
            'АЛЕУТСКАЯ, обновленческая (см. Североамериканская, обновленческая)',
        # Каз. хочется раскрыть как Казанская, но нет - здесь именно Казахстанская
        'ПЕТРОПАВЛОВСКАЯ (Каз.), обн.':
            'ПЕТРОПАВЛОВСКАЯ (Казахстанская), обновленческая',

        # Дон. - Донская, но приходит на ум и Донецкя
        'РОСТОВСКАЯ (Дон.), григ.': 'РОСТОВСКАЯ (Донская), григорианская',
        'РОСТОВСКАЯ (Дон.), обн.': 'РОСТОВСКАЯ (Донская), обновленческая',
    }

    if manual.get(origin_header) == expanded_header: return True

    # Пробуем раскрыть сокращения сами и сверить с результатом из раскрытого файла
    e2 = expand_abbrs(origin_header)


    return re.sub(r'\s', '', e2) == re.sub(r'\s', '', expanded_header)


def expand_abbrs(txt):
    replace_dict = {
        'обн.': 'обновленческая',
        'григ.': 'григорианская',
        'г.': 'года',
        'юрисд.': 'юрисдикции',

        'ПАПЦ': 'Польская Автокефальная Православная Церковь',
        # Обычно расшифоровывают ".. заграницей", но в списке сокращений так
        'РПЦЗ': 'Русская Православная Церковь за рубежом',

        'Вик-во': 'Викариатство',

        'Ивановск.': 'Ивановская',
        'Влад.': 'Владимирская',
        'Северокавк.': 'Северокавказская',
        'Самар.': 'Самарская',

        'Моск. Кремля': 'Московского Кремля',
        'Моск. Патриархии' : 'Московской Патриархии',
        'Моск.': 'Московская',

        'Орл.': 'Орловская',
        'Воронежск.': 'Воронежская',
        'Новочерк.': 'Новочеркасская',
        'Киевск.': 'Киевская',
        'Алтайск.': 'Алтайская',
        'Рост.': 'Ростовская',
        'Вятск.': 'Вятская',
        'Самарск.': 'Самарская',
        'Камч.': 'Камчатская',
        'Ряз.': 'Рязанская',
        'Хабар.': 'Хабаровская',

        'Укр.': 'Украинская',

    }

    for k, v in replace_dict.items():
        txt = txt.replace(k, v)
    return txt

def build_note_index(article):
    r = []

    t, notes = extract_notes(article['text'] or '')
    if notes:
        r.append(('text', notes))

    for i, ep in enumerate(article['episkops']):
        if isinstance(ep, str):
            r.append(('ep subheader', expand_abbrs(ep).replace(' )', ')') ))
            continue

        t, notes = extract_notes(ep['text'])
        if notes:
            r.append((i, notes))
    return r

def check_notes_integrity(caf, notes, notes_index):
    ns1 = sorted([int(x['num']) for x in notes])
    ns2 = []
    for h, notes in notes_index:
        if h != 'ep subheader':
            ns2.extend([int(x) for x in notes])
    ns2 = sorted(ns2)

    if ns1 != ns2:
        print(f'''Несогласованные сноски {caf}:\n\tnotes: {ns1}\n\t refs: {ns2}\n''')

# Выписка кода из article_parser.py
# - лучше выпишем маленький кусок, чем создавать лишнюю связь и головную боль при переработке основных классов.
note_re = re.compile(
                r'<span\s+class="note"[^>]*>\s*(?P<note_num>\d+)\s*</span>')

def extract_notes(s):
    # remove note
    all_notes = [x.group('note_num') for x in note_re.finditer(s)]
    s = note_re.sub('', s)
    return s, all_notes
# Конец выписки из article_parser.py


def load_data(f1, f2):
    r = []
    for i in (f1, f2):
        with open(i) as f:
            r.append(json.load(f))
    return r

if __name__ == '__main__':
    main()
