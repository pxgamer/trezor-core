from apps.monero.xmr.serialize.message_types import MessageType
from apps.monero.xmr.serialize.messages.base import ECKey
from apps.monero.xmr.serialize.messages.ct_keys import KeyV


class Bulletproof(MessageType):
    __slots__ = ['V', 'A', 'S', 'T1', 'T2', 'taux', 'mu', 'L', 'R', 'a', 'b', 't']
    MFIELDS = [
        ('A', ECKey),
        ('S', ECKey),
        ('T1', ECKey),
        ('T2', ECKey),
        ('taux', ECKey),
        ('mu', ECKey),
        ('L', KeyV),
        ('R', KeyV),
        ('a', ECKey),
        ('b', ECKey),
        ('t', ECKey),
    ]