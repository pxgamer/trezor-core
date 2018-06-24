#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Dusan Klinec, ph4r05, 2018


import ubinascii as binascii

from apps.monero import trezor_iface, trezor_misc
from apps.monero.xmr.serialize import xmrtypes, xmrserialize
from apps.monero.xmr.monero import TsxData, classify_subaddresses
from apps.monero.xmr import monero, mlsag2, ring_ct, crypto, common, key_image, trezor
from apps.monero.xmr.enc import chacha_poly
from apps.monero.xmr import trezor as twrap

from apps.monero import layout
from apps.monero.messages import MoneroKeyImageSync, MoneroExportedKeyImage, \
    MoneroKeyImageExportInit, MoneroKeyImageExportInitResp, \
    MoneroKeyImageSyncStep, MoneroKeyImageSyncStepResp, \
    MoneroKeyImageSyncFinal, MoneroKeyImageSyncFinalResp, \
    MoneroRespError


class KeyImageSync(object):
    def __init__(self, ctx=None, iface=None, creds=None):
        self.ctx = ctx
        self.iface = iface  # type: trezor_iface.TrezorInterface
        self.creds = creds  # type: monero.AccountCreds

        self.num = 0
        self.c_idx = -1
        self.hash = None
        self.blocked = None
        self.enc_key = None
        self.subaddresses = {}
        self.hasher = common.HashWrapper(crypto.get_keccak())

    async def derive_creds(self, msg: MoneroKeyImageExportInit):
        self.creds = await twrap.monero_get_creds(self.ctx, msg.address_n or (), msg.network_type)

    async def init(self, ctx, msg: MoneroKeyImageExportInit):
        self.ctx = ctx
        await self.derive_creds(msg)

        confirmation = await self.iface.confirm_ki_sync(msg, ctx=ctx)
        if not confirmation:
            return MoneroRespError(reason='rejected')

        self.num = msg.num
        self.hash = msg.hash
        self.enc_key = crypto.random_bytes(32)

        # Sub address precomputation
        if msg.subs and len(msg.subs) > 0:
            for sub in msg.subs:  # type: MoneroSubAddrIndicesList
                monero.compute_subaddresses(self.creds, sub.account, sub.minor_indices, self.subaddresses)
        return MoneroKeyImageExportInitResp()

    async def sync(self, ctx, tds: MoneroKeyImageSyncStep):
        self.ctx = ctx
        if self.blocked:
            raise ValueError('Blocked')
        if len(tds.tdis) == 0:
            raise ValueError('Empty')
        resp = []
        for td in tds.tdis:
            self.c_idx += 1
            if self.c_idx >= self.num:
                raise ValueError('Too many outputs')

            hash = key_image.compute_hash(td)
            self.hasher.update(hash)

            ki, sig = await key_image.export_key_image(self.creds, self.subaddresses, td)

            buff = crypto.encodepoint(ki)
            buff += crypto.encodeint(sig[0][0])
            buff += crypto.encodeint(sig[0][1])

            nonce, ciph, tag = chacha_poly.encrypt(self.enc_key, buff)
            eki = MoneroExportedKeyImage(iv=nonce, tag=tag, blob=ciph)
            resp.append(eki)
        return MoneroKeyImageSyncStepResp(kis=resp)

    async def final(self, ctx, msg=None):
        self.ctx = ctx
        if self.blocked:
            raise ValueError('Blocked')

        if self.c_idx + 1 != self.num:
            await self.iface.ki_error('Invalid number of outputs', ctx=self.ctx)
            raise ValueError('Invalid number of outputs')

        final_hash = self.hasher.digest()
        if final_hash != self.hash:
            await self.iface.ki_error('Invalid hash', ctx=self.ctx)
            raise ValueError('Invalid hash')

        return MoneroKeyImageSyncFinalResp(enc_key=self.enc_key)


SYNC_STATE = None


async def layout_key_image_sync(ctx, msg: MoneroKeyImageSync):
    global SYNC_STATE
    try:
        if msg.init:
            SYNC_STATE = KeyImageSync()
            return await SYNC_STATE.init(ctx, msg.init)

        elif msg.step:
            return await SYNC_STATE.sync(ctx, msg.step)

        elif msg.final_msg:
            res = await SYNC_STATE.final(ctx, msg.final_msg)
            SYNC_STATE = None
            return res

        else:
            raise ValueError('Unknown error')

    except Exception as e:
        SYNC_STATE = None



