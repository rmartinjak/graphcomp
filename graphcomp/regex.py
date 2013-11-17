from __future__ import print_function

import sys
import string
import itertools
import parsley

from graphcomp import dot

special_chars = r'|*?+()\\'
epsilon = u'\u03b5'.encode('utf-8')


class AST(object):
    def __init__(self):
        self.id_gen = itertools.count()
        self.pos_gen = itertools.count()
        self.root = None

    def node(self, typ, *args):
        return ASTNode(self, typ, *args)

    def calc_followpos(self):
        self.root.calc_followpos()

    def dfa(self, alphabet=string.printable):
        self.calc_followpos()
        marked = set()
        unmarked = set()
        unmarked.add(tuple(sorted(self.root.children[0].firstpos)))
        trans = {}

        while unmarked:
            S = unmarked.pop()
            marked.add(S)
            for a in alphabet:
                U = set()
                for p in S:
                    if p.typ == a:
                        U.update(p.followpos)
                U = tuple(sorted(U))
                if not U:
                    continue
                if U not in marked.union(unmarked):
                    unmarked.add(U)
                trans[S, a] = U
        return marked, trans

    def dfa_dot(self, title, graph_label):
        states, trans = self.dfa()
        g = dot.Graph('dfa', label=graph_label)
        nodes = {}

        for s in states:
            label = ','.join(sorted(repr(x) for x in s))
            if any(x.typ == 'end' for x in s):
                n = g.node(label, style='bold,filled', bgcolor='grey')
            else:
                n = g.node(label, style='solid')
            nodes[s] = n

        for k, v in trans.items():
            s, a = k
            g.edge(nodes[s], nodes[v], label=a)
        return g

    def dot(self, **kwargs):
        g = dot.Graph('ast', **kwargs)
        self.root.dot(g)
        return g


class ASTNode(object):
    def __init__(self, tree, typ, *args):
        self.tree = tree
        self.typ = typ
        self.children = args
        self._firstpos = self._lastpos = None
        self.followpos = set()
        if len(typ) == 1 or typ == 'end':
            self.pos = next(self.tree.pos_gen)
        else:
            self.pos = None

    def __repr__(self):
        if self.pos is not None:
            return str(self.pos)
        return self.typ or epsilon

    def __str__(self):
        s = self.typ
        if self.children:
            tmp = ', '.join(map(str, self.children))
            s += '({})'.format(tmp)
        elif self.pos is not None:
            s += '({})'.format(self.pos)
        return s

    def dot(self, graph=None, parent=None):
        if graph is None:
            graph = dot.Graph()
        n = graph.node(self.typ)
        if parent is not None:
            graph.edge(parent, n)
        for c in self.children:
            c.dot(graph, n)
        return graph

    @property
    def nullable(self):
        if self.typ in ['', 'star', 'qmark']:
            return True
        if self.typ == 'or':
            c1, c2 = self.children
            return c1.nullable or c2.nullable
        if self.typ == 'cat':
            c1, c2 = self.children
            return c1.nullable and c2.nullable
        if self.typ == 'plus':
            c1, = self.children
            return c1.nullable
        # non-epsilon leaf
        return False

    @property
    def firstpos(self):
        if self._firstpos is None:
            self.calc_pos()
        return self._firstpos

    @property
    def lastpos(self):
        if self._firstpos is None:
            self.calc_pos()
        return self._lastpos

    def calc_pos(self):
        if self.typ == '':
            self._firstpos = frozenset()
            self._lastpos = frozenset()

        elif self.typ == 'or':
            c1, c2 = self.children
            self._firstpos = c1.firstpos.union(c2.firstpos)
            self._lastpos = c1.lastpos.union(c2.lastpos)

        elif self.typ == 'cat':
            c1, c2 = self.children
            if c1.nullable:
                self._firstpos = c1.firstpos.union(c2.firstpos)
            else:
                self._firstpos = c1.firstpos
            if c2.nullable:
                self._lastpos = c2.lastpos.union(c1.lastpos)
            else:
                self._lastpos = c2.lastpos

        elif self.typ in ['star', 'plus', 'qmark']:
            c1, = self.children
            self._firstpos = c1.firstpos
            self._lastpos = c1.lastpos

        else:
            self._lastpos = self._firstpos = frozenset([self])

    def calc_followpos(self):
        if self.typ == 'cat':
            c1, c2 = self.children
            for c in c1.lastpos:
                c.followpos.update(c2.firstpos)

        if self.typ in ['star', 'plus']:
            for c in self.lastpos:
                c.followpos.update(self.firstpos)

        for c in self.children:
            c.calc_followpos()


def comp(inputstr):
    gr = r"""
    esc = '\\' anything:x -> x
    symbol = ( anything:x ?(x not in '|*?+()\\') | esc:x ) -> Node(x)
    group = '(' expr:x ')' -> x

    repeat = (group | symbol):x ( '*' -> Node('star', x)
                                | '+' -> Node('plus', x)
                                | '?' -> Node('qmark', x)
                                | -> x )

    cat =  ( cat:x repeat:y -> Node('cat', x, y)
           | repeat )

    or = ( or:x '|' cat:y -> Node('or', x, y)
         | cat )

    expr =  or?:x -> x or Node('')

    ast = expr:x -> Node('root', Node('cat', x, Node('end')))

    """
    tree = AST()
    grammar = parsley.makeGrammar(
        gr, {'special_chars': r'|*?+()\\', 'Node': tree.node})
    tree.root = grammar(inputstr).ast()
    dfa = tree.dfa_dot('dfa', inputstr)
    return dfa, tree.dot()

if __name__ == '__main__':
    g, ast = comp(sys.argv[1])
    print(g.render(tool='circo'))
