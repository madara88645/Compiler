"""Sentence splitting must not mangle coherent requests.

Regression for the input-mangling defect: the splitter used `[\\n;.]+`, so it
broke a single coherent request on every semicolon and every period — turning
'…does nothing on Safari; works on Chrome.' into two fragments, and splitting
dotted tokens like 'Node.js' / 'v2.0'. It should split on newlines and real
sentence boundaries (.!? followed by whitespace) only.
"""

from app.compiler import split_sentences, extract_goals_tasks


def test_semicolon_does_not_split():
    parts = split_sentences("export button does nothing on Safari; works on Chrome")
    assert len(parts) == 1
    assert "works on Chrome" in parts[0]


def test_dotted_tokens_stay_intact():
    parts = split_sentences("Deploy the Node.js app version v2.0 to production")
    assert len(parts) == 1
    joined = " ".join(parts)
    assert "Node.js" in joined
    assert "v2.0" in joined


def test_real_sentences_still_split():
    parts = split_sentences("Set up the database. Then seed it with test data.")
    assert len(parts) == 2


def test_newlines_still_split():
    assert len(split_sentences("First task\nSecond task")) == 2


def test_safari_issue_does_not_fragment():
    goals, tasks = extract_goals_tasks(
        "Turn this GitHub issue into a safe implementation brief: "
        '"export button does nothing on Safari; works on Chrome."',
        "en",
    )
    # the coherent request must not split off a bare "works on Chrome" task
    assert not any(g.strip().lower().startswith("works on chrome") for g in goals)
    assert not any(t.strip().lower().startswith("works on chrome") for t in tasks)
