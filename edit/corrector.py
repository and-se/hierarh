import os
import sys
sys.path.append(os.getcwd())
import logging
logging.basicConfig()

from edit.storage import HierarhEditStorage, TextCafedra, TextEpiskop

import re

def check_episkop_to_cafedra_links(remove_old_tasks=False):
    db = HierarhEditStorage()

    if remove_old_tasks:
        db.task.reset()

    Cafedra_name_map = {
        'ВСЕРОССИЙСКАЯ': 
            'ВСЕРОССИЙСКАЯ Митрополия Киевская и всея Руссии («Митрополия России»), Митрополия Московская и всея Руссии',
        'ВЛАДИМИРСКАЯ': 'ВЛАДИМИРСКАЯ (Суздальско-Владимирская)',
        'МОСКОВСКАЯ, обновленческая': 'МОСКОВСКАЯ I, обновленческая',
        'ЗВЕНИГОРОДСКАЯ' : 'ЗВЕНИГОРОДСКАЯ (Московская)',
        'ЗВЕНИГОРОДСКАЯ, обновленческая' : 'ЗВЕНИГОРОДСКАЯ (Московская), обновленческая',
    }
    
    for cnt, ep in enumerate(db.episkop.iterate()):
        if cnt and cnt % 100 == 0:
            logging.warning("Processed %s items", cnt)   
        task = db.task.get(coll_name=db.episkop.name, doc_key=ep.key, reg_data_when=ep.reg_data['when'])
        task.title = ep.header() + " - непонятные ссылки на кафедры"        
        task.type_ = "episkop->cafedra"

        ep = EpiskopView(ep)

        for i, caf in enumerate(ep.cafedras):
            if caf.link:
                linked = db.cafedra.get(caf.link)
                if not linked:
                    task.add_problem(i, caf, 'сломанная ссылка - нет такой кафедры', caf.link)
                else:
                    linked = CafedraView(linked)
                    if not linked.has_name(caf.name):
                        task.add_problem(i, caf, 'Проставлена сылка на кафедру', linked.name, 'Это верно?')
            else:
                #if caf in db.cafedra.ignored_names:                
                    # не нужно проставлять ссылки на ?, NN
                    #continue
                
                search_name = caf.name
                if caf.name in Cafedra_name_map:
                    search_name = Cafedra_name_map[caf.name]

                found_cafs = db.cafedra.find_by_name(search_name)
                if len(found_cafs) == 1:
                    ... # проставить ссылку на кафедру
                elif not len(found_cafs):
                    task.add_problem(i, caf, "кафедра не найдена")
                else: # many cafedra
                    task.add_problem(i, caf, "какая именно кафедра?", found_cafs)            
        
        if task.changed:
            task.save()


from lxml import html

"""
Структурированное представление html данных епископа
"""
class EpiskopView:
    def __init__(self, data: TextEpiskop):
        self._text = data
        self._tree = html.fragment_fromstring(data.html)    
    
    @property
    def cafedras(self) -> list['CafedraRowView']:
        # отбираем строки таблицы епископов, которые не являются заголовками
        rows = self._tree.xpath("""//table[contains(@class, 'cafedras')]/tbody/tr[not(contains(@class, 'header-row'))]""")
        return [CafedraRowView(r) for r in rows]


from edit.init_db_creator import CAFEDRA_MAP_FILE
import json

"""
Структурированное представление строки таблицы кафедр в html епископа
"""
class CafedraRowView:    
    def __init__(self, tr: html.HtmlElement):
        self.d = tr
        self.caf = tr[0]
        assert self.caf.tag == 'td'

        self._name = None
 
    @property
    def name(self):
        if not self._name:
            self._name = self.get_cafedra_name_in_episkop(self.caf.text_content())
        return self._name
    
    @property
    def link(self):
        return None  # TODO now no links

    @property
    def dating(self):
        return self.d[1].text_content().strip()
    
    def __repr__(self):
        return f"CafedraRow({self.name} {self.dating})"
    
    def __str__(self):
        return f"{self.name} ({self.dating})"
    
    with open(CAFEDRA_MAP_FILE, encoding='utf8') as f:
        Cafedra_name_map = json.load(f)

    @classmethod
    def get_cafedra_name_in_episkop(cls, caf_td: str):
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







"""
Структурированное представление html данных кафедры
"""
class CafedraView:
    def __init__(self, data: TextCafedra):
        self._text = data
        #self.d = html.fragment_fromstring(data.html)

    def has_name(self, name: str):
        return name.lower().strip() == self._text.header()
        # TODO other names...
    
    



    
if __name__ == '__main__':
    #check_episkop_to_cafedra_links()
    check_episkop_to_cafedra_links(remove_old_tasks=True)