from __future__ import print_function

from  graphcomp import dot

import sys
import string
import parsley


class Gate(object):
    def __init__(self, op, inputs):
        self.op = op
        self.label = op.upper()
        for inp in inputs:
            inp.outputs.add(self)
        self.inputs = set(inputs)
        self.outputs = set()
        self.value = None

    def eval(self):
        inpt = [n.value for n in self.inputs]
        if self.op == 'and':
            self.value = all(inpt)
        elif self.op == 'or':
            self.value = any(inpt)
        else:
            i, = inpt
            self.value = not(i)


class Input(object):
    def __init__(self, label):
        self.label = label
        self.value = None
        self.outputs = set()

    @property
    def inputs(self):
        return list()

    def eval(self):
        for o in self.outputs:
            o.inputs.add(self)


class Output(object):
    def __init__(self, label, inputs):
        self.label = label
        self.value = None
        for inp in inputs:
            inp.outputs.add(self)
        self.inputs = set(inputs)

    @property
    def outputs(self):
        return set()

    def eval(self):
        n, = self.inputs
        self.value = n.value


class Circuit(object):
    def __init__(self):
        self.input_nodes = dict()
        self.output_nodes = dict()
        self.gates = dict()

    def eval(self, true_inputs):
        for k, v in self.input_nodes.items():
            v.value = k in true_inputs
        nodes = self.input_nodes.values()
        while nodes:
            n = nodes.pop(0)
            n.eval()
            nodes.extend(n.outputs)

    def dot(self,
            true_style={'color': '#00aa00'},
            false_style={'color': '#aa4444'}):

        g = dot.Graph(splines='ortho', nodesep='0.8')
        ig = g.subgraph(rank='same')
        og = g.subgraph(rank='same')

        styles = {True: true_style, False: false_style, None: {}}

        i_nodes = dict((n, ig.node(n.label, **styles[n.value])) for n in
                       self.input_nodes.values())

        nodes = [(n, og.node(n.label, **styles[n.value])) for n in
                 self.output_nodes.values()]

        while nodes:
            n, dot_n = nodes.pop(0)
            for i in n.inputs:
                if i in self.input_nodes.values():
                    dot_i = i_nodes[i]
                else:
                    dot_i = g.node(i.label, shape='box', **styles[i.value])
                g.edge(dot_i, dot_n, **styles[i.value])
                nodes.append((i, dot_i))
        return g


class ASTNode(object):
    def __init__(self, typ, *args):
        self.typ = typ
        self.parent = None

        if typ in ['input', 'output']:
            self.id = args[0]
            if typ == 'output':
                self.children = tuple(args[1:])
        else:
            self.children = args
            for c in self.children:
                c.parent = self

    def make_circuit(self):
        c = Circuit()
        self.circuit(c)
        return c

    def circuit(self, circ, inp=None):
        if self.typ == 'output_list':
            for c in self.children:
                c.circuit(circ)
            return
        elif self.typ == 'input':
            n = circ.input_nodes.setdefault(self.id, Input(self.id))
        else:
            inp = [c.circuit(circ) for c in self.children]
            if self.typ == 'output':
                assert self.id not in circ.output_nodes
                n = Output(self.id, inp)
                circ.output_nodes[self.id] = n
            else:
                n = Gate(self.typ, inp)
        return n

    def dot(self, graph=None, parent=None):
        if graph is None:
            graph = dot.Graph()
        n = graph.node(self.typ)
        if parent is not None:
            graph.edge(parent, n)
        if self.typ != 'input':
            for c in self.children:
                c.dot(graph, n)
        return graph

    def __repr__(self):
        if self.typ == 'input':
            s = self.id
        else:
            s = ', '.join(repr(c) for c in self.children)
        return 'ASTNode({}: {})'.format(self.typ, s)


gr = r"""
lower = anything:x ?(x in string.ascii_lowercase)
upper = anything:x ?(x in string.ascii_uppercase)
alnum = anything:x ?(x in string.ascii_letters + string.digits)

id_input = <lower alnum*>:x -> x
id_output = <upper alnum*>:x -> x

input = id_input:x -> Node('input', x)

term = ( '~' term:x -> Node('not', x)
       | '(' ws expr:x ws ')' -> x
       | input )

and = ( and:x ws '&' ws term:y -> Node('and', x, y)
      | term )

or = ( or:x ws '|' ws and:y -> Node('or', x, y)
     | and )

expr =  ws or:x ws -> x

output = id_output:x ws '=' expr:y -> Node('output', x, y)

output_list = ( output:x ws ',' ws output_list:y -> Node('output_list', x, y)
              | output)

circuit = ( output_list
          | expr:x -> Node('output', 'Output', x) )

true_inputs = (id_input:x ws -> x)+

ast = circuit:c ( ';' ws true_inputs:t ';'? ws -> (c, t)
                | ';'? ws -> (c, None) )
"""
grammar = parsley.makeGrammar(gr , {'string': string, 'Node': ASTNode})

def comp(inputstr):
    ast, values = grammar(sys.argv[1]).ast()
    c = ast.make_circuit()
    if values:
        c.eval(values)
    return c.dot(), ast.dot()


if __name__ == '__main__':
    g, ast = comp(sys.argv[1])
    print(g.render(tool='dot'))
