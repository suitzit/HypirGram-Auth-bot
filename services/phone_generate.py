import re
from collections import Counter
from pathlib import Path
from random import choice, randint


def is_valid(phone: str) -> bool:
    if re.search(r"(\d)\1", phone):
        return False

    counts = Counter(phone)

    return max(counts.values()) <= 4

def random_file(folder: str | Path) -> Path:
    folder = Path(folder)

    if not folder.is_dir():
        raise NotADirectoryError(f"Не папка: {folder}")

    files = [p for p in folder.iterdir() if p.is_file()]

    if not files:
        raise FileNotFoundError(f"Не файл: {files}")

    return choice(files)

def random_code(file_path: Path) -> str | None:
    with open(file_path, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        return None
    
    return choice(lines).strip()

def generate_phone():
    while True:
        f = random_file("resources/area_code")
        code = random_code(f)

        if f.stem == "code_with_nine_digits":
            number = randint(100000000, 999999999)
        elif f.stem == "code_with_ten_digits":
            number = randint(1000000000, 9999999999)
        else:
            continue

        phone = f"{code}{number}"

        if not is_valid(phone):
            continue

        return phone
