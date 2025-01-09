import sys
import os
import json
from pathlib import Path
import re
from dataclasses import dataclass

sys.path.append(os.getcwd())
from article_parser import divide_episkop_row
from parsers.fail import ParseFail

CSS_UNPARSED_CLASS = 'error-unparsed'
CSS_NOTE_ERROR = 'error-note'

def main():
    filename = sys.argv[1]
    if filename.endswith(".json"):
        filename, error = article_json_to_html_edit(filename)
        if error:
            print(f"""При конвертации начальных данных для редактирования есть ошибки.
            Отредактируйте в файле {filename} элементы с class="{CSS_UNPARSED_CLASS}"
            {error}""")
            return 1

    print(f"Сконвертированный html в файле {filename}")

def article_json_to_html_edit(filename):
    result_file = Path(filename).with_suffix(".html")
    errs = []
    with open(filename) as f, open(result_file, 'w', encoding="utf8") as t:
        data = json.load(f)
        assert isinstance(data, list)
        for d in data:
            r, err = convert_cafedra_json_to_html(d)
            if err:
                errs.append(d['header'])
            t.write(r)
    return result_file, errs



note_re = re.compile(r'<span\s+class="note"[^>]*>\s*(?P<note_num>\d+)\s*</span>')

@dataclass
class Note:
    num: int
    text: str
    touched: bool = False

def convert_cafedra_json_to_html(caf: dict):
    has_err = False
    notes = [Note(int(x['num']), x['text']) for x in caf['notes']]

    def find_note(num):
        num = int(num)
        for x in notes:
            if x.num == num:
                return x

    def note_convert(m):
        r = find_note(m.group('note_num'))
        if r:
            r.touched=True
            return f''' <details><div data-note-num="{m.group('note_num')}">{r.text}</div>'''
        else:
            has_err=True
            return f'''<span class="{CSS_NOTE_ERROR}" data-note-num="{m.group('note_num')}"></span>'''

    def convert_notes(txt):
        return note_re.sub(note_convert, txt)

    header = convert_notes(caf['header'])
    text = convert_notes(caf.get('text') or '')

    html_eps = []
    for ep in (caf['episkops'] or []):
        if isinstance(ep, str):
            ep = convert_notes(ep)
            html_eps.append(f'''<tr class="header-row"><td colspan="3">{ep}</td></tr>''')
        else:
            assert isinstance(ep, dict) and len(ep) == 1
            ep = ep['text']
            r = divide_episkop_row(ep)
            if isinstance(r, ParseFail):
                ep = convert_notes(ep)
                html_eps.append(
                f'  <tr class="{CSS_UNPARSED_CLASS}"><td></td><td></td><td>{ep}</td></tr>')
            else:
                start, end, who, inexact = r
                if inexact:
                    start = '( ' + start
                    who = who + ' )'
                start, end, who = map(convert_notes, (start, end, who))
                html_eps.append(
                f'  <tr><td>{start}</td><td>{end}</td><td>{who}</td></tr>')
    html_eps = '\n'.join(html_eps)

    unused_notes = '\n'.join([f'''<li>{x.num}. {x.text}</li>''' for x in notes if not x.touched])
    if unused_notes:
        unused_notes = f'''
        <div class="{CSS_NOTE_ERROR}">
        Неиспользованные ссылки
            <ul>
            {unused_notes}
            </ul>
        </div>'''
        has_err = True


    #NB! html-escaping уже сделан во входном json
    result = f'''
<article class="cafedra_article" data-start-line="{caf['start_line']}" data-is-link="{caf['is_link']}" data-is-obn="{caf['is_obn']}">
<div class="header">{header}</div>
<div class="text">
{text}
</div>
<table class="episkops">
{html_eps}
</table>
{unused_notes}
</article>
    '''

    return result, has_err

if __name__ == '__main__':
    main()
