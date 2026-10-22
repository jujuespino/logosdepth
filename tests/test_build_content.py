"""Unit tests for the pure helpers in scripts/build_content.py (no external datasets needed)."""
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_content as bc  # noqa: E402


def test_kjv_keys_single_range_and_psalm_naming():
    assert bc.kjv_keys("John 3:16") == ["John 3:16"]
    assert bc.kjv_keys("Psalm 23:1") == ["Psalms 23:1"]
    assert bc.kjv_keys("Ephesians 2:8-9") == ["Ephesians 2:8", "Ephesians 2:9"]
    assert bc.kjv_keys("1 John 4:19") == ["1 John 4:19"]


def test_word_ids_normalizes_padded_hebrew_and_missing_strongs_array():
    assert bc.word_ids({"lemma": "strong:H07225", "strongs": ["H7225"]}) == {"H7225"}
    assert bc.word_ids({"lemma": "strong:H0853 strong:H01254"}) == {"H853", "H1254"}
    # Greek words sometimes lack the clean array (John 3:16 "loved")
    assert bc.word_ids({"lemma": "strong:G25 lemma.TR:ηγαπησεν"}) == {"G25"}
    assert bc.word_ids({"lemma": None}) == set()


def test_is_content_keeps_nouns_verbs_adjectives_names_only():
    assert bc.is_content({"gloss": "to love", "morphology": "G:V"})
    assert bc.is_content({"gloss": "world", "morphology": "G:N-M"})
    assert bc.is_content({"gloss": "holy", "morphology": "G:A-NSM"})
    assert bc.is_content({"gloss": "Jesus", "morphology": "N:N-M"})
    assert not bc.is_content({"gloss": "and", "morphology": "G:CONJ"})
    assert not bc.is_content({"gloss": "in", "morphology": "G:PREP"})
    assert not bc.is_content({"gloss": "he", "morphology": "G:P-NSM"})
    assert not bc.is_content({"gloss": "", "morphology": "G:V"})


def test_step_lookup_prefers_single_word_lemma_over_place_names():
    h = {
        "H7462a": {"lemma": "בֵּית־עֵ֫קֶד הָרֹעִים", "gloss": "House of Shepherds"},
        "H7462b": {"lemma": "רָעָה", "gloss": "to pasture"},
        "H7462c": {"lemma": "רָעָה", "gloss": "to accompany"},
        "H1044": {"lemma": "בֵּית־עֵ֫קֶד", "gloss": "Beth-eked"},
    }
    assert bc.step_lookup("H7462", {}, h)["gloss"] == "to pasture"
    assert bc.step_lookup("H1044", {}, h)["gloss"] == "Beth-eked"
    assert bc.step_lookup("H9999", {}, h) is None


def test_rendering_list_drops_stopwords_and_rare_words():
    c = collections.Counter({"love": 60, "loved": 40, "the": 90, "of": 80, "loveth": 1, "ye": 30})
    assert bc.rendering_list(c) == ["love", "loved"]


def test_superscription_detection():
    assert bc.SUPERSCRIPTION.match("A Psalm by David. The LORD is my shepherd")
    assert bc.SUPERSCRIPTION.match("For the Chief Musician. By the sons of Korah.")
    assert bc.SUPERSCRIPTION.match("By David. Bless the LORD, my soul")
    assert not bc.SUPERSCRIPTION.match("The LORD is my shepherd; I shall lack nothing.")
    assert not bc.SUPERSCRIPTION.match("For God so loved the world")


def test_clean_kjv_removes_paragraph_and_italic_marks():
    assert bc.clean_kjv("# And darkness [was] upon  the face") == "And darkness was upon the face"
