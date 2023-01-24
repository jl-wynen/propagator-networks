from __future__ import annotations
from dataclasses import dataclass, field
import math
from typing import Any, Callable

from .graph import mermaid


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

    def __init__(self, sup: set[str] | str | None = None) -> None:
        if isinstance(sup, str):
            sup = {sup}
        self.sup = sup or set()

    def more_informative_than(self, other: Support) -> bool:
        return self.sup != other.sup and self.sup.issubset(other.sup)

    def merge(self, other: Support) -> Support:
        return Support(self.sup | other.sup)


# called v&s in thesis
@dataclass(frozen=True)
class Datum:
    value: Any
    support: Support = field(default_factory=Support)

    def merge(self, other: Datum) -> Datum:
        v1 = self.value
        v2 = other.value
        vm = merge(v1, v2)

        if vm == v1:
            if implies(v2, vm):
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
        return Datum(value=sqrt(self.value), support=self.support)

    def __str__(self) -> str:
        if self.support.sup:
            return f"{self.value} because of {{{', '.join(self.support.sup)}}}"
        return str(self.value)


@dataclass(frozen=True)
class Interval:
    lo: float
    hi: float

    @staticmethod
    def intervalise(x) -> Interval:
        if isinstance(x, Interval):
            return x
        return Interval(lo=x, hi=x)

    def __add__(self, other):
        other = Interval.intervalise(other)
        return Interval(self.lo + other.lo, self.hi + other.hi)

    def __mul__(self, other):
        other = Interval.intervalise(other)
        return Interval(self.lo * other.lo, self.hi * other.hi)

    def __rmul__(self, other):
        other = Interval.intervalise(other)
        return Interval(other.lo * self.lo, other.hi * self.hi)

    def __truediv__(self, other):
        other = Interval.intervalise(other)
        return Interval(self.lo / other.hi, self.hi / other.lo)

    def __pow__(self, power):
        if isinstance(power, Interval):
            if power.lo != power.hi:
                raise NotImplementedError("Only intervals with equal lo and hi are supported")
            power = power.lo
        if power != 2:
            raise NotImplementedError("Can only raise to power of 2")
        return Interval(self.lo ** 2, self.hi ** 2)

    def sqrt(self):
        return Interval(math.sqrt(self.lo), math.sqrt(self.hi))

    def intersect(self, other: Interval) -> Interval:
        other= Interval.intervalise(other)
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

    def __str__(self) -> str:
        return f"[{self.lo}, {self.hi}]"


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

    def __str__(self) -> str:
        return str(self.value)


def merge(a, b):
    if isinstance(a, Interval):
        return a.merge(b)
    if isinstance(b, Interval):
        return Interval.intervalise(a).merge(b)
    if a != b:
        raise RuntimeError(f"Clashing numbers: {a} and {b}")
    return a


def implies(a, b):
    return a == merge(a, b)


def sqrt(x):
    if isinstance(x, (int, float)):
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
squarer = make_propagator(lambda a: a ** Datum(2))
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
