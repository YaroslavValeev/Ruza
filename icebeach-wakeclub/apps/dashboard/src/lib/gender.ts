import { WetsuitGender } from "../types";

const FEMALE_NAMES = new Set([
  "александра", "алена", "алина", "алла", "анастасия", "анна", "валентина", "валерия",
  "варвара", "вера", "вероника", "виктория", "галина", "дарья", "диана", "евгения",
  "екатерина", "елена", "елизавета", "жанна", "инна", "ирина", "карина", "кристина",
  "ксения", "лариса", "любовь", "людмила", "марина", "мария", "милана", "надежда",
  "наталья", "оксана", "ольга", "полина", "светлана", "снежана", "софия", "софья",
  "тамара", "татьяна", "ульяна", "юлия", "яна",
]);

const MALE_NAMES = new Set([
  "александр", "алексей", "андрей", "антон", "артём", "артем", "борис", "вадим",
  "валентин", "валерий", "виктор", "виталий", "владимир", "владислав", "геннадий",
  "георгий", "григорий", "дмитрий", "евгений", "иван", "игорь", "илья", "кирилл",
  "константин", "лев", "леонид", "максим", "михаил", "никита", "николай", "олег",
  "павел", "пётр", "петр", "рома", "роман", "сергей", "станислав", "степан",
  "тимофей", "фёдор", "федор", "юрий", "ярослав",
]);

const MALE_A_EXCEPTIONS = new Set(["никита", "илья", "савва", "кузьма", "фома", "данила", "саша"]);

function normalizeNamePart(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/ё/g, "е")
    .replace(/[^a-zа-я-]/gi, "");
}

export function inferGenderFromFullName(fullName: string): WetsuitGender | null {
  const parts = fullName.split(/\s+/).map(normalizeNamePart).filter(Boolean);
  if (parts.length === 0) {
    return null;
  }

  // Имя может стоять первым или вторым: «Ирина Смирнова» и «Смирнова Ирина».
  for (const part of parts) {
    if (FEMALE_NAMES.has(part)) {
      return "female";
    }
  }
  for (const part of parts) {
    if (MALE_NAMES.has(part)) {
      return "male";
    }
  }

  for (const part of parts) {
    if (/(овна|евна|ична)$/.test(part)) {
      return "female";
    }
    if (/(ович|евич)$/.test(part)) {
      return "male";
    }
  }

  if (parts.length > 1) {
    for (const part of parts) {
      if (/(ова|ева|ина|ына|ая|ская)$/.test(part)) {
        return "female";
      }
      if (/(ов|ев|ин|ын|ский|цкий)$/.test(part)) {
        return "male";
      }
    }
  }

  const first = parts[0];
  if (MALE_A_EXCEPTIONS.has(first)) {
    return "male";
  }
  if (/[ая]$/.test(first)) {
    return "female";
  }
  if (/[бвгджзклмнпрстфхцчшщй]$/.test(first)) {
    return "male";
  }
  return null;
}

export function genderLabel(gender?: WetsuitGender | null): string {
  if (gender === "male") return "Муж";
  if (gender === "female") return "Жен";
  return "—";
}

export function displayGenderForClient(fullName: string, stored?: WetsuitGender | null): string {
  return genderLabel(stored || inferGenderFromFullName(fullName));
}
