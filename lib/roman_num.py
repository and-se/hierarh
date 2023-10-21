
_d  = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII']

def to_roman(num: int) -> str:
    if 1 <= num <= 7:
        return _d[num-1]
    raise ValueError('Expected num between 1 and 7')

def from_roman(num: str) -> int:
    num = num.strip().upper()
    if num in _d:
        return _d.index(num)+1
    raise ValueError(f'Expected num between {_d[0]} and {_d[-1]}')


if __name__ == '__main__':
    for n, rn in zip(range(1, 8), _d):
        assert to_roman(n) == rn
        assert from_roman(rn) == n
        assert to_roman(from_roman(rn)) == rn

    try:
        to_roman(100)
        assert("Must fail")
    except ValueError:
        pass

    try:
        from_roman('abcde')
        assert("Must fail 2")
    except ValueError:
        pass

    print("Ok")

