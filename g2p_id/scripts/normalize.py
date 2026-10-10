"""Normalisasi teks agar enak dibaca oleh model TTS.

Dipisah dari tts.py supaya bisa dipakai ulang oleh backend tanpa harus
menarik dependensi berat (wget, simpleaudio, torch).
"""

import re

from .terbilang import terbilang


def ganti_angka(s):
    while True:
        match = re.search(r'\d+', s)
        if not match:
            return s
        angka = int(match.group(0))
        t = terbilang(angka)
        awal, akhir = match.span()
        s = s[:awal] + t + s[akhir:]


def ganti_persen(s):
    while True:
        i = s.find('%')
        if i < 0:
            return s
        s = s[:i] + ' persen' + s[i+1:]


def ganti_titik_dua(s):
    while True:
        match = re.search(r'\b\w+:', s)
        if not match:
            return s
        awal, akhir = match.span()
        s = s[:akhir-1] + ',' + s[akhir:]


def text_normalization(content):
    text_list = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        if line[-1] not in ['.', '?', '!']:
            line = line + '.'
        line = ganti_angka(line)
        line = ganti_persen(line)
        line = ganti_titik_dua(line)
        text_list.append(line)
    return '\n'.join(text_list)
