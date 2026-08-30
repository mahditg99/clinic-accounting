# -*- coding: utf-8 -*-
"""Minimal RSA (PKCS#1 v1.5 with SHA-256) written in pure Python.

Why hand-rolled: the target machine runs Windows 7 with Python 3.8 and the
packaged exe must not depend on any binary wheel (``cryptography`` ships a
Rust extension that is fragile on that platform).  Everything here uses only
the standard library, so the same file runs from source and inside PyInstaller.

Scope is deliberately tiny: sign one short message and verify it.  This is a
license check, not a TLS stack — no OAEP, no multi-prime CRT, no key parsing
beyond the JSON form produced by :func:`key_to_json`.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
from typing import Dict

__all__ = ["generate_keypair", "sign", "verify", "key_to_json",
           "key_from_json", "fingerprint", "modulus_bytes"]


# --------------------------------------------------------------------------- #
# Small-prime table (trial division) — built once with a sieve.
# --------------------------------------------------------------------------- #

def _sieve(limit):
    # type: (int) -> list
    flags = bytearray([1]) * (limit + 1)
    flags[0] = flags[1] = 0
    for i in range(2, int(limit ** 0.5) + 1):
        if flags[i]:
            flags[i * i::i] = bytearray(len(flags[i * i::i]))
    return [i for i, v in enumerate(flags) if v]


_SMALL_PRIMES = _sieve(1500)

# DER prefix of DigestInfo(SHA-256): the fixed part of a PKCS#1 v1.5 digest.
_SHA256_ASN1 = bytes.fromhex("3031300d060960864801650304020105000420")


# --------------------------------------------------------------------------- #
# Number theory helpers
# --------------------------------------------------------------------------- #

def _gcd(a, b):
    # type: (int, int) -> int
    while b:
        a, b = b, a % b
    return a


def _modinv(a, m):
    # type: (int, int) -> int
    """Extended Euclid.  Written out rather than using pow(a, -1, m) because
    that three-argument inverse only landed in Python 3.8 and we want the
    arithmetic to be obvious in a security-sensitive path."""
    if a < 0:
        a %= m
    g, x, _ = _egcd(a, m)
    if g != 1:
        raise ValueError("no modular inverse")
    return x % m


def _egcd(a, b):
    # type: (int, int) -> tuple
    old_r, r = a, b
    old_s, s = 1, 0
    while r:
        q = old_r // r
        old_r, r = r, old_r - q * r
        old_s, s = s, old_s - q * s
    return old_r, old_s, 0


def _is_prime(n, rounds=24, rng=None):
    # type: (int, int, random.Random) -> bool
    if n < 2:
        return False
    for p in _SMALL_PRIMES:
        if n % p == 0:
            return n == p
    # Miller-Rabin
    d = n - 1
    r = 0
    while d % 2 == 0:
        d //= 2
        r += 1
    rand = rng or random.SystemRandom()
    for _ in range(rounds):
        a = rand.randrange(2, n - 2)
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(r - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def _gen_prime(bits, rng):
    # type: (int, random.Random) -> int
    """Random prime of exactly ``bits`` bits (top two bits forced so that
    p*q always fills the full modulus width)."""
    while True:
        cand = int.from_bytes(os.urandom((bits + 7) // 8), "big")
        cand |= (1 << (bits - 1)) | (1 << (bits - 2))
        cand |= 1
        if _is_prime(cand, 24, rng):
            return cand


def generate_keypair(bits=2048, e=65537):
    # type: (int, int) -> Dict[str, int]
    """Return ``{n, e, d, p, q}``.  Takes a couple of seconds in pure Python."""
    if bits % 2:
        raise ValueError("bits must be even")
    rng = random.SystemRandom()
    half = bits // 2
    while True:
        p = _gen_prime(half, rng)
        q = _gen_prime(half, rng)
        if p == q:
            continue
        n = p * q
        if n.bit_length() != bits:
            continue
        lam = (p - 1) * (q - 1) // _gcd(p - 1, q - 1)  # Carmichael lambda
        if _gcd(e, lam) != 1:
            continue
        d = _modinv(e, lam)
        return {"n": n, "e": e, "d": d, "p": p, "q": q}


# --------------------------------------------------------------------------- #
# PKCS#1 v1.5 encode / decode
# --------------------------------------------------------------------------- #

def modulus_bytes(n):
    # type: (int) -> int
    return (n.bit_length() + 7) // 8


def _emsa(msg, k):
    # type: (bytes, int) -> bytes
    """EMSA-PKCS1-v1_5(msg) — the exact byte string that gets exponentiated."""
    digest = hashlib.sha256(msg).digest()
    tail = _SHA256_ASN1 + digest
    pad = k - len(tail) - 3
    if pad < 8:
        raise ValueError("message too long for this key")
    return b"\x00\x01" + (b"\xff" * pad) + b"\x00" + tail


def _const_eq(a, b):
    # type: (bytes, bytes) -> bool
    if len(a) != len(b):
        return False
    acc = 0
    for x, y in zip(a, b):
        acc |= x ^ y
    return acc == 0


def sign(msg, d, n):
    # type: (bytes, int, int) -> bytes
    k = modulus_bytes(n)
    em = _emsa(msg, k)
    m = int.from_bytes(em, "big")
    if m >= n:
        raise ValueError("message representative out of range")
    return pow(m, d, n).to_bytes(k, "big")


def verify(msg, sig, e, n):
    # type: (bytes, bytes, int, int) -> bool
    k = modulus_bytes(n)
    if not isinstance(sig, (bytes, bytearray)) or len(sig) != k:
        return False
    s = int.from_bytes(bytes(sig), "big")
    if s >= n:
        return False
    try:
        em = pow(s, e, n).to_bytes(k, "big")
    except OverflowError:
        return False
    try:
        return _const_eq(em, _emsa(msg, k))
    except ValueError:
        return False


# --------------------------------------------------------------------------- #
# Key serialisation (hex integers in JSON — readable, diffable, no deps)
# --------------------------------------------------------------------------- #

def key_to_json(keys, private=True):
    # type: (Dict[str, int], bool) -> str
    out = {"n": "%x" % keys["n"], "e": int(keys["e"])}
    if private:
        for part in ("d", "p", "q"):
            if part in keys:
                out[part] = "%x" % keys[part]
    return json.dumps(out, indent=2, sort_keys=True)


def key_from_json(text):
    # type: (str) -> Dict[str, int]
    raw = json.loads(text)
    keys = {}  # type: Dict[str, int]
    for part in ("n", "e", "d", "p", "q"):
        if part in raw:
            val = raw[part]
            keys[part] = int(val, 16) if isinstance(val, str) else int(val)
    if "n" not in keys or "e" not in keys:
        raise ValueError("incomplete key")
    return keys


def fingerprint(n, e=65537):
    # type: (int, int) -> str
    """Short id for a public key, so the issuer tool can prove it matches the
    key embedded in the shipped program."""
    blob = ("%x|%x" % (n, e)).encode("ascii")
    return hashlib.sha256(blob).hexdigest()[:8].upper()


def self_test():
    # type: () -> bool
    """Fast sanity check of the primitives without generating a key."""
    n = int("f" * 512, 16) | 1  # not prime, only used for width
    try:
        _emsa(b"x", modulus_bytes(n))
    except ValueError:
        return False
    return math.gcd(65537, 65536) == 1
