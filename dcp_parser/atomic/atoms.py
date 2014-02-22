""" Definitions of atomic functions """
import abc
import exceptions
import copy
from types import MethodType
from numbers import Number
import dcp_parser.expression.settings as settings
from dcp_parser.expression.sign import Sign
from dcp_parser.expression.curvature import Curvature
from dcp_parser.atomic.monotonicity import Monotonicity
from dcp_parser.expression.expression import Expression, Constant

class Atom(object):
    """ Abstract base class for all atoms. """
    __metaclass__ = abc.ABCMeta

    # Name for expressions generated by arguments.
    GENERATED_EXPRESSION = "atom"

    # Sign of argument to monoticity in that argument.
    # For all functions akin to |x|
    ABS_SIGN_TO_MONOTONICITY = {
                            str(Sign.POSITIVE): Monotonicity.INCREASING,
                            str(Sign.ZERO): Monotonicity.INCREASING,
                            str(Sign.NEGATIVE): Monotonicity.DECREASING,
                            str(Sign.UNKNOWN): Monotonicity.NONMONOTONIC
                            }

    # args are the expressions passed into the Atom constructor.
    def __init__(self, *args):
        # Throws error if args is empty.
        if len(args) == 0:
            raise TypeError("No arguments given to '%s'." % self.name())
        # Convert numeric constants to Constants
        self.args = map(Expression.type_check, list(args))
        # Arguments passed into the Atom. Defaults to self.args,
        # but if the Atom is defined in terms of another Atom
        # self.args could be different.
        self.original_args = self.args

    # Returns the Atom's name as a function.
    def name(self):
        return self.__class__.__name__.lower()

    # Returns the atomic expression's string representation
    # with subexpressions removed.
    # For non-parameterized Atoms this will be the same as the function name.
    # For parameterized Atoms this will be name(..., parameter).
    def short_name(self):
        if Parameterized in self.__class__.__bases__:
            return "%s(..., %s)" % (self.name(), self.parameter)
        else:
            return self.name()

    # Returns expression arguments passed into the Atom.
    def arguments(self):
        return self.original_args

    # Stores the original args in case they differ from self.args.
    def save_original_args(self, original_args):
        self.original_args = map(Expression.type_check, original_args)

    # Determines sign from args.
    @abc.abstractmethod
    def sign(self):
        return NotImplemented

    # Determines curvature from args and sign.
    def curvature(self):
        curvature = self.signed_curvature()
        return Atom.dcp_curvature(curvature, self.args, self.monotonicity())

    # Returns argument curvatures as a list.
    def argument_curvatures(self):
        return [arg.curvature for arg in self.args]

    # Returns argument signs as a list.
    def argument_signs(self):
        return [arg.sign for arg in self.args]

    # Converts an Atom into an expression with the same curvature and sign.
    # Used for defining atoms as compositions of atoms.
    @staticmethod
    def atom_to_expression(instance):
        return Expression(instance.curvature(),
                          instance.sign(),
                          Atom.GENERATED_EXPRESSION,
                          instance.arguments())

    # Converts a Constant or -Constant to its numeric value.
    # Returns given argument if cannot be converted.
    # http://stackoverflow.com/questions/379906/parse-string-to-float-or-int
    @staticmethod
    def constant_to_number(constant):
        if isinstance(constant, Constant) or \
          (isinstance(constant, Expression) and \
           len(constant.subexpressions) == 1 and \
           constant.name ==  settings.MINUS + constant.subexpressions[0].name):
            try:
                return int(constant.name)
            except exceptions.ValueError:
                return float(constant.name)
        else:
            return constant

    # Determines curvature from sign, e.g. x^3 is convex for positive x
    # and concave for negative x.
    # Usually result will not depend on sign.
    @abc.abstractmethod
    def signed_curvature(self):
        return NotImplemented

    # Returns a list with the monotonicity in each argument.
    # Monotonicity can depend on the sign of the argument.
    @abc.abstractmethod
    def monotonicity(self):
        return NotImplemented

    """
    Applies DCP composition rules to determine curvature in each argument.
    The overall curvature is the sum of the argument curvatures.
    """
    @staticmethod
    def dcp_curvature(curvature, args, monotonicities):
        if len(args) != len(monotonicities):
            raise Exception('The number of args be'
                            ' equal to the number of monotonicities.')
        arg_curvatures = [monotonicity.dcp_curvature(curvature,arg.curvature)
                          for arg,monotonicity in zip(args,monotonicities)]
        return Curvature.sum(arg_curvatures)

class Parameterized(object):
    """
    Abstract base class for all parameterized atoms.
    All parameterized atoms must inherit from some subclass of Atom and Parameterized.
    """
    __metaclass__ = abc.ABCMeta

    # Saves the last argument as self.parameter.
    # If the argument has a default (i.e. default is not None),
    # sets the parameter to the default if the last arg is not a constant or
    # string argument.
    # If the Atom is not vararg, call set_parameter with only the parameter.
    # Ends by validating parameter.
    # Returns the arguments without the parameter.
    def set_parameter(self, default, *args):
        self.parameter = default
        if len(args) > 0:
            last_arg = Atom.constant_to_number(args[len(args)-1])
            if not isinstance(last_arg, Expression):
                self.parameter = last_arg
                args = args[:-1]
        # Throws error if parameter is invalid.
        self.validate_parameter()
        return args

    # Throws an error if the parameter is invalid.
    @abc.abstractmethod
    def validate_parameter(self):
        return NotImplemented


"""---------------------------------- Atoms ----------------------------------"""
class Log_sum_exp(Atom):
    """ log(e^(arg[0]) + e^(arg[1]) + ... + e^(arg[n])) """
    # Always unknown
    def sign(self):
        return Sign.UNKNOWN

    # Always convex
    def signed_curvature(self):
        return Curvature.CONVEX

    # Always increasing.
    def monotonicity(self):
        return [Monotonicity.INCREASING] * len(self.args)

class Max(Atom):
    """ Maximum argument. """
    """
    Reduces the list of argument signs according to the following rules:
        POSITIVE, ANYTHING = POSITIVE
        ZERO, UNKNOWN = POSITIVE
        ZERO, ZERO = ZERO
        ZERO, NEGATIVE = ZERO
        UNKNOWN, NEGATIVE = UNKNOWN
        NEGATIVE, NEGATIVE = NEGATIVE
    """
    def sign(self):
        arg_signs = self.argument_signs()
        sign = max(arg_signs)
        if sign == Sign.UNKNOWN and Sign.ZERO in arg_signs:
            return Sign.POSITIVE
        return sign

    # Always convex
    def signed_curvature(self):
        return Curvature.CONVEX

    # Always increasing.
    def monotonicity(self):
        return [Monotonicity.INCREASING] * len(self.args)

class Min(Atom):
    """ Minimum argument. """
    """
    Reduces the list of argument signs according to the following rules:
        NEGATIVE, ANYTHING = NEGATIVE
        ZERO, UNKNOWN = NEGATIVE
        ZERO, ZERO = ZERO
        ZERO, POSITIVE = ZERO
        UNKNOWN, POSITIVE = UNKNOWN
        POSITIVE, POSITIVE = POSITIVE
    """
    def sign(self):
        arg_signs = self.argument_signs()
        sign = min(arg_signs)
        if sign == Sign.ZERO and Sign.UNKNOWN in arg_signs:
            return Sign.NEGATIVE
        return sign

    # Always convex
    def signed_curvature(self):
        return Curvature.CONCAVE

    # Always increasing.
    def monotonicity(self):
        return [Monotonicity.INCREASING] * len(self.args)

class Log(Atom):
    """
    Natural logarithm
    log(x) for x > 0.
    -Inf for x <= 0.
    """
    def __init__(self, arg):
        super(Log, self).__init__(arg)

    # Always unknown.
    def sign(self):
        return Sign.UNKNOWN

    # Concave unless domain error,
    # i.e., an argument is negative or zero.
    def signed_curvature(self):
        if self.args[0].sign in [Sign.NEGATIVE, Sign.ZERO]:
            return Curvature.NONCONVEX
        else:
            return Curvature.CONCAVE

    # Always increasing.
    def monotonicity(self):
        return [Monotonicity.INCREASING]

class Sum(Atom):
    """ Sum of all arguments. """
    # Sum of argument signs.
    def sign(self):
        signs = [arg.sign for arg in self.args]
        return Sign.sum(*signs)

    # Always affine
    def signed_curvature(self):
        return Curvature.AFFINE

    # Always increasing.
    def monotonicity(self):
        return [Monotonicity.INCREASING] * len(self.args)

class Geo_mean(Atom):
    """
    (x1*...*xn)^(1/n) if all xi >= 0.
    Domain error if any xi < 0.
    """
    def __init__(self, *args):
        super(Geo_mean, self).__init__(*args)

    # Unknown if any argument negative,
    # otherwise positive.
    def sign(self):
        if Sign.NEGATIVE in self.argument_signs():
            return Sign.UNKNOWN
        else:
            for sign in self.argument_signs():
                if sign != Sign.ZERO:
                    return Sign.POSITIVE
            return Sign.ZERO

    # Concave unless domain error,
    # i.e., an argument is negative
    def signed_curvature(self):
        if Sign.NEGATIVE in self.argument_signs():
            return Curvature.NONCONVEX
        else:
            return Curvature.CONCAVE

    # Always increasing.
    def monotonicity(self):
        return [Monotonicity.INCREASING] * len(self.args)

class Sqrt(Geo_mean):
    """ square root of a single argument """
    def __init__(self, x):
        super(Sqrt, self).__init__(x)

class Log_normcdf(Atom):
    """
    logarithm of cumulative distribution function of
    standard normal random variable
    """
    def __init__(self, x):
        super(Log_normcdf, self).__init__(x)

    # Always unknown
    def sign(self):
        return Sign.UNKNOWN

    # Always concave
    def signed_curvature(self):
        return Curvature.CONCAVE

    # Always increasing.
    def monotonicity(self):
        return [Monotonicity.INCREASING]

class Exp(Atom):
    """ e^x """
    def __init__(self, x):
        super(Exp,self).__init__(x)

    # Always positive
    def sign(self):
        return Sign.POSITIVE

    # Always convex
    def signed_curvature(self):
        return Curvature.CONVEX

    # Always increasing.
    def monotonicity(self):
        return [Monotonicity.INCREASING]

class Norm(Atom, Parameterized):
    """
    The p-norm for a vector (list of scalar values)
    Use:  Norm(*args, p)
    p can be either a number greater than or equal to 1 or 'Inf'
    p defaults to 2.
    """
    def __init__(self, *args):
        # Set parameter to last arg if last arg is not a non-Constant Expression
        # Otherwise default to parameter = 2
        args = self.set_parameter(2, *args)
        super(Norm,self).__init__(*args)

    # Throws error if parameter is invalid.
    def validate_parameter(self):
        if not ( (isinstance(self.parameter, Number) and self.parameter >= 1) or
            self.parameter == 'Inf'):
            raise Exception(
                "Invalid value '%s' for p in norm(..., p)." % self.parameter
                )

    # Positive unless all arguments are zero.
    def sign(self):
        for sign in self.argument_signs():
            if sign != Sign.ZERO:
                return Sign.POSITIVE
        return Sign.ZERO

    # Always convex
    def signed_curvature(self):
        return Curvature.CONVEX

    # Increasing (decreasing) for positive (negative) argument.
    def monotonicity(self):
        monotonicities = []
        for scalar in self.args:
            sign_str = str(scalar.sign)
            monotonicity = Norm.ABS_SIGN_TO_MONOTONICITY[sign_str]
            monotonicities.append(monotonicity)
        return monotonicities

class Norm2(Norm):
    """
    The L2-norm for a vector (list of scalar values)
    Use:  Norm2(*args)
    """
    def __init__(self, *args):
        args = [arg for arg in args] + [2]
        super(Norm2, self).__init__(*args)

class Norm1(Norm):
    """
    The L1-norm for a vector (list of scalar values)
    Use:  Norm1(*args)
    """
    def __init__(self, *args):
        args = [arg for arg in args] + [1]
        super(Norm1, self).__init__(*args)

class Norm_inf(Norm):
    """
    The LInfinity-norm for a vector (list of scalar values)
    Use:  Norm_inf(*args)
    """
    def __init__(self, *args):
        args = [arg for arg in args] + ["Inf"]
        super(Norm_inf, self).__init__(*args)

class Abs(Norm):
    """ Absolute value of one scalar argument. """
    def __init__(self, x):
        super(Abs,self).__init__(x,1)

class Entr(Atom):
    """ The entropy function -x*log(x)
    Domain x >= 0.
    """
    def __init__(self, x):
        super(Entr,self).__init__(x)

    # Zero if x is 0, otherwise unknown.
    def sign(self):
        if Sign.ZERO in self.argument_signs():
            return Sign.ZERO
        else:
            return Sign.UNKNOWN

    # Concave unless domain error,
    # i.e., an argument is negative
    def signed_curvature(self):
        if Sign.NEGATIVE in self.argument_signs():
            return Curvature.NONCONVEX
        else:
            return Curvature.CONCAVE

    # Always non-monotonic
    def monotonicity(self):
        return [Monotonicity.NONMONOTONIC]


class Huber(Atom, Parameterized):
    """
    The Huber function
    Huber(x,M) = 2M|x|-M^2 for |x| >= M
                 |x|^2 for |x| <= M
    M defaults to 1. M must be positive.
    """
    def __init__(self, x, M=1):
        self.set_parameter(Atom.constant_to_number(M))
        super(Huber,self).__init__(x)

    # Throws error if parameter is invalid.
    def validate_parameter(self):
        if not (isinstance(self.parameter, Number) and self.parameter > 0):
            raise Exception(
                "Invalid value '%s' for M in %s(...,M)." % (self.parameter, self.name())
                )

        # Zero if x is 0, otherwise positive.
    def sign(self):
        if Sign.ZERO in self.argument_signs():
            return Sign.ZERO
        else:
            return Sign.POSITIVE

    # Always convex
    def signed_curvature(self):
        return Curvature.CONVEX

    # Increasing (decreasing) for positive (negative) argument.
    def monotonicity(self):
        arg_sign_str = str(self.args[0].sign)
        monotonicity = Berhu.ABS_SIGN_TO_MONOTONICITY[arg_sign_str]
        return [monotonicity]

class Berhu(Huber, Parameterized):
    """
    The reversed Huber function
    Berhu(x,M) = |x| for |x| <= M
                 (|x|^2 + M^2)/2M for |x| >= M
    M defaults to 1. M must be positive.
    """

class Huber_pos(Huber, Parameterized):
    """ Same as Huber for non-negative x, zero for negative x. """
    # Positive unless x negative or zero, in which case zero.
    def sign(self):
        if self.args[0].sign <= Sign.ZERO:
            return Sign.ZERO
        else:
            return Sign.POSITIVE

    # Convex unless zero, in which case constant.
    def signed_curvature(self):
        if self.sign() <= Sign.ZERO:
            return Curvature.CONSTANT
        else:
            return Curvature.CONVEX

    # Always increasing.
    def monotonicity(self):
        return [Monotonicity.INCREASING]

class Huber_circ(Huber_pos, Parameterized):
    """
    Circularly symmetric Huber function
    Huber_circ(vector, M) is equivalent to huber_pos(norm(x),M)
    Default M is 1.
    """
    def __init__(self, *args):
        args = list(args)
        # Default to M=1 if last argument is not a number.
        args = self.set_parameter(1, *args)
        # Use Norm
        tmp_args = copy.copy(list(args))
        tmp_args.append(2)
        norm = Atom.atom_to_expression(Norm(*tmp_args))
        super(Huber_circ, self).__init__(norm,self.parameter)
        self.save_original_args(args)

class Inv_pos(Atom):
    """
    1/x, domain x > 0.
    """
    def __init__(self, x):
        super(Inv_pos, self).__init__(x)

    # Positive unless domain error,
    # i.e., an argument is negative.
    def sign(self):
        if self.args[0].sign in [Sign.NEGATIVE, Sign.ZERO]:
            return Sign.UNKNOWN
        else:
            return Sign.POSITIVE

    # Convex unless domain error,
    # i.e., an argument is negative
    def signed_curvature(self):
        if self.args[0].sign in [Sign.NEGATIVE, Sign.ZERO]:
            return Curvature.NONCONVEX
        else:
            return Curvature.CONVEX

    # Always decreasing.
    def monotonicity(self):
        return [Monotonicity.DECREASING]

class Kl_div(Atom):
    """
    Kullback-Leibler distance
    kl_div(x,y) = x*log(x/y)-x+y
    Domain error unless x,y non-negative.
    """
    def __init__(self, x,y):
        super(Kl_div, self).__init__(x,y)

    # Always positive
    def sign(self):
        return Sign.POSITIVE

    # Convex unless domain error,
    # i.e., an argument is negative or zero.
    def signed_curvature(self):
        if Sign.NEGATIVE in self.argument_signs() or \
           Sign.ZERO in self.argument_signs():
            return Curvature.NONCONVEX
        else:
            return Curvature.CONVEX

    # Always non-monotonic.
    def monotonicity(self):
        return [Monotonicity.NONMONOTONIC] * len(self.args)

class Norm_largest(Atom, Parameterized):
    """
    Sum of the k largest magnitudes (i.e. absolute values) in the given arguments.
    norm_largest(vector, k)
    """
    def __init__(self, *args):
        # Use last argument as k
        args = self.set_parameter(None, *args)
        super(Norm_largest, self).__init__(*args)

    # Raises error if the parameter is not a number.
    def validate_parameter(self):
        if not isinstance(self.parameter,Number):
            raise Exception(
                "Invalid value '%s' for k in norm_largest(...,k)." % self.parameter
                )

    # Always positive
    def sign(self):
        return Sign.POSITIVE

    # Always convex
    def signed_curvature(self):
        return Curvature.CONVEX

    # Increasing (decreasing) for positive (negative) argument.
    def monotonicity(self):
        monotonicities = []
        for scalar in self.args:
            sign_str = str(scalar.sign)
            monotonicity = Norm_largest.ABS_SIGN_TO_MONOTONICITY[sign_str]
            monotonicities.append(monotonicity)
        return monotonicities

class Pos(Max):
    """ max{x,0} """
    def __init__(self, x):
        super(Pos, self).__init__(x, 0)
        self.save_original_args([x])

class Pow(Atom, Parameterized):
    """
    pow(x,p) =
        If p <= 0 then x^p with domain x > 0.
        If 0 < p <=1 then x^p with domain x >= 0/
        If p > 1 then x^p with domain x >= 0.
    """
    def __init__(self,x,p):
        self.set_parameter(Atom.constant_to_number(p))
        super(Pow, self).__init__(x)
        self.p = self.parameter
        self.x = self.args[0]

    # Raises error if the parameter is not a number.
    def validate_parameter(self):
        if not isinstance(self.parameter, Number):
            raise Exception(
                "Invalid value '%s' for p in pow(..., p)." % self.parameter
                )

    # Depends on p and the sign of x.
    # Unknown if x out of domain.
    def sign(self):
        # Check for domain error.
        if self.x.sign == Sign.NEGATIVE or \
           (self.p <= 0 and self.x.sign == Sign.ZERO):
            return Sign.UNKNOWN
        else:
            if self.x.sign == Sign.ZERO:
                return Sign.ZERO
            else:
                return Sign.POSITIVE

    # Depends on p.
    # Non-convex if x out of domain.
    def signed_curvature(self):
        # Check for domain error.
        if self.x.sign == Sign.NEGATIVE or \
           (self.p <= 0 and self.x.sign == Sign.ZERO):
            return Curvature.NONCONVEX

        if self.p <= 0:
            return Curvature.CONVEX
        elif self.p <= 1:
            return Curvature.CONCAVE
        else: # p > 1
            return Curvature.CONVEX

    # Depends on p and the sign of x.
    def monotonicity(self):
        if self.p <= 0:
            return [Monotonicity.DECREASING]
        elif self.p <= 1:
            return [Monotonicity.INCREASING]
        else: # p > 1
            return [Pow.ABS_SIGN_TO_MONOTONICITY[str(self.x.sign)]]

class Pow_abs(Pow, Parameterized):
    """ |x|^p """
    def __init__(self,x,p):
        # Must have p >= 1
        abs_exp = Atom.atom_to_expression(Abs(x))
        super(Pow_abs, self).__init__(abs_exp,p)
        self.save_original_args([x])

    # Raises error if the parameter is not a number >= 1.
    def validate_parameter(self):
        if not (isinstance(self.parameter, Number) and self.parameter >= 1):
            raise Exception('Must have p >= 1 for pow_abs(..., p), but have p = %s.' % self.parameter)

class Pow_pos(Pow, Parameterized):
    """ max{x,0}^p """
    def __init__(self,x,p):
        # Must have p >= 1
        pos_exp = Atom.atom_to_expression(Pos(x))
        super(Pow_pos, self).__init__(pos_exp,p)
        self.save_original_args([x])


    # Raises error if the parameter is not a number >= 1.
    def validate_parameter(self):
        if not (isinstance(self.parameter, Number) and self.parameter >= 1):
            raise Exception('Must have p >= 1 for pow_pos(..., p), but have p = %s.' % self.parameter)


class Square_abs(Pow_abs):
    """ |x|^2 """
    def __init__(self,x):
        super(Square_abs, self).__init__(x,2)

class Square_pos(Pow_pos):
    """ max{x,0}^2 """
    def __init__(self,x):
        super(Square_pos, self).__init__(x,2)

class Rel_entr(Atom):
    """ rel_entr(x,y) = x*log(x/y) """
    def __init__(self,x,y):
        super(Rel_entr,self).__init__(x,y)

    # Always unknown
    def sign(self):
        return Sign.UNKNOWN

    # Always convex
    def signed_curvature(self):
        return Curvature.CONVEX

    # Always non-monotonic
    def monotonicity(self):
        return [Monotonicity.NONMONOTONIC] * len(self.args)

class Quad_over_lin(Atom):
    """
    quad_over_lin(x,y) = x^2/y
    Domain y > 0.
    Last argument is the divisor. All preceding arguments are treated as part of the vector x.
    """
    def __init__(self, x, y):
        super(Quad_over_lin,self).__init__(x,y)
        self.x = self.args[0]
        self.y = self.args[1]

    # Positive unless domain error,
    # i.e., y is negative or zero.
    def sign(self):
        if self.y.sign in [Sign.NEGATIVE, Sign.ZERO]:
            return Sign.UNKNOWN
        else:
            return Sign.POSITIVE

    # Convex unless domain error,
    # i.e., y is negative or zero.
    def signed_curvature(self):
        if self.y.sign in [Sign.NEGATIVE, Sign.ZERO]:
            return Curvature.NONCONVEX
        else:
            return Curvature.CONVEX

    # Increasing (decreasing) for positive (negative) argument in vector args.
    # Decreasing for divisor arguments
    def monotonicity(self):
        # Numerator
        sign_str = str(self.x.sign)
        monotonicity = Norm.ABS_SIGN_TO_MONOTONICITY[sign_str]
        monotonicities = [monotonicity]
        # Denominator
        monotonicities.append(Monotonicity.DECREASING)
        return monotonicities

class Square(Quad_over_lin):
    """ Squares a single argument. """
    def __init__(self, x):
        super(Square,self).__init__(x,1)
        self.save_original_args([x])

class Sum_square(Quad_over_lin):
    """ x1^2 + ... + xn^2 = quad_over_lin(norm(x1,...,xn),1) """
    def __init__(self, *x):
        args = list(x)
        args.append(2)
        norm_exp = Atom.atom_to_expression(Norm(*args))
        super(Sum_square,self).__init__(norm_exp, 1)
        self.save_original_args(list(x))

class Sum_square_abs(Sum_square):
    """ |x1|^2 + ... + |xn|^2 = sum_square(abs(x1),...,abs(xn)) """
    def __init__(self, *x):
        exp_vec = []
        for scalar in x:
            abs_exp = Atom.atom_to_expression(Abs(scalar))
            exp_vec.append(abs_exp)
        super(Sum_square_abs,self).__init__(*exp_vec)
        self.save_original_args(list(x))

class Sum_square_pos(Sum_square):
    """ max{x1,0}^2 + ... + max{xn,0}^2 = sum_square(pos(x1),..., pos(xn)) """
    def __init__(self, *x):
        exp_vec = []
        for scalar in x:
            pos_exp = Atom.atom_to_expression(Pos(scalar))
            exp_vec.append(pos_exp)
        super(Sum_square_pos,self).__init__(*exp_vec)
        self.save_original_args(list(x))

class Sum_largest(Atom, Parameterized):
    """ Sum of the largest k values given. """
    def __init__(self, *args):
        # Use last argument as k
        args = self.set_parameter(None, *args)
        super(Sum_largest, self).__init__(*args)

    # Raises error if the parameter is not a number.
    def validate_parameter(self):
        if not isinstance(self.parameter,Number):
            raise Exception(
                "Invalid value '%s' for k in %s(...,k)." % (self.parameter, self.name())
                )

    # Always unknown
    # Could determine from signs of elements, but would be obscure.
    def sign(self):
        return Sign.UNKNOWN

    # Always convex
    def signed_curvature(self):
        return Curvature.CONVEX

    # Always increasing.
    def monotonicity(self):
        return [Monotonicity.INCREASING] * len(self.args)

class Sum_smallest(Sum_largest, Parameterized):
    """ Sum of the smallest k values given. """
    # Always concave
    def signed_curvature(self):
        return Curvature.CONCAVE

    # Always increasing
    def monotonicity(self):
        return [Monotonicity.INCREASING] * len(self.args)