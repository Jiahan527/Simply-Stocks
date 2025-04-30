from models import Portfolio


def test_add_stock_to_portfolio(client):
    # 先登录
    client.post('/login', data={
        'username': 'testuser',
        'password': 'SecurePass123'
    })

    # 添加股票
    response = client.post('/add_to_portfolio', data={
        'ticker': 'GOOGL'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'GOOGL has been added' in response.data

    portfolio = Portfolio.query.filter_by(ticker='GOOGL').first()
    assert portfolio is not None