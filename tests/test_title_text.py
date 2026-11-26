"""Unit tests for sedna_options._title_text: metadata-api v2's langString titles."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # noqa: E402
import sedna_options  # noqa: E402


def test_prefers_french():
    assert sedna_options._title_text({"en": "Code Beluga", "fr": "Projet code Béluga"}) == "Projet code Béluga"


def test_falls_back_to_english_without_french():
    assert sedna_options._title_text({"en": "Code Beluga"}) == "Code Beluga"


def test_falls_back_to_any_language_left():
    assert sedna_options._title_text({"es": "Proyecto Beluga"}) == "Proyecto Beluga"


def test_empty_dict_is_empty_string():
    assert sedna_options._title_text({}) == ""


def test_non_dict_passes_through():
    assert sedna_options._title_text("plain title") == "plain title"
    assert sedna_options._title_text(None) == ""
