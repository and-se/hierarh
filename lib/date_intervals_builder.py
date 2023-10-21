import calendar
from datetime import date


class DateIntervalsBuilder(object):
    def __init__(self):
        self.ready_intervals = []
        self._p_year = None
        self._p_month = None
        self._p_day = None

    def add_date(self, year, month, day):
        if year:
            self.add_year(year)
        if month:
            self.add_month(month)
        if day:
            self.add_day(day)

    def add_year(self, year):
        if self._year:
            self._push_result()
        self._year = year

    def add_month(self, month):
        if self._month:
            self._push_result()
        self._month = month

    def add_day(self, day):
        if self._day:
            self._push_result()
        self._day = day

    def add_years_range(self, min_year, max_year):
        self._year = None
        r = DateInterval()
        r.set_years_range(min_year, max_year)
        self.ready_intervals.append(r)

    def add_months_range(self, start, end):
        self._month = None
        r = DateInterval()
        r.set_year(self._year)
        r.set_months_range(start, end)
        self.ready_intervals.append(r)
        self._year = None

    def add_days_by_proportions(self, min_k: float, max_k: float):
        self._day = None
        r = DateInterval()
        r.set_year(self._year)
        r.set_month(self._month)

        mm = r.get_last_month_day(self._year, self._month) - 1
        min_day = int(min_k * mm) + 1
        max_day = int(max_k * mm) + 1
        r.set_days_range(min_day, max_day)

        self.ready_intervals.append(r)
        self._year = None

    def build(self):
        if self._year:
            self._push_result()
        return self.ready_intervals

    def _push_result(self):
        if not self._year:
            raise ValueError("Year isn't specified")

        r = DateInterval()
        r.set_year(self._year)
        if self._month:
            r.set_month(self._month)
        if self._day:
            r.set_day(self._day)

        self.ready_intervals.append(r)

    @property
    def _year(self):
        return self._p_year

    @_year.setter
    def _year(self, value):
        self._p_year = value
        self._month = None

    @property
    def _month(self):
        return self._p_month

    @_month.setter
    def _month(self, value):
        self._p_month = value
        self._day = None

    @property
    def _day(self):
        return self._p_day

    @_day.setter
    def _day(self, value):
        self._p_day = value


class DateInterval(object):
    def __init__(self):
        self.end = None
        self.begin = None

    def set_year(self, year):
        self.begin = date(year, 1, 1)
        self.end = date(year, 12, 31)

    def set_month(self, month):
        self.begin = date(self.begin.year, month, 1)
        self.end = self.begin.replace(
            day=self.get_last_month_day(self.begin.year, self.begin.month))

    def set_day(self, day):
        self.begin = date(self.begin.year, self.begin.month, day)
        self.end = self.begin

    def set_years_range(self, start, end):
        self.begin = date(start, 1, 1)
        self.end = date(end, 12, 31)

    def set_months_range(self, start, end):
        self.begin = date(self.begin.year, start, 1)
        self.end = self.begin.replace(month=end,
                                      day=self.get_last_month_day(self.begin.year, end))

    def set_days_range(self, min_day, max_day):
        self.begin = date(self.begin.year, self.begin.month, min_day)
        self.end = self.begin.replace(day=max_day)

    @staticmethod
    def get_last_month_day(year, month):
        return calendar.monthrange(year, month)[1]

    def __repr__(self) -> str:
        return "DateInterval<%s, %s>" % (self.begin, self.end)

def _test():
    d = DateInterval()
    d.set_year(2019)
    print(d)

    d.set_month(1)
    print(d)

    d.set_month(12)
    print(d)

    d.set_day(5)
    print(d)

    d.set_years_range(1910, 1920)
    print(d)

    d.set_months_range(2, 8)
    print(d)

    d.set_days_range(10, 18)
    print(d)


if __name__ == "__main__":
    _test()