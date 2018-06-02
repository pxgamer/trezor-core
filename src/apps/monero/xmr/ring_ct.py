#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: https://github.com/monero-project/mininero
# Author: Dusan Klinec, ph4r05, 2018


from apps.monero.xmr.serialize import xmrtypes
from apps.monero.xmr import mlsag2, crypto, common, monero

ATOMS = 64

    
def d2b(n, digits):
    b = [0] * digits
    i = 0
    while n:
        b[i] = n & 1
        i = i + 1
        n >>= 1
    return b 


def sum_Ci(Cis):
    """
    Sums points
    :param Cis:
    :return:
    """
    CSum = crypto.identity()
    for i in Cis:
        CSum = crypto.point_add(CSum, i)
    return CSum


def prove_range(amount, last_mask=None, decode=False):
    """
    Range proof generator.
    In order to minimize the memory consumption and CPU usage during transaction generation the returned values
    are returned encoded.

    :param amount:
    :param last_mask:
    :param use_asnl: ASNL range proof, insecure
    :param mem_opt: memory optimized
    :param backend_impl: backend implementation, if available
    :param decode: decodes output
    :return:
    """
    C, a, R = crypto.prove_range(amount, last_mask)[:3]  # backend returns encoded
    if decode:
        R = monero.recode_rangesig(R, encode=False)
        return C, a, R
    return C, a, R


def ver_range(C=None, rsig=None, decode=True):
    """
    Verifies that \sum Ci = C and that each Ci is a commitment to 0 or 2^i
    :param C:
    :param rsig:
    :param decode: decodes encoded range proof
    :return:
    """
    n = ATOMS
    CiH = [None] * n
    C_tmp = crypto.identity()
    c_H = crypto.gen_H()

    if decode:
        rsig = monero.recode_rangesig(rsig, encode=False, copy=True)

    for i in range(0, n):
        CiH[i] = crypto.point_sub(rsig.Ci[i], c_H)
        C_tmp = crypto.point_add(C_tmp, rsig.Ci[i])
        c_H = crypto.point_double(c_H)

    if C is not None and not crypto.point_eq(C_tmp, C):
        return 0

    return mlsag2.ver_borromean(rsig.Ci, CiH, rsig.asig.s0, rsig.asig.s1, rsig.asig.ee)


# Ring-ct MG sigs
# Prove:
#   c.f. http:#eprint.iacr.org/2015/1098 section 4. definition 10. 
#   This does the MG sig on the "dest" part of the given key matrix, and 
#   the last row is the sum of input commitments from that column - sum output commitments
#   this shows that sum inputs = sum outputs
# Ver:
#   verifies the above sig is created corretly


def ecdh_encode(unmasked, receiver_pk=None, derivation=None):
    """
    Elliptic Curve Diffie-Helman: encodes and decodes the amount b and mask a
    where C= aG + bH
    :param unmasked:
    :param receiver_pk:
    :param derivation:
    :return:
    """
    rv = xmrtypes.EcdhTuple()
    if derivation is None:
        esk = crypto.random_scalar()
        rv.senderPk = crypto.scalarmult_base(esk)
        derivation = crypto.encodepoint(crypto.scalarmult(receiver_pk, esk))

    sharedSec1 = crypto.hash_to_scalar(derivation)
    sharedSec2 = crypto.hash_to_scalar(crypto.encodeint(sharedSec1))

    rv.mask = crypto.sc_add(unmasked.mask, sharedSec1)
    rv.amount = crypto.sc_add(unmasked.amount, sharedSec2)
    return rv

    
def ecdh_decode(masked, receiver_sk=None, derivation=None):
    """
    Elliptic Curve Diffie-Helman: encodes and decodes the amount b and mask a
    where C= aG + bH
    :param masked:
    :param receiver_sk:
    :param derivation:
    :return:
    """
    rv = xmrtypes.EcdhTuple()

    if derivation is None:
        derivation = crypto.scalarmult(masked.senderPk, receiver_sk)

    sharedSec1 = crypto.hash_to_scalar(derivation)
    sharedSec2 = crypto.hash_to_scalar(crypto.encodeint(sharedSec1))

    rv.mask = crypto.sc_sub(masked.mask, sharedSec1)
    rv.amount = crypto.sc_sub(masked.amount, sharedSec2)
    return rv


#
# RingCT protocol
#


def decode_rct(rv, sk, i):
    """
    c.f. http:#eprint.iacr.org/2015/1098 section 5.1.1
    Uses the attached ecdh info to find the amounts represented by each output commitment
    must know the destination private key to find the correct amount, else will return a random number

    :param rv:
    :param sk:
    :param i:
    :return:
    """
    decodedTuple = ecdh_decode(rv.ecdhInfo[i], sk)
    mask = decodedTuple.mask
    amount = decodedTuple.amount
    C = rv.outPk[i].mask
    H = crypto.gen_H()
    Ctmp = crypto.point_add(crypto.scalarmult_base(mask), crypto.scalarmult(H, amount))
    if not crypto.point_eq(crypto.point_sub(C, Ctmp), crypto.identity()):
        raise ValueError("warning, amount decoded incorrectly, will be unable to spend")
    return amount


#
# Key image import / export
#


def generate_ring_signature(prefix_hash, image, pubs, sec, sec_idx, test=False):
    """
    Generates ring signature with key image.
    void crypto_ops::generate_ring_signature()
    TODO: test

    :param prefix_hash:
    :param image:
    :param pubs:
    :param sec:
    :param sec_idx:
    :param test:
    :return:
    """
    if test:
        t = crypto.scalarmult_base(sec)
        if not crypto.point_eq(t, pubs[sec_idx]):
            raise ValueError('Invalid sec key')

        k_i = monero.generate_key_image(crypto.encodepoint(pubs[sec_idx]), sec)
        if not crypto.point_eq(k_i, image):
            raise ValueError('Key image invalid')
        for k in pubs:
            crypto.ge_frombytes_vartime_check(k)

    image_unp = crypto.ge_frombytes_vartime(image)
    image_pre = crypto.ge_dsm_precomp(image_unp)

    buff = b'' + prefix_hash
    sum = crypto.sc_0()
    k = crypto.sc_0()
    sig = []
    for i in range(len(pubs)):
        sig.append([crypto.sc_0(), crypto.sc_0()])  # c, r

    for i in range(len(pubs)):
        if i == sec_idx:
            k = crypto.random_scalar()
            tmp3 = crypto.scalarmult_base(k)
            buff += crypto.encodepoint(tmp3)
            tmp3 = crypto.hash_to_ec(crypto.encodepoint(pubs[i]))
            tmp2 = crypto.scalarmult(tmp3, k)
            buff += crypto.encodepoint(tmp2)
        else:
            sig[i] = [crypto.random_scalar(), crypto.random_scalar()]
            tmp3 = crypto.ge_frombytes_vartime(pubs[i])
            tmp2 = crypto.ge_double_scalarmult_base_vartime(sig[i][0], tmp3, sig[i][1])
            buff += crypto.encodepoint(tmp2)
            tmp3 = crypto.hash_to_ec(crypto.encodepoint(tmp3))
            tmp2 = crypto.ge_double_scalarmult_precomp_vartime(sig[i][1], tmp3, sig[i][0], image_pre)
            buff += crypto.encodepoint(tmp2)
            sum = crypto.sc_add(sum, sig[i][0])

    h = crypto.hash_to_scalar(buff)
    sig[sec_idx][0] = crypto.sc_sub(h, sum)
    sig[sec_idx][1] = crypto.sc_mulsub(sig[sec_idx][0], sec, k)
    return sig


def check_ring_singature(prefix_hash, image, pubs, sig):
    """
    Checks ring signature generated with generate_ring_signature
    :param prefix_hash:
    :param image:
    :param pubs:
    :param sig:
    :return:
    """
    image_unp = crypto.ge_frombytes_vartime(image)
    image_pre = crypto.ge_dsm_precomp(image_unp)

    buff = b'' + prefix_hash
    sum = crypto.sc_0()
    for i in range(len(pubs)):
        if crypto.sc_check(sig[i][0]) != 0 or crypto.sc_check(sig[i][1]) != 0:
            return False

        tmp3 = crypto.ge_frombytes_vartime(pubs[i])
        tmp2 = crypto.ge_double_scalarmult_base_vartime(sig[i][0], tmp3, sig[i][1])
        buff += crypto.encodepoint(tmp2)
        tmp3 = crypto.hash_to_ec(crypto.encodepoint(pubs[i]))
        tmp2 = crypto.ge_double_scalarmult_precomp_vartime(sig[i][1], tmp3, sig[i][0], image_pre)
        buff += crypto.encodepoint(tmp2)
        sum = crypto.sc_add(sum, sig[i][0])

    h = crypto.hash_to_scalar(buff)
    h = crypto.sc_sub(h, sum)
    return crypto.sc_isnonzero(h) == 0


def export_key_image(creds, subaddresses, pkey, tx_pub_key, additional_tx_pub_keys, out_idx, test=True, verify=True):
    """
    Generates key image for the TXO + signature for the key image
    :param creds:
    :param subaddresses:
    :param pkey:
    :param tx_pub_key:
    :param additional_tx_pub_keys:
    :param out_idx:
    :param test:
    :param verify:
    :return:
    """
    r = monero.generate_key_image_helper(creds, subaddresses, pkey, tx_pub_key, additional_tx_pub_keys, out_idx)
    xi, ki, recv_derivation = r[:3]

    phash = crypto.encodepoint(ki)
    sig = generate_ring_signature(phash, ki, [pkey], xi, 0, test)

    if verify:
        if check_ring_singature(phash, ki, [pkey], sig) != 1:
            raise ValueError('Signature error')

    return ki, sig
