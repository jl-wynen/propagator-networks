"""
Measuring the height of a building with a barometer.
Uses intervals as cell content.
Tracks dependencies.

Section 4.1
"""

from __future__ import annotations
from dataclasses import dataclass, field
import math
from typing import Any, Callable


@dataclass
class Network:
    cells: dict[str, Cell] = field(default_factory=dict)
    alerted_propagators: list[Callable] = field(default_factory=list)
    propagators_ever_alerted: list[Callable] = field(default_factory=list)

    def add_cell(self, name: str, cell: Cell):
        self.cells[name] = cell
        return cell

    def alert_propagator(self, *propagators):
        for prop in propagators:
            if prop not in self.alerted_propagators:
                self.alerted_propagators.append(prop)
            if prop not in self.propagators_ever_alerted:
                self.propagators_ever_alerted.append(prop)

    def run(self):
        while self.alerted_propagators:
            prop = self.alerted_propagators.pop(0)
            prop()

    def __getitem__(self, key):
        return self.cells[key]


@dataclass(init=False)
class Support:
    sup: set[str]

    def __init__(self, sup: set[str] | None = None) -> None:
        self.sup = sup or set()

    def more_informative_than(self, other: Support) -> bool:
        return self.sup != other.sup and self.sup.issubset(other.sup)

    def merge(self, other: Support) -> Support:
        return Support(self.sup | other.sup)


# called v&s in thesis
@dataclass(frozen=True)
class Datum:
    value: Any
    support: Support

    def merge(self, other: Datum) -> Datum:
        v1 = self.value
        v2 = other.value
        vm = v1.merge(v2)

        if vm == v1:
            if v2.implies(vm):
                if other.support.more_informative_than(self.support):
                    return other
                return self
            return self
        elif vm == v2:
            return other
        else:
            return Datum(value=vm, support=self.support.merge(other.support))

    def __add__(self, other: Datum) -> Datum:
        return Datum(value=self.value + other.value, support=self.support.merge(other.support))

    def __sub__(self, other: Datum) -> Datum:
        return Datum(value=self.value - other.value, support=self.support.merge(other.support))

    def __mul__(self, other: Datum) -> Datum:
        return Datum(value=self.value * other.value, support=self.support.merge(other.support))

    def __truediv__(self, other: Datum) -> Datum:
        return Datum(value=self.value / other.value, support=self.support.merge(other.support))

    def __pow__(self, power: Datum) -> Datum:
        return Datum(value=self.value ** power.value, support=self.support.merge(power.support))

    def sqrt(self) -> Datum:
        return Datum(value=self.value.sqrt(), support=self.support)


@dataclass(frozen=True)
class Interval:
    lo: float
    hi: float

    def __add__(self, other):
        return Interval(self.lo + other.lo, self.hi + other.hi)

    def __mul__(self, other):
        return Interval(self.lo * other.lo, self.hi * other.hi)

    def __truediv__(self, other):
        return Interval(self.lo / other.hi, self.hi / other.lo)

    def __pow__(self, power):
        return Interval(self.lo ** 2, self.hi ** 2)

    def sqrt(self):
        return Interval(math.sqrt(self.lo), math.sqrt(self.hi))

    def intersect(self, other: Interval) -> Interval:
        return Interval(max(self.lo, other.lo),
                        min(self.hi, other.hi))

    def is_empty(self):
        return self.lo > self.hi

    def merge(self, other: Interval) -> Interval:
        new = self.intersect(other)
        if new == self:
            return self
        if new.is_empty():
            raise ValueError("empty interval")
        return new

    def implies(self, other: Interval) -> bool:
        return self == self.merge(other)


@dataclass
class Cell:
    value: Datum | None = None
    neighbors: list[Callable] = field(default_factory=list)

    def content(self) -> Datum:
        return self.value

    def add_content(self, increment: Datum | None, net: Network):
        if increment is None:
            return
        if self.value is None:
            self.value = increment
        else:
            if (merged := self.value.merge(increment)) == self.value:
                return
            self.value = merged
        net.alert_propagator(*self.neighbors)

    def add_neighbor(self, new_neighbor: Callable, net: Network):
        if new_neighbor not in self.neighbors:
            self.neighbors.append(new_neighbor)
            net.alert_propagator(new_neighbor)


def sqrt(x):
    if isinstance(x, float):
        return math.sqrt(x)
    return x.sqrt()


def propagator(neighbors: tuple[Cell], func: Callable, net: Network):
    for cell in neighbors:
        cell.add_neighbor(func, net)
    net.alert_propagator(func)


def call_if_full_information(func, cells: tuple[Cell]):
    values = list(map(Cell.content, cells))
    if any(v is None for v in values):
        return None
    # print("calling", func.__code__)
    return func(*values)


def make_propagator(func: Callable):
    def maker(*cells: Cell, net: Network):
        output = cells[-1]
        inp = cells[:-1]
        impl = lambda: output.add_content(call_if_full_information(func, inp), net)
        propagator(inp, impl, net)

    return maker


adder = make_propagator(lambda a, b: a + b)
subtractor = make_propagator(lambda a, b: a - b)
multiplier = make_propagator(lambda a, b: a * b)
divider = make_propagator(lambda a, b: a / b)
squarer = make_propagator(lambda a: a ** Datum(Interval(2, 2), support=Support()))
sqrter = make_propagator(lambda a: sqrt(a))


def sum_(x, y, total, net):
    adder(x, y, total, net=net)
    subtractor(total, x, y, net=net)
    subtractor(total, y, x, net=net)


def product_(x, y, total, net):
    multiplier(x, y, total, net=net)
    divider(total, x, y, net=net)
    divider(total, y, x, net=net)


def quadratic(x, x2, net):
    squarer(x, x2, net=net)
    sqrter(x2, x, net=net)


def fall_duration():
    net = Network()
    g = net.add_cell('g', Cell(Datum(value=Interval(9.789, 9.832), support=Support())))
    half = net.add_cell('half', Cell(Datum(value=Interval(0.5, 0.5), support=Support())))
    t2 = net.add_cell('t^2', Cell())
    gt2 = net.add_cell('gt^2', Cell())
    t = net.add_cell('fall_time', Cell())
    h = net.add_cell('building_height', Cell())

    quadratic(t, t2, net=net)
    product_(g, t2, gt2, net=net)
    product_(half, gt2, h, net=net)

    return net


def similar_triangles(net):
    ratio = net.add_cell('ratio', Cell())
    barometer_height = net.add_cell('barometer_height', Cell())
    barometer_shadow = net.add_cell('barometer_shadow', Cell())
    building_shadow = net.add_cell('building_shadow', Cell())
    product_(barometer_shadow, ratio, barometer_height, net=net)
    product_(building_shadow, ratio, net['building_height'], net=net)


def report(net, name):
    datum = net[name].content()
    print(f'{name}: {datum.value} because {datum.support.sup}')


def main():
    net = fall_duration()

    similar_triangles(net)
    net['building_shadow'].add_content(Datum(value=Interval(54.9, 55.1), support=Support({'shadows'})), net=net)
    net['barometer_height'].add_content(Datum(value=Interval(0.3, 0.32), support=Support({'shadows'})), net=net)
    net['barometer_shadow'].add_content(Datum(value=Interval(0.36, 0.37), support=Support({'shadows'})), net=net)

    # shadows only
    net.run()
    report(net, 'building_height')
    print('-----')

    # lousy fall time
    net['fall_time'].add_content(Datum(value=Interval(2.9, 3.3), support=Support({'lousy_fall_time'})), net=net)
    net.run()
    report(net, 'building_height')  # determined by shadows only
    report(net, 'fall_time')  # determined by shadows, original value overwritten
    print('-----')

    # good fall time
    net['fall_time'].add_content(Datum(value=Interval(2.9, 3.1), support=Support({'good_fall_time'})), net=net)
    net.run()
    report(net, 'building_height')  # determine dy shadows and fall time
    report(net, 'fall_time')  # improved by shadows
    print('-----')

    # superintendent who knows the answer
    net['building_height'].add_content(Datum(value=Interval(45, 45), support=Support({'superintendent'})), net=net)
    net.run()
    report(net, 'building_height')  # only superintendent
    report(net, 'fall_time')  # improved by superintendent
    print('-----')


if __name__ == '__main__':
    main()
