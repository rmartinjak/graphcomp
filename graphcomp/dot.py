import sys
import subprocess
import string
from itertools import product, chain
from random import shuffle


class ToolError(Exception):
    pass


def format_attr(attr):
    return ', '.join('{} = "{}"'.format(*x) for x in attr.items())


class IdGen(object):
    def __init__(self, length=2, chars=string.lowercase):
        self.chars = chars
        self.length = length
        self.gen()

    def gen(self):
        self.ids = list(product(self.chars, repeat=self.length))
        shuffle(self.ids)

    def __call__(self):
        if not self.ids:
            self.length += 1
            self.gen()
        return ''.join(self.ids.pop(0))

id_gen = IdGen(2)


class Node(object):
    def __init__(self, label, **kwargs):
        self.attr = kwargs
        self.attr['label'] = label
        self.id = 'node_' + id_gen()

    def dot(self, f):
        f.write('{} [ {} ]\n'.format(self.id, format_attr(self.attr)))


class Edge(object):
    def __init__(self, node_from, node_to, **kwargs):
        self.node_from = node_from
        self.node_to = node_to
        self.attr = kwargs

    def dot(self, f):
        f.write('{} -> {} [ {} ]\n'.format(self.node_from.id,
                                           self.node_to.id,
                                           format_attr(self.attr)))


class Subgraph(object):
    typename = 'subgraph'
    typ = 'subgraph'

    def __init__(self, **kwargs):
        self.id = self.typename + '_' + id_gen()
        self.attr = kwargs
        self.node_attr = {}
        self.nodes = list()
        self.subgraphs = list()
        self.edges = list()

    def node(self, label, **kwargs):
        n = Node(label, **kwargs)
        self.nodes.append(n)
        return n

    def subgraph(self, **kwargs):
        s = Subgraph(**kwargs)
        self.subgraphs.append(s)
        return s

    def edge(self, node_from, node_to, **kwargs):
        self.edges.append(Edge(node_from, node_to, **kwargs))

    def dot(self, f=sys.stdout):
        f.write('{} {} {{\n'.format(self.typ, self.id))
        f.write('node [ {} ]'.format(format_attr(self.node_attr)))
        f.writelines('{} = "{}"\n'.format(*x) for x in self.attr.items())
        for c in chain(self.subgraphs, self.nodes, self.edges):
            c.dot(f)
        f.write('}\n')


class Graph(Subgraph):
    typename = 'graph'

    def __init__(self, name='"graph"', typ='digraph', **kwargs):
        super(Graph, self).__init__(**kwargs)
        self.id = name
        self.typ = typ

    def render(self, fmt='svg', tool='dot'):
        p = subprocess.Popen([tool, '-T', fmt],
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        self.dot(p.stdin)
        out, err = p.communicate()
        if err:
            raise ToolError(err)
        return out
