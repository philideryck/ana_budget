import unicodedata
import re
import csv

def strip_accents(s: str) -> str:
    if s is None:
        return ""
    return "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")

def normalize_header(h: str) -> str:
    h = strip_accents(h).lower().strip()
    h = re.sub(r"[^\w]+", "_", h)  # espaces/ponctuation -> underscore
    h = re.sub(r"_+", "_", h).strip("_")
    return h

def detect_dialect(path: str) -> csv.Dialect:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        sample = f.read(4096)
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=";,|\t,")
        dialect.doublequote = True
        dialect.skipinitialspace = True
        return dialect
    except Exception:
        class SemiColon(csv.Dialect):
            delimiter = ";"
            quotechar = '"'
            doublequote = True
            skipinitialspace = True
            lineterminator = "\n"
        return SemiColon()
