import unittest
from pathlib import Path
import os

TestDbName = 'data/test-hierarh-edit.sqlite3'

if __name__ == '__main__':
    import sys
    sys.path.append(str(Path(__file__).parent.parent))


# Подменяем БД для редактирования
import settings
settings.EditDbName = TestDbName

# Теперь подключаем модуль storage - при этом он настроится на тестовую БД
import storage
from storage import TextCafedra


def load_file(test_file, key=None):
    path = Path(__file__).parent.joinpath('testdata').joinpath(test_file)
    with open(path) as f:
        html = f.read()
        return TextCafedra.from_html(key, html)


class TestStorage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("start storage test")
        if os.path.exists(TestDbName):
            print("Remove old db", TestDbName)
            os.remove(TestDbName)

        print("create new db")
        storage.init_edit_db()

        TestStorage.db = storage.HierarhEditStorage()
        assert storage.EditDb.database == TestDbName

        TestStorage.cafedra = TestStorage.db.cafedra

    @classmethod
    def tearDownClass(cls):
        print("end storage test")

    def test_crud(self):
        # create
        #n = self.db.new()
        n = load_file('1.html')
        self.assertEqual(n.key, None)

        n2 = self.cafedra.upsert(n)
        self.assertTrue(n2.key is not None)
        self.assertTrue(id(n2) == id(n))

        n3 = self.cafedra.get(n2.key)
        self.checkCafEqual(n2, n3)
        self.assertTrue('when' in n3.reg_data)

        mn = self.cafedra.portion(take=1)
        self.assertEqual(len(mn), 1)
        n4 = mn[0]
        self.checkCafEqual(n2, n4)

        # Модифицировали html, но не трогали reg_data.when
        # --> оно не изменилось
        n4.html = load_file('1-div.html').html
        n5 = self.cafedra.upsert(n4)
        self.assertTrue(id(n5) == id(n4))

        # Новый объект без reg_data -> when изменился
        n6 = load_file('1.html')
        n6.key = n5.key
        self.cafedra.upsert(n6)
        self.assertGreater(n6.reg_data['when'], n5.reg_data['when'])

    def checkCafEqual(self, c1, c2):
        self.assertEqual(c1.key, c2.key)
        self.assertEqual(c1.html, c2.html)



if __name__ == '__main__':
    unittest.main(verbosity=2, failfast=True)
