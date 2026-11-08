"""Small CSV helpers shared by the tools that rewrite a course's CSV files."""
import csv
import os

BOM = b"\xef\xbb\xbf"


def detect_eol(path, default="\n"):
    """The line ending an existing CSV file uses ("\\r\\n" or "\\n"), from its header line, or
    `default` for a missing/one-line file. Pass it as DictWriter's lineterminator so rewriting a
    file does not flip every line (csv's own default is "\\r\\n")."""
    try:
        with open(path, "rb") as f:
            head = f.read(65536)
    except OSError:
        return default
    idx = head.find(b"\n")
    if idx < 0:
        return default
    return "\r\n" if head[idx - 1 : idx] == b"\r" else "\n"


def has_bom(path):
    """True when the file starts with a UTF-8 byte order mark."""
    try:
        with open(path, "rb") as f:
            return f.read(3) == BOM
    except OSError:
        return False


def read_dict_csv(path, strict=True):
    """(fieldnames, rows) of a CSV file, reading through a UTF-8 BOM (utf-8-sig); ([], []) for a
    missing file. strict: raise ValueError when a row has more columns than the header (usually an
    unescaped comma), since writing such a row back would crash DictWriter mid-file."""
    if not os.path.isfile(path):
        return [], []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, restkey="_extra")
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    if strict:
        bad = [r.get("id") for r in rows if r.get("_extra")]
        if bad:
            raise ValueError(
                f"{path}: malformed row(s) with extra columns (id={bad}) - likely an unescaped comma "
                "in a field. Fix the CSV by hand before running this script."
            )
    return fieldnames, rows


def write_dict_csv(path, fieldnames, rows):
    """Rewrite a CSV atomically (temp file + os.replace, so a crash never leaves it truncated),
    keeping the existing file's line endings and its UTF-8 BOM if it had one."""
    tmp = path + ".tmp"
    encoding = "utf-8-sig" if has_bom(path) else "utf-8"
    with open(tmp, "w", encoding=encoding, newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator=detect_eol(path))
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)
