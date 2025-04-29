import pytest
from app import create_app, db
from models import User


@pytest.fixture
def client():
    app = create_app()
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False
    })

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        db.drop_all()


def test_user_registration(client):
    response = client.post('/register', data={
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'SecurePass123'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'<title>Login</title>' in response.data
    assert b'Registration successful' in response.data
    with client.application.app_context():
        user = User.query.filter_by(username='testuser').first()
        assert user is not None
        assert user.email == 'test@example.com'