# Automatically generated by pb2py
import protobuf as p
if __debug__:
    try:
        from typing import List
    except ImportError:
        List = None


class MoneroTsxInitResp(p.MessageType):
    MESSAGE_WIRE_TYPE = 302
    FIELDS = {
        1: ('version', p.UVarintType, 0),
        2: ('status', p.UVarintType, 0),
        3: ('in_memory', p.BoolType, 0),
        4: ('hmacs', p.BytesType, p.FLAG_REPEATED),
    }

    def __init__(
        self,
        version: int = None,
        status: int = None,
        in_memory: bool = None,
        hmacs: List[bytes] = None
    ) -> None:
        self.version = version
        self.status = status
        self.in_memory = in_memory
        self.hmacs = hmacs if hmacs is not None else []