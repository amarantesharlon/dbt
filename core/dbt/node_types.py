
class NodeType(object):
    Base = 'base'
    Model = 'model'
    Analysis = 'analysis'
    Test = 'test'
    Archive = 'archive'
    Macro = 'macro'
    Operation = 'operation'
    Seed = 'seed'
    Documentation = 'documentation'
    Source = 'source'
    RPCCall = 'rpc'

    @classmethod
    def executable(cls):
        return [
            cls.Model,
            cls.Test,
            cls.Archive,
            cls.Analysis,
            cls.Operation,
            cls.Seed,
            cls.Documentation,
            cls.RPCCall,
        ]

    @classmethod
    def refable(cls):
        return [
            cls.Model,
            cls.Seed,
            cls.Archive,
        ]


class RunHookType:
    Start = 'on-run-start'
    End = 'on-run-end'
    Both = [Start, End]
