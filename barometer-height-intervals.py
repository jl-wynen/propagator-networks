"""
Measuring the height of a building with a barometer.
Uses intervals as cell content.

Section 3.3
"""

from __future__ import annotations
from dataclasses import dataclass, field
import math
from typing import Callable


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


@dataclass
class Cell:
    value: Interval | None = None
    neighbors: list[Callable] = field(default_factory=list)

    def content(self) -> Interval:
        return self.value

    def add_content(self, increment: Interval | None, net: Network):
        if increment is None:
            return
        if self.value is None:
            self.value = increment
        else:
            new_range = self.value.intersect(increment)
            if new_range == self.value:
                return
            if new_range.is_empty():
                raise ValueError("empty interval")
            self.value = new_range
        net.alert_propagator(*self.neighbors)

    def add_neighbor(self, new_neighbor: Callable, net: Network):
        if new_neighbor not in self.neighbors:
            self.neighbors.append(new_neighbor)
            net.alert_propagator(new_neighbor)


@dataclass
class Interval:
    lo: float
    hi: float

    def __add__(self, other):
        return Interval(self.lo + other.lo, self.hi + other.hi)

    def __sub__(self, other):
        return Interval(self.lo - other.lo, self.hi - other.hi)

    def __mul__(self, other):
        return Interval(self.lo * other.lo, self.hi * other.hi)

    def __truediv__(self, other):
        return Interval(self.lo / other.lo, self.hi / other.hi)

    def __pow__(self, power):
        return Interval(self.lo ** 2, self.hi ** 2)

    def sqrt(self):
        return Interval(sqrt(self.lo), sqrt(self.hi))

    def intersect(self, other: Interval) -> Interval:
        return Interval(max(self.lo, other.lo),
                        min(self.hi, other.hi))

    def is_empty(self):
        return self.lo > self.hi


def sqrt(x):
    if isinstance(x, float):
        return math.sqrt(x)
    return x.sqrt()


def propagator(neighbors: list[Cell], func: Callable, net: Network):
    for cell in neighbors:
        cell.add_neighbor(func, net)
    net.alert_propagator(func)


def call_if_full_information(func, cells):
    values = list(map(Cell.content, cells))
    if any(v is None for v in values):
        return None
    return func(*values)


def make_propagator(func: Callable):
    def maker(*cells, net: Network):
        output = cells[-1]
        inp = cells[:-1]
        impl = lambda: output.add_content(call_if_full_information(func, inp), net)
        propagator(inp, impl, net)

    return maker


adder = make_propagator(lambda a, b: a + b)
subtractor = make_propagator(lambda a, b: a - b)
multiplier = make_propagator(lambda a, b: a * b)
divider = make_propagator(lambda a, b: a / b)
squarer = make_propagator(lambda a: a ** 2)
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
    g = net.add_cell('g', Cell(Interval(9.789, 9.832)))
    half = net.add_cell('half', Cell(Interval(0.5, 0.5)))
    t2 = net.add_cell('t^2', Cell())
    gt2 = net.add_cell('gt^2', Cell())
    t = net.add_cell('t', Cell())
    h = net.add_cell('h', Cell())

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
    product_(building_shadow, ratio, net['h'], net=net)


def main():
    net = fall_duration()
    fall_time = net['t']
    building_height = net['h']
    fall_time.add_content(Interval(2.9, 3.1), net=net)
    net.run()
    print('building height: ', building_height.content())

    # add method of triangles
    similar_triangles(net)
    net['building_shadow'].add_content(Interval(54.9, 55.1), net=net)
    net['barometer_height'].add_content(Interval(0.3, 0.32), net=net)
    net['barometer_shadow'].add_content(Interval(0.36, 0.37), net=net)

    net.run()
    print('building height: ', building_height.content())
    print('fall time: ', fall_time.content())  # more precise!!

    # make fall time crappy
    fall_time.add_content(Interval(0.1, 4.09), net=net)
    net.run()
    print('building height: ', building_height.content())  # still as good
    print('fall time: ', fall_time.content())  # a better measurement again


if __name__ == '__main__':
    main()
