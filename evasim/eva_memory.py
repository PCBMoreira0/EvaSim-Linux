class EvaMemory:
    def __init__(self):
        # Is equivalent to the $ of the original Eva software
        # Is a list of results
        self.var_dolar = []

        # "case" flag
        self.reg_case = 0

        # Eva ram (a key/value dictionary)
        self.vars = {}