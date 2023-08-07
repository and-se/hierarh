from dataclasses import dataclass, field, asdict
from typing import Union, List, Dict, Tuple, Union

@dataclass
class CafedraArticle:
    header: str = None
    is_obn: bool = False
    is_link: bool = False
    start_line: int = None
    
    text: str = None
    # episkop in cafedra info header as str - fro ex. 'Архиепископы и митрополиты Московские;'
    episkops: List[Union['EpiskopInCafedra', str]] = field(default_factory = list)
    notes: List['ArticleNote'] = field(default_factory = list)

    @staticmethod
    def from_dict(d):
        res = CafedraArticle(**d)
        for i in range(len(res.episkops)):
            ep = res.episkops[i]
            if isinstance(ep, dict):
                res.episkops[i] = EpiskopInCafedra(**ep)

        for i in range(len(res.notes)):
            nt = res.notes[i]
            if isinstance(nt, dict):
                res.notes[i] = ArticleNote(**nt)

        return res
                

@dataclass
class EpiskopInCafedra:
    begin_dating: str = None
    end_dating: str = None
    who: str = None
    unparsed_data: str = None


@dataclass
class ArticleNote:
    num: int
    text: str
