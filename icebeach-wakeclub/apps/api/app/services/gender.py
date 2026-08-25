from __future__ import annotations

FEMALE_NAMES = {
    "александра",
    "алена",
    "алина",
    "алла",
    "анастасия",
    "анна",
    "валентина",
    "валерия",
    "варвара",
    "вера",
    "вероника",
    "виктория",
    "галина",
    "дарья",
    "диана",
    "евгения",
    "екатерина",
    "елена",
    "елизавета",
    "жанна",
    "инна",
    "ирина",
    "карина",
    "кристина",
    "ксения",
    "лариса",
    "любовь",
    "людмила",
    "марина",
    "мария",
    "милана",
    "надежда",
    "наталья",
    "оксана",
    "ольга",
    "полина",
    "светлана",
    "снежана",
    "софия",
    "софья",
    "тамара",
    "татьяна",
    "ульяна",
    "юлия",
    "яна",
}

MALE_NAMES = {
    "александр",
    "алексей",
    "андрей",
    "антон",
    "артем",
    "борис",
    "вадим",
    "валентин",
    "валерий",
    "виктор",
    "виталий",
    "владимир",
    "владислав",
    "геннадий",
    "георгий",
    "григорий",
    "дмитрий",
    "евгений",
    "иван",
    "игорь",
    "илья",
    "кирилл",
    "константин",
    "лев",
    "леонид",
    "максим",
    "михаил",
    "никита",
    "николай",
    "олег",
    "павел",
    "петр",
    "рома",
    "роман",
    "сергей",
    "станислав",
    "степан",
    "тимофей",
    "федор",
    "юрий",
    "ярослав",
}

MALE_A_EXCEPTIONS = {"никита", "илья", "савва", "кузьма", "фома", "данила", "саша"}


def _normalize_name_part(value: str) -> str:
    cleaned = value.strip().lower().replace("ё", "е")
    return "".join(char for char in cleaned if char.isalpha() or char == "-")


def infer_gender_from_full_name(full_name: str) -> str | None:
    """Guess male/female from a Russian full name when Sheets has no wetsuit gender."""
    parts = [_normalize_name_part(part) for part in full_name.split() if _normalize_name_part(part)]
    if not parts:
        return None

    for part in parts:
        if part in FEMALE_NAMES:
            return "female"
    for part in parts:
        if part in MALE_NAMES:
            return "male"

    for part in parts:
        if part.endswith(("овна", "евна", "ична")):
            return "female"
        if part.endswith(("ович", "евич")):
            return "male"

    if len(parts) > 1:
        for part in parts:
            if part.endswith(("ова", "ева", "ина", "ына", "ая", "ская")):
                return "female"
            if part.endswith(("ов", "ев", "ин", "ын", "ский", "цкий")):
                return "male"

    first = parts[0]
    if first in MALE_A_EXCEPTIONS:
        return "male"
    if first.endswith(("а", "я")):
        return "female"
    if first and first[-1] in "бвгджзклмнпрстфхцчшщй":
        return "male"
    return None
