#!/usr/bin/env python3
"""Tests for generate_language_course.py — stdlib unittest, matching this
repo's dependency-free convention. Run with:
    python tools/test_generate_language_course.py
"""
import random
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_language_course import VocabRow, build_cards_csv, build_units_csv

RTL_PATTERN = re.compile(f"[{chr(0x0590)}-{chr(0x08FF)}]")
CHOICE_TYPES = {"multiple_choice", "multi_select", "image_choice", "select_blank"}


def sample_rows():
    return [
        VocabRow("Greetings", "Hello", "word", "سلام"),
        VocabRow("Greetings", "Please", "word", "لطفاً"),
        VocabRow("Greetings", "Thank you", "phrase", "متشکرم"),
        VocabRow("Numbers", "One", "word", "یک"),
        VocabRow("Numbers", "Two", "word", "دو"),
    ]


class GenerateLanguageCourseTest(unittest.TestCase):
    def setUp(self):
        self.rows = sample_rows()
        self.cards, self.tts_manifest = build_cards_csv(self.rows, random.Random(0))

    def test_units_grouped_by_deck_in_first_seen_order(self):
        units = build_units_csv(self.rows)
        self.assertEqual([u["title"] for u in units], ["Greetings", "Numbers"])
        self.assertEqual([u["id"] for u in units], ["1", "2"])

    def test_every_pack_has_a_preview_a_main_and_at_least_three_practice_cards(self):
        mains = [c for c in self.cards if c["role"] == "main"]
        self.assertEqual(len(mains), len(self.rows))
        for main in mains:
            previews = [
                c for c in self.cards if c["role"] == "preview" and c["related_main_id"] == main["id"]
            ]
            exercises = [
                c for c in self.cards if c["role"] == "exercise" and c["related_main_id"] == main["id"]
            ]
            self.assertEqual(len(previews), 1, f"main {main['id']} should have exactly one preview")
            self.assertGreaterEqual(
                len(exercises), 3, f"main {main['id']} should have at least 3 practice cards"
            )

    def test_true_false_only_ever_used_for_preview(self):
        offenders = [c for c in self.cards if c["type"] == "true_false" and c["role"] != "preview"]
        self.assertEqual(offenders, [], f"true_false used outside preview: {offenders}")

    def test_no_options_list_mixes_scripts(self):
        for card in self.cards:
            if card["type"] not in CHOICE_TYPES:
                continue
            options = [o for o in card["options"].split("|") if o]
            scripts = {"rtl" if RTL_PATTERN.search(o) else "ltr" for o in options}
            self.assertLessEqual(
                len(scripts), 1, f"card {card['id']} mixes scripts in its options: {options}"
            )

    def test_every_distractor_traces_back_to_an_earlier_row(self):
        # The ledger invariant: a "meaning" multiple_choice card's wrong
        # options must always be glosses from rows that appear *before*
        # the current one in the input — never the current row's own gloss
        # repeated, and never a gloss that doesn't exist in the vocabulary
        # at all.
        gloss_by_word = {r.target_word: r.base_gloss for r in self.rows}
        row_index_by_gloss = {r.base_gloss: i for i, r in enumerate(self.rows)}
        for card in self.cards:
            if card["type"] != "multiple_choice":
                continue
            target_word = card["prompt"].split(" یعنی")[0]
            if target_word not in gloss_by_word:
                continue
            current_index = next(i for i, r in enumerate(self.rows) if r.target_word == target_word)
            options = [o for o in card["options"].split("|") if o]
            for opt in options[1:]:  # options[0] is the correct gloss itself
                self.assertIn(opt, row_index_by_gloss, f"distractor {opt!r} isn't a real gloss")
                self.assertLess(
                    row_index_by_gloss[opt],
                    current_index,
                    f"card for {target_word!r} uses a distractor from a later row: {opt!r}",
                )

    def test_no_pack_repeats_the_identical_question(self):
        # Regression: the generator used to ask "X یعنی چی؟" twice per pack
        # (main + a "second attempt" practice) with only the distractor set
        # different — validate_course.py now hard-errors on exactly this
        # pattern for any non-production card type.
        mains = [c for c in self.cards if c["role"] == "main"]
        for main in mains:
            pack = [main] + [
                c for c in self.cards if c["role"] == "exercise" and c["related_main_id"] == main["id"]
            ]
            seen = {}
            for card in pack:
                if card["type"] in ("speech_recognition", "listening_card"):
                    continue
                prompt = card["prompt"].strip()
                if not prompt:
                    continue
                seen[prompt] = seen.get(prompt, 0) + 1
            duplicates = {p: n for p, n in seen.items() if n > 1}
            self.assertEqual(duplicates, {}, f"pack for main {main['id']} repeats a question: {duplicates}")

    def test_reproducible_with_the_same_seed(self):
        first = build_cards_csv(self.rows, random.Random(0))
        second = build_cards_csv(self.rows, random.Random(0))
        self.assertEqual(first, second)

    def test_every_listening_card_has_audio_and_a_matching_tts_manifest_entry(self):
        listening_cards = [c for c in self.cards if c["type"] == "listening_card"]
        # Rows with at least one prior item get a listening_card rep (row 0,
        # "Hello", has no prior item to build either variant from and is the
        # only one skipped) — 4 of this fixture's 5 rows qualify.
        self.assertEqual(len(listening_cards), 4)
        manifest_by_audio = {m["audio"]: m["text"] for m in self.tts_manifest}
        for card in listening_cards:
            self.assertTrue(card["audio"], f"listening_card {card['id']} has no audio filename")
            self.assertIn(card["audio"], manifest_by_audio, "every listening_card's audio must be in the manifest")
            response_type = card["options"].split("|")[0]
            self.assertIn(response_type, ("select", "type"))
            if response_type == "select":
                self.assertTrue(card["correct_index"])

    def test_type_answer_card_asks_for_the_target_word_from_its_gloss(self):
        # Every 3rd row (i % 3 == 0), not every row — see the generator's own
        # comment on why: one type_answer per pack alone would already push
        # a course over validate_course.py's 10% typing-card budget.
        type_cards = [c for c in self.cards if c["type"] == "type_answer"]
        row_by_word = {r.target_word: r for r in self.rows}
        self.assertEqual(len(type_cards), 2)  # rows 0 ("Hello") and 3 ("One")
        for card in type_cards:
            accepted_word = card["options"]
            self.assertIn(accepted_word, row_by_word, "accepted answer must be a real target word")
            self.assertIn(row_by_word[accepted_word].base_gloss, card["prompt"])

    def test_type_answer_typing_budget_stays_under_ten_percent(self):
        TYPING_TYPES = {"type_answer", "numeric_answer", "code_fill", "command_output", "short_answer"}

        def requires_typing(c):
            if c["type"] in TYPING_TYPES:
                return True
            if c["type"] == "listening_card":
                return c["options"].split("|", 1)[0] == "type"
            return False

        typing_count = sum(requires_typing(c) for c in self.cards)
        self.assertLessEqual(typing_count / len(self.cards), 0.10)

    def test_example_sentence_produces_an_order_practice_card(self):
        rows = sample_rows()
        rows[2] = VocabRow(
            "Greetings", "Thank you", "phrase", "متشکرم",
            example_sentence="Hello,|Thank you",
            example_gloss="سلام، متشکرم",
        )
        cards, _ = build_cards_csv(rows, random.Random(0))
        main = next(c for c in cards if c["role"] == "main" and c["prompt"] == "Thank you یعنی چی؟")
        sentence_cards = [
            c for c in cards
            if c["type"] == "order" and c["related_main_id"] == main["id"]
        ]
        self.assertEqual(len(sentence_cards), 1)
        self.assertEqual(sentence_cards[0]["options"], "Hello,|Thank you")

    def test_three_or_more_substitutions_still_get_distinct_order_prompts(self):
        # Regression: a pack listing 3+ ";;" substitutions used to cycle
        # only two prompt phrasings, so the 2nd and 3rd order cards shared
        # the identical prompt text — validate_course.py's "identical
        # question in a pack" check correctly flags exactly this.
        rows = sample_rows()
        rows[2] = VocabRow(
            "Greetings", "Thank you", "phrase", "متشکرم",
            example_sentence="Hello,|Thank you;;Please,|Thank you;;Yes,|Thank you",
            example_gloss="سلام، متشکرم؛؛لطفاً، متشکرم؛؛بله، متشکرم",
        )
        cards, _ = build_cards_csv(rows, random.Random(0))
        main = next(c for c in cards if c["role"] == "main" and c["prompt"] == "Thank you یعنی چی؟")
        order_cards = [c for c in cards if c["type"] == "order" and c["related_main_id"] == main["id"]]
        self.assertEqual(len(order_cards), 3)
        prompts = [c["prompt"] for c in order_cards]
        self.assertEqual(len(prompts), len(set(prompts)), f"order prompts must all differ: {prompts}")

    def test_no_example_sentence_means_no_order_card_for_that_pack(self):
        # sample_rows() supplies no example_sentence at all — none of its
        # packs should contain an order card.
        self.assertEqual([c for c in self.cards if c["type"] == "order"], [])

    def test_example_gloss_produces_a_translate_the_sentence_typing_card(self):
        rows = sample_rows()
        rows[2] = VocabRow(
            "Greetings", "Thank you", "phrase", "متشکرم",
            example_sentence="Hello,|Thank you",
            example_gloss="سلام، متشکرم",
        )
        cards, _ = build_cards_csv(rows, random.Random(0))
        main = next(c for c in cards if c["role"] == "main" and c["prompt"] == "Thank you یعنی چی؟")
        pack = [c for c in cards if c["related_main_id"] == main["id"]]

        translate_cards = [
            c for c in pack if c["type"] == "type_answer" and c["options"] == "Hello, Thank you"
        ]
        self.assertEqual(len(translate_cards), 1)
        self.assertIn("سلام، متشکرم", translate_cards[0]["prompt"])

    def test_translate_the_sentence_card_needs_example_gloss_not_just_example_sentence(self):
        rows = sample_rows()
        rows[2] = VocabRow(
            "Greetings", "Thank you", "phrase", "متشکرم",
            example_sentence="Hello,|Thank you",
            example_gloss="",
        )
        cards, _ = build_cards_csv(rows, random.Random(0))
        main = next(c for c in cards if c["role"] == "main" and c["prompt"] == "Thank you یعنی چی؟")
        pack = [c for c in cards if c["related_main_id"] == main["id"]]
        translate_cards = [c for c in pack if c["type"] == "type_answer"]
        self.assertEqual(translate_cards, [])

    def test_example_sentence_also_gets_a_full_sentence_speech_card_and_fill_in_blank(self):
        rows = sample_rows()
        rows[2] = VocabRow(
            "Greetings", "Thank you", "phrase", "متشکرم",
            example_sentence="Hello,|Thank you",
            example_gloss="سلام، متشکرم",
        )
        cards, _ = build_cards_csv(rows, random.Random(0))
        main = next(c for c in cards if c["role"] == "main" and c["prompt"] == "Thank you یعنی چی؟")
        pack = [c for c in cards if c["related_main_id"] == main["id"]]

        speech_cards = [c for c in pack if c["type"] == "speech_recognition" and c["prompt"] == "Hello, Thank you"]
        self.assertEqual(len(speech_cards), 1, "the full sentence must be said aloud, not just the isolated word")

        # "Thank you" fits as an option (2 words) and prior rows (Hello,
        # Please) supply real distractors, so a fill-in-the-blank rep should
        # also appear.
        blank_cards = [c for c in pack if c["type"] == "select_blank"]
        self.assertEqual(len(blank_cards), 1)
        self.assertEqual(blank_cards[0]["prompt"], "Hello, ___")
        options = blank_cards[0]["options"].split("|")
        self.assertEqual(options[int(blank_cards[0]["correct_index"])], "Thank you")

    def test_sentence_practice_cards_come_before_the_other_practice_cards(self):
        rows = sample_rows()
        rows[2] = VocabRow(
            "Greetings", "Thank you", "phrase", "متشکرم",
            example_sentence="Hello,|Thank you",
            example_gloss="سلام، متشکرم",
        )
        cards, _ = build_cards_csv(rows, random.Random(0))
        main = next(c for c in cards if c["role"] == "main" and c["prompt"] == "Thank you یعنی چی؟")
        exercises = [c for c in cards if c["role"] == "exercise" and c["related_main_id"] == main["id"]]
        # The reverse-direction multiple_choice quiz (step 4) is the first
        # card that is unambiguously NOT part of the sentence-practice
        # block — everything before it must be order/select_blank/the
        # full-sentence speech_recognition rep.
        first_old_style = next(i for i, c in enumerate(exercises) if c["type"] == "multiple_choice")
        leading = exercises[:first_old_style]
        self.assertEqual(
            {c["type"] for c in leading}, {"order", "select_blank", "speech_recognition", "type_answer"}
        )
        self.assertIn("order", [c["type"] for c in leading])


if __name__ == "__main__":
    unittest.main()
