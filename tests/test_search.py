"""Search by the words a person types."""

from __future__ import annotations

import unittest

from harnsy_hr.errors import Refusal
from harnsy_hr.search import search
from harnsy_hr.types import Entry


def person(name: str, department: str, tagline: str, competency: str, *keywords: str) -> Entry:
    return Entry.read({"id": "harnsy/" + name, "title": name.replace("-", " ").capitalize(), "summary": tagline,
                       "department": department, "persona": {"name": "Ada"}, "skills": [competency], "keywords": list(keywords)})


STAFF = [
    person("bookkeeper", "finance", "Keeps the ledger tidy every day.", "Ledger entries", "accounting records", "invoices"),
    person("accountant", "finance", "Closes your month on a calendar.", "Month-end close", "reconcile invoices"),
    person("reviewer", "engineering", "Finds the race before it ships.", "Go review", "code review", "pull request"),
    person("developer-go", "engineering", "Ships small Go services.", "Go services", "backend"),
]
PAIR = [
    person("account-executive", "sales", "Prepares your sales calls.", "Call preparation"),
    person("accountant", "finance", "Closes your month on a calendar.", "Month-end close"),
]


def ids(entries) -> str:
    return " ".join(e.id.removeprefix("harnsy/") for e in entries)


class SearchTest(unittest.TestCase):
    def test_search(self) -> None:
        for name, text, department, want in [
            ("no words: everyone, in the feed's order", "", "", "bookkeeper accountant reviewer developer-go"),
            ("the title beats a keyword", "accountant", "", "accountant bookkeeper"),
            ("a phrase a person types", "Find me someone to review Go code", "", "reviewer developer-go"),
            ("more words matched come first", "go services backend", "", "developer-go reviewer"),
            ("a department alone", "", "finance", "bookkeeper accountant"),
            ("words within a department", "invoices", "engineering", ""),
            ("any letter case", "INVOICES", "Finance", "bookkeeper accountant"),
            ("nothing matches", "zeppelin pilot", "", ""),
            ("the persona's name", "ada", "", "bookkeeper accountant reviewer developer-go"),
        ]:
            with self.subTest(name):
                self.assertEqual(ids(search(STAFF, text, department)), want)

    def test_the_exact_word_comes_first(self) -> None:
        for text, want in [("accountant", "accountant account-executive"), ("find an Accountants", "accountant account-executive"),
                           ("account executive", "account-executive accountant"),
                           ("accounting", "account-executive accountant"),  # neither is named: the feed's order
                           ("an executive for sales", "account-executive")]:
            self.assertEqual(ids(search(PAIR, text)), want, text)

    def test_a_request_is_short(self) -> None:
        for long in ["x" * 257, " ".join(f"word{i}" for i in range(17))]:
            with self.assertRaises(Refusal) as got:
                search(STAFF, long)
            self.assertNotIn("word1", str(got.exception))


if __name__ == "__main__":
    unittest.main()
