"""Unit tests for the pure helpers in scripts/build_content.py (no external datasets needed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_content as bc  # noqa: E402


def test_kjv_keys_single_range_and_psalm_naming():
    assert bc.kjv_keys("John 3:16") == ["John 3:16"]
    assert bc.kjv_keys("Psalm 23:1") == ["Psalms 23:1"]
    assert bc.kjv_keys("Ephesians 2:8-9") == ["Ephesians 2:8", "Ephesians 2:9"]
    assert bc.kjv_keys("1 John 4:19") == ["1 John 4:19"]


def test_clean_kjv_removes_markers_and_extra_space():
    assert bc.clean_kjv("# In the beginning  [God] created") == "In the beginning God created"


def test_superscription_detection():
    assert bc.SUPERSCRIPTION.match("A Psalm by David. The LORD is my shepherd")
    assert bc.SUPERSCRIPTION.match("For the Chief Musician. By the sons of Korah.")
    assert bc.SUPERSCRIPTION.match("By David. Bless the LORD, my soul")
    assert not bc.SUPERSCRIPTION.match("The LORD is my shepherd; I shall lack nothing.")
    assert not bc.SUPERSCRIPTION.match("For God so loved the world")
