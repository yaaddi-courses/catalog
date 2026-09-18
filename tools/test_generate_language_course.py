#!/usr/bin/env python3
"""Tests for generate_language_course.py — stdlib unittest, matching this
repo's dependency-free convention. Run with:
    python tools/test_generate_language_course.py
"""
import json
import random
import re
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_language_course import (
    VocabRow,
    build_cards_csv,
    build_units_csv,
    deck_cover_prompt,
    generate_deck_cover,
    generate_deck_covers,
    meaning_question,
)

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
        # No --generate-images flag involved in this call — every unit's
        # image column stays blank, same as before this feature existed.
        self.assertEqual([u["image"] for u in units], ["", ""])

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

    def test_bilingual_prompts_and_explanations_split_target_and_gloss_onto_separate_lines(self):
        # See AUTHORING.md's "Bilingual text goes on separate lines" section:
        # the app can only align a whole line one way, so a line mixing
        # English and Farsi can't be aligned correctly either way — every
        # generator template that combines the target word/phrase with a
        # Farsi gloss must put them on separate lines (a literal "\n"), never
        # side by side on one.
        for card in self.cards:
            for field in ("prompt", "explanation"):
                text = card[field]
                if not (RTL_PATTERN.search(text) and re.search("[A-Za-z]", text)):
                    continue  # not actually bilingual — nothing to check
                for line in text.split("\n"):
                    has_rtl = bool(RTL_PATTERN.search(line))
                    has_ltr = bool(re.search("[A-Za-z]", line))
                    self.assertFalse(
                        has_rtl and has_ltr,
                        f"card {card['id']} {field!r} mixes scripts on one line: {line!r}",
                    )

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
            target_word = card["prompt"].split("\n")[0]
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
        main = next(c for c in cards if c["role"] == "main" and c["prompt"] == meaning_question("Thank you"))
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
        main = next(c for c in cards if c["role"] == "main" and c["prompt"] == meaning_question("Thank you"))
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
        main = next(c for c in cards if c["role"] == "main" and c["prompt"] == meaning_question("Thank you"))
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
        main = next(c for c in cards if c["role"] == "main" and c["prompt"] == meaning_question("Thank you"))
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
        main = next(c for c in cards if c["role"] == "main" and c["prompt"] == meaning_question("Thank you"))
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
        main = next(c for c in cards if c["role"] == "main" and c["prompt"] == meaning_question("Thank you"))
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


class FakeResponse:
    """Minimal stand-in for the object urllib.request.urlopen() returns —
    just enough to support `with urlopen(...) as resp: resp.read()`."""

    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


class DeckCoverImageGenerationTest(unittest.TestCase):
    """--generate-images support. Never hits the real FLUX server (slow,
    needs a local GPU service running) — urllib.request.urlopen is mocked
    throughout, matching a real server's request/response shape."""

    def test_deck_cover_prompt_names_the_deck_and_asks_for_no_text(self):
        prompt = deck_cover_prompt("At the Airport")
        self.assertIn("at the airport", prompt.lower())
        self.assertIn("no text", prompt.lower())
        # Regression: quoting the deck title verbatim as if it were a
        # caption/poster headline led FLUX to actually render it (often
        # garbled) despite the "no text" instruction — see this function's
        # own doc comment. Steer clear of scene types that invite signage.
        self.assertIn("signage", prompt.lower())
        self.assertNotIn('"At the Airport"', prompt)

    def test_generate_deck_cover_raises_an_actionable_error_when_server_is_down(self):
        with patch("generate_language_course.urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(RuntimeError) as ctx:
                    generate_deck_cover("Greetings", Path(tmp) / "deck1.png")
                self.assertIn("start_servers.ps1", str(ctx.exception))

    def test_generate_deck_cover_writes_the_file_when_server_is_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "deck1.png"

            def fake_urlopen(req, timeout=None):
                url = req if isinstance(req, str) else req.full_url
                if "health" in url:
                    return FakeResponse({"status": "ok", "model_loaded": True})
                # Simulate the real server actually writing the file.
                output_path.write_bytes(b"fake-png-bytes")
                return FakeResponse({"output_path": str(output_path), "width": 256, "height": 256})

            with patch("generate_language_course.urllib.request.urlopen", side_effect=fake_urlopen):
                generate_deck_cover("Greetings", output_path)
            self.assertTrue(output_path.exists())

    def test_generate_deck_covers_skips_decks_whose_image_already_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            images_dir = Path(tmp)
            (images_dir / "deck1.png").write_bytes(b"already-there")
            generated_for: list[str] = []

            def fake_urlopen(req, timeout=None):
                url = req if isinstance(req, str) else req.full_url
                if "health" in url:
                    return FakeResponse({"status": "ok", "model_loaded": True})
                body = json.loads(req.data.decode("utf-8"))
                generated_for.append(body["prompt"])
                Path(body["output_path"]).write_bytes(b"fake-png-bytes")
                return FakeResponse({"output_path": body["output_path"]})

            with patch("generate_language_course.urllib.request.urlopen", side_effect=fake_urlopen):
                result = generate_deck_covers(["Greetings", "Numbers"], images_dir)

            self.assertEqual(result, {"Greetings": "deck1.png", "Numbers": "deck2.png"})
            # Only "Numbers" actually triggered a generate call — "Greetings"
            # already had a file on disk.
            self.assertEqual(len(generated_for), 1)
            self.assertIn("numbers", generated_for[0].lower())
            self.assertTrue((images_dir / "deck2.png").exists())


if __name__ == "__main__":
    unittest.main()
