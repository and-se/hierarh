# Human interactions for code


def _show_to_human(*args, greeting='HUMAN! ::'):
    # print(greeting, *args)
    print(greeting, ' '.join(str(x) for x in args)[:100])


def send(*args):
    _show_to_human(*args)


def show_exception(func):
    def _wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as ex:
            _show_to_human(ex, *args, kwargs, greeting='HUMAN! Exception ::')
            raise
    return _wrapper


if __name__ == '__main__':
    send('list text', [1, 2], 'error list msg')
    send((3, 4), 'tuple msg')

    @show_exception
    def test(a, b):
        raise Exception("error exception")

    test(4, 5)
