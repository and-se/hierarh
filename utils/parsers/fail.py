from dataclasses import dataclass


@dataclass
class ParseFail:
    text: str
    code: str
    error: any
