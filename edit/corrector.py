import os
import sys
sys.path.append(os.getcwd())

from edit.storage import HierarhEditStorage, TextCafedra, TextEpiskop

def check_episkop_to_cafedra_links():
    db = HierarhEditStorage()
    
    for ep in db.episkop.iterate():  #.portion(0, 20):        
        task = db.task.get_opened(db.episkop.name, ep.key, ep.reg_data['when'])
        ep = EpiskopView(ep)

        for i, caf in enumerate(ep.cafedras):
            if caf.link:
                linked = db.cafedra.get(caf.link)
                if not linked:
                    task.add(i, caf.name, 'сломанная ссылка - нет такой кафедры', caf.link)
                else:
                    linked = CafedraView(linked)
                    if not linked.has_name(caf.name):
                        task.add(i, caf.name, 'Проставлена сылка на кафедру', linked.name, 'Это верно?')
            else:
                #if caf in db.cafedra.ignored_names:                
                    # не нужно проставлять ссылки на ?, NN
                    #continue
                
                found_cafs = db.cafedra.find_by_name(caf.name)
                if len(found_cafs) == 1:
                    ... # проставить ссылку на кафедру
                elif not len(found_cafs):
                    task.add(i, caf.name, "не найдена кафедра")
                else: # many cafedra
                    task.add(i, caf.name, "какая именно кафедра?", found_cafs)
        
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


"""
Структурированное представление строки таблицы кафедр в html епископа
"""
class CafedraRowView:
    def __init__(self, tr: html.HtmlElement):
        self.d = tr
        self.caf = tr[0]
        assert self.caf.tag == 'td'
 
    @property
    def name(self):
        return self.caf.text_content()
    
    @property
    def link(self):
        return None  # TODO now no links
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return f"CafedraRow({self.name})"
    

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
    check_episkop_to_cafedra_links()