# Проверяет корректность парсинга данных раздела о епископах.
# Сравнивает данные из xml вёрстки книги с построенным парсером utils/full-episkops-parser json файлом


# при разработке парсера этот xml был поправлен по сравнению с xml вёрстки книги
# правки просмотрены глазами - они несущественны.
# Внесённые правки сводятся к склеиванию подряд идущих кусков текста и удалению ненужных тегов с пробельными символами.
EPISKOP_XML = '../data/full_episkops.xml'

# результат работы парсера
EPISKOP_JSON = '../data/full_episkops.json'
#EPISKOP_JSON = '../data/edit-init/episkop-edit.json'

import sys
from pathlib import Path
sys.path.append(str(Path('..').resolve()))

import json
import re

from chain import Chain, ChainLink, XmlSax, SaxItem, Printer

class EpiskopJsonXmlChecker(ChainLink):
    def __init__(self, parsed_json):
        assert isinstance(parsed_json, list)
        self.episkops = parsed_json
        self._i = None
        
        self._reset_xml_ep()
        self._xml_state = 'NeedPerson'
        
        self._skip_text = False
        
    def _reset_xml_ep(self):
        self._xml_text = ''
        self._xml_obn_tags = []
        
    
    def process(self, xml: SaxItem):
        try:
            if xml.event == 'text':
                if not self._skip_text:
                    self._add_text(xml.data)
            elif xml.event == 'start':
                self._skip_text = False
                if xml.name.lower() == 'br':
                    self._add_text('\n')
                elif xml.name == 'AppliedFont':
                    self._skip_text = True
                elif xml.name == 'ParagraphStyleRange':
                    attr = xml.data.get('AppliedParagraphStyle')
                    if 'Персона' in attr:                        
                        self._new_episkop()
                    
                    if ' Обн' in attr:
                        self._add_obn_tag(xml)
                    else:
                        self._add_not_obn()
            # TODO check last caf is obn for obn ep
            # check last caf is not obn for not obn ep
                    # Так можно найти епископов, которые
                    # некоторое время были обновленцами,
                    # но в итоге после покаяния вернулись
                    #if ' Обн' in attr:
                    #    self._set_obn()
        except Exception as err:
            print(str(err))
            print("xml state:  ", self._xml_state)
            print("xml obn?:   ", self._is_xml_obn)
            print("xml text:   ", self._xml_text)
            print("sax:        ", xml)
            sys.exit(1)
            
    def finish(self):
        if self._xml_state != 'NeedPersonOrText':
            raise CheckError('Expected NeedPersonOrText state')
        
        if self._xml_text:            
            self._compare_current_episkop()
            if self._i != len(self.episkops) - 1:
                raise CheckError(
                    'В json есть ещё епископы, а xml кончился: ' + \
                    f'{self._i} != {len(self.episkops)}-1'
                )
        print("Compare OK")
                
    
    def _new_episkop(self):
        if self._xml_state not in ('NeedPersonOrText', 'NeedPerson'):
            raise CheckError('Expected NeepPerson[OrText] state')
        
        if self._i:
            self._compare_current_episkop()
        
        self._xml_state = 'NeedText'
        self._reset_xml_ep()
        
        self._i = self._i + 1 if self._i is not None else 0
    
    def _compare_current_episkop(self):
        if self._xml_text:
            xml_ep = self._xml_text
            json_ep = self.episkops[self._i]
            xml_obn = self._is_xml_obn
            self.compare_episkop_json_xml(json_ep, xml_ep, xml_obn)
    
    def _add_obn_tag(self, xml):
        self._xml_obn_tags.append(xml)
        
    def _add_not_obn(self):
        self._xml_obn_tags.append(False)
    
    @property
    def _is_xml_obn(self):
        return self._xml_obn_tags[-1] != False
    
    def _add_text(self, text):
        if self._xml_state not in ('NeedPersonOrText', 'NeedText'):
            raise CheckError('Expected NeedText or NeedPersonOrText state')
        self._xml_state = 'NeedPersonOrText'
        self._xml_text += text
        
    @staticmethod
    def compare_episkop_json_xml(json_ep: dict, xml_ep: str, xml_obn: bool):        
        # сравнение текстов статей
        json_txt = json_ep['name']
        for caf in json_ep['appointments']:
            d = caf['dates']
            t = caf['department'] + d
            json_txt += '\n' + t
        
        json_txt = re.sub(r'\s+', '', json_txt)
        xml_ep = re.sub(r'\s+', '', xml_ep)
        if json_txt != xml_ep:
            raise CheckError('??? xml-->\n' + xml_ep + '\n' + json_txt + '\n<--json???\n')
        
        # проверка корректности признака обновленчества
        """
        С галкой обновленчества всё как всегда сложно.
        
        Есть епископы, которые некоторое время были обновленцами. Кто-то покаялся, кто-то нет.
        Как их отличить? Можно смотреть, была ли обновленческой последняя занимаемая кафедра
        (что сейчас и происходит при формировании флага xml_obn).
        
        Но это не работает. Например:
                
        Агапит Вишневский - последняя кафедра Днепропетровская, обн, но не обновленец.
        В сноске к нему в статье этой кафедры написано, что
        <<По свидетельству еп. Иоанникия (Соколовского) от 07-08.1923 г., «умер в единении со св. Церковию»
         (РГИА. Ф. 831, Оп. 1, Д. 201, Л. 12 об.).>>
        
        В разделе епископов он не обновленец (текст не курсивный).
        
        Также непонятно с самочинной Грузинской автокефалией до момента признания. В книге они курсивом.
        
        Но есть и ошибки парсера, и ошибки книги.
        
        Список таких неоднозначностей мы и выводим на экран - когда признак "обновленчества" последней кафедры
        не соответствует признаку "обновленчества" епископа в результатах парсера.
         
        Это всё надо будет выверять потом, сделав соответствующий интерфейс.
        """

        if json_ep['isRenovator'] != xml_obn:
        #    #raise CheckError(
            print(f'OBN? {json_ep["name"][:40]:40} json_obn = {json_ep["isRenovator"]} xml_obn = {xml_obn}')
        
        


class CheckError(Exception): pass
        

def check_episkops():
    with open(EPISKOP_JSON) as f:
        ep_json = json.load(f)
    ch = Chain(XmlSax(ignore_whitespace_text=True)) \
              .add(EpiskopJsonXmlChecker(ep_json))

    with open(EPISKOP_XML) as f:
        ch.process(f)
    
    
if __name__ == '__main__':
    check_episkops()
