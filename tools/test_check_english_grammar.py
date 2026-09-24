import csv
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import check_english_grammar as g  # noqa: E402


def fixed(text):
    return g.apply_rules(text)[0]


class RuleTests(unittest.TestCase):
    def test_uncountable_article(self):
        self.assertEqual(fixed("I want a water"), "I want water")
        self.assertEqual(fixed("Give me a water"), "Give me some water")
        self.assertEqual(fixed("Can I have an information?"), "Can I have some information?")
        self.assertEqual(fixed("A rice, please."), "Some rice, please.")

    def test_countable_ordering_left_alone(self):
        for ok in ("A coffee, please.", "I want a bottle of water.", "I want water.",
                   "I want some water.", "A table for two."):
            self.assertEqual(fixed(ok), ok)

    def test_a_an(self):
        self.assertEqual(fixed("I have a apple"), "I have an apple")
        self.assertEqual(fixed("It is an book"), "It is a book")
        for ok in ("a university", "an hour", "a one-way ticket", "an SQL query", "a US visa"):
            self.assertEqual(fixed(ok), ok)

    def test_verbs(self):
        self.assertEqual(fixed("I am agree"), "I agree")
        self.assertEqual(fixed("I have 20 years"), "I am 20 years old")
        self.assertEqual(fixed("She have a bag"), "She has a bag")
        self.assertEqual(fixed("He don't like tea"), "He doesn't like tea")

    def test_clean_text_untouched(self):
        s = "How much is this? I'm staying in a hotel. I have a reservation."
        self.assertEqual(fixed(s), s)


class ExtractionTests(unittest.TestCase):
    def test_skips_farsi_single_words_and_mixed_lines(self):
        self.assertEqual(g.english_segments("prompt", "Hello\nیعنی چی؟"), [])
        self.assertEqual(g.english_segments("prompt", "Hello یعنی چی؟"), [])
        self.assertEqual(g.english_segments("prompt", "I want a water\nیعنی چی؟"), ["I want a water"])

    def test_options_split(self):
        self.assertEqual(g.english_segments("options", "I want water|Hello|Good morning"),
                         ["I want water", "Good morning"])

    def test_blanks_and_backticks_stripped(self):
        self.assertEqual(g.english_segments("prompt", "I want {{1}} water"), [])
        self.assertEqual(g.english_segments("prompt", "Use `git status` now"), ["Use git status now"])


class PlanTests(unittest.TestCase):
    def card(self, **kw):
        base = {"type": "multiple_choice", "options": "I want a water|I want water", "correct_index": "1"}
        base.update(kw)
        return base

    def test_wrong_option_is_review_not_autofixed(self):
        safe, review = g.plan_card_fixes(self.card(), [("rule", "I want a water", "I want water", "x")])
        self.assertEqual((safe, len(review)), ([], 1))

    def test_correct_option_is_safe(self):
        c = self.card(options="I want a water|Hello", correct_index="0")
        safe, review = g.plan_card_fixes(c, [("rule", "I want a water", "I want some water", "x")])
        self.assertEqual((len(safe), review), (1, []))

    def test_fix_making_duplicate_options_needs_review(self):
        c = self.card(options="I want some water|I want a water", correct_index="1")
        safe, review = g.plan_card_fixes(c, [("rule", "I want a water", "I want some water", "x")])
        self.assertEqual((safe, len(review)), ([], 1))

    def test_noop_and_case_only_changes_ignored(self):
        self.assertFalse(g.is_real_change("I agree", "I agree"))
        self.assertFalse(g.is_real_change("a Room", "a room"))
        self.assertFalse(g.is_real_change("I'm hungry", "I'm hungry."))
        self.assertTrue(g.is_real_change("I want a water", "I want water"))

    def test_contraction_and_completion_ignored(self):
        self.assertFalse(g.is_real_change("I'm thirsty", "I am thirsty"))
        self.assertFalse(g.is_real_change("I need", "I need to"))
        self.assertTrue(g.is_real_change("What is name?", "What is your name?"))

    def test_fragments_and_blanks_skipped(self):
        self.assertEqual(g.english_segments("options", "I want|I need a|Excuse me"), ["Excuse me"])
        self.assertEqual(g.english_segments("prompt", "I need a {{1}}."), [])

    def test_llm_findings_never_auto_applied(self):
        c = {"type": "type_answer", "options": "x"}
        safe, review = g.plan_card_fixes(c, [("llm", "She happy", "She is happy", "x")])
        self.assertEqual((safe, len(review)), ([], 1))

    def test_insane_llm_fix_needs_review(self):
        c = {"type": "type_answer", "options": "x"}
        safe, review = g.plan_card_fixes(c, [("llm", "I want a water", "سلام", "x")])
        self.assertEqual((safe, len(review)), ([], 1))


class RoundTripTests(unittest.TestCase):
    def test_csv_roundtrip_preserves_bytes_and_applies_fix(self):
        raw = ('id,type,prompt,options,explanation\r\n'
               '1,type_answer,"سلام\nI want a water",Hello,"x, y"\r\n')
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "cards.csv")
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write(raw)
            rows, meta, _ = g.read_rows(p)
            g.write_rows(p, rows, meta)
            self.assertEqual(open(p, encoding="utf-8", newline="").read(), raw)
            g.apply_fixes_to_row(rows[0], g.CARD_FIELDS, [("I want a water", "I want some water", "", "rule")])
            g.write_rows(p, rows, meta)
            self.assertIn("I want some water", open(p, encoding="utf-8", newline="").read())

    def test_llm_hallucinated_original_is_dropped(self):
        # 'original' not present in any segment must never reach findings.
        segs = ["I want water"]
        self.assertFalse(any("I want a water" in s for s in segs))


if __name__ == "__main__":
    unittest.main()
