""" Text based demo of parse tree generation for convex optimization expressions. """
from dcp_parser.parser import Parser

def main():
    welcome()
    parser = Parser()
    parse_file(parser)
    explore_parse_trees(parser)

def welcome():
    print "This is a demo of parse tree navigation."

def get_filename():
    return raw_input('Name of the convex optimization script file: ')

def parse_file(parser):
    while True:
        try:
            filename = get_filename()
            f = open(filename, 'r')
            break
        except Exception, e:
            print "Invalid filename"
    for line in f.readlines():
        try:
          parser.parse(line)
        except Exception, e:
          print "Error parsing " + line

def select_expression(expressions):
    for i in range(len(expressions)):
        print "Expression %i: %s" % (i, str(expressions[i]))

    index = int(raw_input('Select an expression by index: '))
    return expressions[index]

def explore_parse_trees(parser):
    exp = select_expression(parser.expressions)
    while True:
        display_root(exp)
        exp = select_child(exp)

def display_root(exp):
    print
    print "Current expression: %s" % exp
    print "Curvature: %s, Sign: %s" % (exp.curvature, exp.sign)
    for error in exp.errors:
        if error.is_indexed():
            print "Argument %i:" % error.index
        print str(error)

def select_child(exp):
    num_children = len(exp.subexpressions)
    if num_children > 0:
      print "Child expressions:"
      for i in range(num_children):
          child = exp.subexpressions[i]
          print "Expression %i: %s" % (i, child)
    index = int(raw_input('Select a child expression by index (-1 for parent): '))
    if index == -1:
        if exp.parent is None:
            return exp
        else:
            return exp.parent
    elif num_children == 0:
        return exp
    else:
        return exp.subexpressions[index]

if __name__ == "__main__":
    main()