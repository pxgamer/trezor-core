# Automatically generated by pb2py
# fmt: off
import protobuf as p

from .NEMMosaicDefinition import NEMMosaicDefinition


class NEMMosaicCreation(p.MessageType):
    FIELDS = {
        1: ('definition', NEMMosaicDefinition, 0),
        2: ('sink', p.UnicodeType, 0),
        3: ('fee', p.UVarintType, 0),
    }

    def __init__(
        self,
        definition: NEMMosaicDefinition = None,
        sink: str = None,
        fee: int = None,
    ) -> None:
        self.definition = definition
        self.sink = sink
        self.fee = fee
