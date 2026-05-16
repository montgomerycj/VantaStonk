from src.signals.ticker_validator import validate_tickers

class FakeClient:
    def __init__(self, valid_symbols):
        self._valid = set(valid_symbols)
    def has_quote(self, symbol):
        return symbol in self._valid

def test_filters_invalid():
    client = FakeClient({"AAPL", "XYZ"})
    candidates = ["AAPL", "XYZ", "FAKE123", "BLZR"]
    valid, rejected = validate_tickers(candidates, client)
    assert valid == ["AAPL", "XYZ"]
    assert set(rejected) == {"FAKE123", "BLZR"}

def test_dedup():
    client = FakeClient({"AAPL"})
    valid, _ = validate_tickers(["AAPL", "AAPL", "aapl"], client)
    assert valid == ["AAPL"]  # dedup + normalize case
