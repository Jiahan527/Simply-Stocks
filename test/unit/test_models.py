from datetime import datetime
from models import Portfolio


def test_portfolio_creation():
    entry = Portfolio(
        user_id=1,
        ticker="AAPL",
        quantity=10,
        added_at=datetime.utcnow()
    )

    assert entry.ticker == "AAPL"
    assert entry.quantity == 10
    assert isinstance(entry.added_at, datetime)