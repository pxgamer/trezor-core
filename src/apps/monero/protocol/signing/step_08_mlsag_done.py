"""
MLSAG message computed.
"""

from .state import State

from apps.monero.layout import confirms


async def mlsag_done(state: State):
    from trezor.messages.MoneroTransactionMlsagDoneAck import (
        MoneroTransactionMlsagDoneAck
    )

    # state.state.set_final_message_done()  todo needed?
    await confirms.transaction_step(state.ctx, state.STEP_MLSAG)

    _ecdh_info(state)
    _out_pk(state)
    state.full_message_hasher.rctsig_base_done()
    state.out_idx = -1
    state.inp_idx = -1

    state.full_message = state.full_message_hasher.get_digest()
    state.full_message_hasher = None

    return MoneroTransactionMlsagDoneAck(full_message_hash=state.full_message)


def _ecdh_info(state: State):  # todo why is it here? remove
    """
    Sets ecdh info for the incremental hashing mlsag.
    """
    pass


def _out_pk(state: State):
    """
    Sets out_pk for the incremental hashing mlsag.
    """
    if state.num_dests() != len(state.output_pk):
        raise ValueError("Invalid number of ecdh")

    for out in state.output_pk:
        state.full_message_hasher.set_out_pk(out)
