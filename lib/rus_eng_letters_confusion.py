import re


class EngInRusWordsTextPreprocessor:
    """
    Обработчик текста для очистки кириллических слов от символов латиницы,
    выглядищих также, как кириллические символы.
    
    Например, с и c (eng), р и p (eng)

    NB! По умолчанию чинит однобуквенные слова (process(...replace_single=True)), но это может ломать гиперссылки:
    http://textarchive.ru <! /с- !>2359150.html
    """
    
    _engLetters = "AaBEeKMHOoPpCcTyXx"
    _rusLetters = "АаВЕеКМНОоРрСсТуХх"
    
    _translate_table = str.maketrans(_engLetters, _rusLetters)
    
    _re1 = re.compile("[%s]+[а-яА-ЯёЁ]" % _engLetters)
    _re2 = re.compile("[а-яА-ЯёЁ][%s]+" % _engLetters)
    
    # Замена одиночного символа
    _re3 = re.compile(r"\b[%s]\b" % _engLetters)
    
    def process(self, text, replace_single=True):
        """
        Выполняет замену английских букв на русские
        :param text: исходный текст
        :param replace_single: заменять ли одиночные буквы
        NB! Может сломать гиперссылки
        :return: исправленный текст
        """
        def lettersEngToRus(match):
            t = match.group()
            return t.translate(self._translate_table)
            
        text = self._re1.sub(lettersEngToRus, text)
        text = self._re2.sub(lettersEngToRus, text)

        if replace_single:
            text = self._re3.sub(lettersEngToRus, text)
        
        return text


if __name__ == "__main__":
    p = EngInRusWordsTextPreprocessor()
    
    eng = "Boт Taкaя cтpoчкa: CПбДА и не-по-русски c неправильными c.e-P предлогами" + p._engLetters
    rus = "Вот Такая строчка: СПбДА и не-по-русски с неправильными с.е-Р предлогами" + p._rusLetters
    
    if rus != p.process(eng):
        print("Something wrong")
    else:
        print("OK")
