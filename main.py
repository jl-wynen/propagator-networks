from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Network:
    cells: dict[str, Cell] = field(default_factory=dict)
    alerted_propagators: list[Callable] = field(default_factory=list)
    propagators_ever_alerted: list[Callable] = field(default_factory=list)

    def add_cell(self, name: str, cell: Cell):
        self.cells[name] = cell

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
    value: float | None = None
    neighbors: list[Callable] = field(default_factory=list)

    def content(self) -> float:
        return self.value

    def add_content(self, increment: float | None, net: Network):
        if increment is None:
            return
        if self.value is None:
            self.value = increment
            net.alert_propagator(*self.neighbors)
        elif self.value != increment:
            raise ValueError(f"Incompatible new cell content: {increment=}, {self.value=}")

    def add_neighbor(self, new_neighbor: Callable, net: Network):
        if new_neighbor not in self.neighbors:
            self.neighbors.append(new_neighbor)
            net.alert_propagator(new_neighbor)


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


def sum_(x, y, total, net):
    adder(x, y, total, net=net)
    subtractor(total, x, y, net=net)
    subtractor(total, y, x, net=net)


def product_(x, y, total, net):
    multiplier(x, y, total, net=net)
    divider(total, x, y, net=net)
    divider(total, y, x, net=net)


def temperature_convertor():
    net = Network()
    net.add_cell('32', Cell(32))
    net.add_cell('5', Cell(5))
    net.add_cell('9', Cell(9))
    net.add_cell('many', Cell(273.15))
    for name in ('f-32', 'c*9', 'f', 'c', 'k'):
        net.add_cell(name, Cell())

    sum_(net['c'], net.cells['many'], net['k'], net=net)
    sum_(net.cells['32'], net.cells['f-32'], net['f'], net=net)
    product_(net.cells['f-32'], net.cells['5'], net.cells['c*9'], net=net)
    product_(net['c'], net.cells['9'], net.cells['c*9'], net=net)
    return net


def main():
    net = temperature_convertor()
    f, c, k = net['f'], net['c'], net['k']
    f.add_content(77.0, net=net)
    net.run()
    print('set f:', f.content(), c.content(), k.content())

    net = temperature_convertor()
    f, c, k = net['f'], net['c'], net['k']
    c.add_content(25.0, net=net)
    net.run()
    print('set c:', f.content(), c.content(), k.content())

    net = temperature_convertor()
    f, c, k = net['f'], net['c'], net['k']
    k.add_content(298.15, net=net)
    net.run()
    print('set k:', f.content(), c.content(), k.content())


if __name__ == '__main__':
    main()
