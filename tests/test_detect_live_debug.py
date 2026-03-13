from app.heuristics import detect_live_debug

def test_detect_live_debug_english():
    assert detect_live_debug("Can you help me debug this error?") is True
    assert detect_live_debug("Here is the traceback for the error") is True
    assert detect_live_debug("why is this failing") is True
    assert detect_live_debug("fix this error") is True
    assert detect_live_debug("How to create an mre?") is True
    assert detect_live_debug("Can you reproduce this issue?") is True
    assert detect_live_debug("I have an exception here") is True

def test_detect_live_debug_turkish():
    assert detect_live_debug("Lütfen hata ayıklama yap") is True
    assert detect_live_debug("canlı debug nasıl yapılır?") is True
    assert detect_live_debug("yığın izi nedir?") is True
    assert detect_live_debug("istisna fırlatıldı") is True

def test_detect_live_debug_regex():
    # logs? regex match
    assert detect_live_debug("Where is the log file?") is True
    assert detect_live_debug("Show the error logs") is True
    assert detect_live_debug("Here is the error log for the server") is True

def test_detect_live_debug_false():
    assert detect_live_debug("How do I write a Python function?") is False
    assert detect_live_debug("Explain quantum physics") is False
    assert detect_live_debug("Can we create a new website?") is False
    assert detect_live_debug("") is False

def test_detect_live_debug_case_insensitive():
    assert detect_live_debug("TRACEBACK") is True
    assert detect_live_debug("ExCePtIoN") is True
    assert detect_live_debug("StAcK TrAcE") is True
