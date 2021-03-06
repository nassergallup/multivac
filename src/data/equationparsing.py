#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import random
import re as reg
import string

from collections import OrderedDict
from sympy import *
from sympy.parsing.latex import parse_latex
from sympy.parsing.latex.errors import LaTeXParsingError


# Use this to store LateX code
LATEXMAP = {}
LATEXMAPTOKENS = {}


def cleaned_latex(s):
    '''LateX requires some cleaning from original file format
    '''
    s=s.replace('$$','')
    s = reg.sub(
        r'\\begin{array}{.*?}|\\end{array}|\\begin{aligned}|\\end{aligned}',
        '',
        s
    )
    s=s.replace('&=&','=')
    s=s.replace('\(','(')
    s=s.replace('\)',')')
    s=s.lstrip().rstrip()

    return s


def extract_and_replace_latex(doc):
    '''
    Find and extract LateX, start with blockquote and then do inline
    '''
    #LateX identifiers
    latexBlock= reg.compile('\$\$.*?\$\$')
    latexInline= reg.compile('\\\\.*?\\\\\)')

    doc = reg.sub(latexBlock, replace_latex, doc)
    doc = reg.sub(latexInline, replace_latex, doc)

    return doc


def find_parens(s):
    '''
    Finds all parentheses in the string representation and returns them in an
    ordered dictionary.
    '''
    toret = OrderedDict()
    pstack = []

    for i, c in enumerate(s):
        if c == '(':
            pstack.append(i)
        elif c == ')':
            if len(pstack) == 0:
                raise IndexError("No matching closing parens at: {} for string: {}".format(i, s))
            toret[pstack.pop()] = i

    if len(pstack) > 0:
        raise IndexError("No matching opening parens at: {} for string: {}".format(i, s))
    return OrderedDict(sorted(toret.items()))


def generate_random_tag():
    '''
    Generate a random tag that begins with Ltxqtn
    '''
    while True:
        tag = ''.join(random.choices(string.ascii_lowercase, k=8))
        tag = reg.sub('a|e|i|o|u', 'z', tag)
        tag = ' Ltxqtn' + tag
        if tag.replace(' ','') not in LATEXMAP:
            break

    return tag


def get_rel(gov):
    '''
    Add the relation to the dependencies for a  final format of:
    relation(gov-#, dep-#)
    '''

    if gov in ['Equality','StrictGreaterThan','StrictLessThan','Approx','approx']:
        rel = "compare"
    elif gov in ['Mul','Add','Pow']:
        rel = "combine"
    elif gov in ['Function']:
        rel = "function"
    else:
        rel = "transform"

    return rel


def get_symbol_and_type(s):
    '''
    For LateX Symbols/Integers/Rational, return value of symbol and symbol type
    '''
    symbol = s[s.find("(")+1:s.find(")")]
    symbolType = s[0:s.find("(")]
    return symbol, symbolType


def gov_dep(s, i=1):
    '''
    Recursively called function that generates dependencies for sympy string
    representations of LateX equations.
    '''
    results = []


    # ignore inputs that don't match the formula syntax - there are some
    # "true" values here, and we don't want to recurse into our "Symbol('x')"
    # etc. tokens
    if "(" in s and not s.startswith("'"):
        # Get an OrderedDict of all our parentheses pairs
        parens = find_parens(s)

        # get our parent/governor token
        p1 = next(iter(parens))
        p2 = parens.pop(p1)


        # if it's "Function" we need to include the next parenthetical(s) in
        # the title and skip it/them so we don't try to interpret the contents
        # as dependencies
        if s[:p1] == "Function":
            gov = (s[:p2+1], i)

            while True:
                p1 = next(iter(parens))
                p_2 = parens.pop(p1)

                if p1 > p2:
                    p2 = p_2
                    break
        else:
            gov = (s[:p1], i)


        # Once we've got our parent/governor, grab the children/dependents
        # and add those dependencies to our list
        while parens:
            # get next token as a child/dependent
            p3 = next(iter(parens))
            p4 = parens.pop(p3)

            # if there's a ', ' preceding us we need to index from that, not
            # the parent parenthesis mark
            if ", " in s[:p3]:
                dep_p1 = s[:p3].rfind(", ")+2
            else:
                dep_p1 = p1+1


            # Again, if this is 'Function' include the next parenthetical
            # portion
            if s[dep_p1:p3] == "Function":
                dep = (s[dep_p1:p4+1], i+1)

                while True:
                    p3 = next(iter(parens))
                    p_4 = parens.pop(p3)

                    if p3 > p4:
                        p4 = p_4
                        break
            else:
                # Get value of certain object types
                if s[dep_p1:p3] in ['Symbol', 'Integer', 'Float']:
                    dep = (s[dep_p1:p4+1], i+1)
                else:
                    dep = (s[dep_p1:p3], i+1)


            # add dependency pair to results!
            results.append((gov, dep))

            # if there are more tokens
            newResultsLength = 1
            if len(parens) > 0:
                # and the next is a child/dependent of the current
                # child/dependent token
                if next(iter(parens)) < p4:
                    # recurse

                    newResults =gov_dep(s[dep_p1:p4+1], i+1)
                    newResultsLength = len(newResults)+1
                    results += newResults

                    # and then clean up the parentheticals we just covered
                    # recursively so we don't try to parse them again at this
                    # level
                    for p in [key for key in parens if key < p4]:
                        del parens[p]

            # keep track of our token counts so we're numbering things right
            i += newResultsLength

    return results


def latexParsing(token, tokenPos):
    '''
    LateX parsing function for DIM files
    '''
    lastPos = 0

    # Each line gets stored as a separate list item in the list
    l_depTokens = []
    l_posTokens = []
    l_morTokens = []
    stringRep = ''

    # Try parsing the latex code as is
    if len(token) == 14:
        try:
            expr = parse_latex(LATEXMAP[token])
            stringRep = srepr(expr)

        except (LaTeXParsingError,SympifyError,TypeError):
            # Good chance the problem is the leading and trailing parens -
            # remove them and try again
            try:
                expr = parse_latex(LATEXMAP[token].lstrip('(').rstrip(')'))
                stringRep = srepr(expr)
            except( LaTeXParsingError, ValueError, TypeError):
                pass


    ## If we have a sympy string representation...
    if stringRep !='':

        # Problematic artefacts from sympy parsing
        stringRep = stringRep.replace(", precision=53","")
        stringRep = stringRep.replace("oo","Symbol(inf)")

        # Call gov_dep function to get list of dependencies, objects
        l_dependencies = (gov_dep(stringRep))

        # This will store each dependency item
        dictAll = {}

        # If we actually have a list of items rather than a single
        # symbol/integer
        if len(l_dependencies)>0:

            #Do the D in DIM
            for li in l_dependencies:

                head=li[0]
                tail=li[1]
                dictAll[head[1]]=head[0]
                dictAll[tail[1]]=tail[0]

                l_depTokens.append(
                    (
                        get_rel(head[0]),
                        (
                            head[0],
                            head[1]+tokenPos-1
                        ),
                        (
                            tail[0],
                            tail[1]+tokenPos-1
                        )
                    )
                )

                if head[1]> lastPos:
                    lastPos = head[1]

                if tail[1]> lastPos:
                    lastPos = tail[1]

        ## We're dealing with just a symbol or integer
        else:

            #Keep track of govs for debugging
            dictAll[1]=stringRep
            lastPos = 1

        ## Do the I and M in DIM
        for key, val in dictAll.items():

            # IF it's a symbol/integer
            if '(' in val:
                symbol, symbolType =get_symbol_and_type(val)
                l_posTokens.append('{}_{}'.format(val,symbolType.upper()))
                l_morTokens.append(val)
            else:
                thisPos = get_rel(val)
                thisPos = thisPos.upper()

                l_posTokens.append('{}_{}'.format(val, thisPos))
                l_morTokens.append(val)

    return l_depTokens, l_posTokens, l_morTokens


def put_equation_tokens_in_text(m):
    """ This is a scaled down version of create_parse_files(), to be used for
        GloVe embeddings. Instead of creating DIM files, it maps equation
        tokens to the latexEquation## for recreating the text files.
    """
    token = m.group()
    (
        l_depTokens_latex_sub_tuples,
        l_posTokens_latex_sub,
        l_morTokens_latex_sub = latexParsing(token, 0)
    )

    return ' '.join(l_morTokens_latex_sub)


def replace_latex(m):
    '''
    Replace LateX equations with placeholder token, with format LateXEquation
    '''
    latexStr = m.group()
    latexStr = cleaned_latex(latexStr)


    if ('cid:' not in latexStr):

        # Sometimes there are multiple equations within each block. Get those
        # here
        latexArray = latexStr.split(', \\\\')
        for latexItem in latexArray:
            counter = len(LATEXMAP)
            thisMapKey =  generate_random_tag()
            # in this case, 'key' is the latex code
            LATEXMAP[thisMapKey.replace(' ','')] = latexItem

        return (thisMapKey)
