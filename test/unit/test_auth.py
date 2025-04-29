from werkzeug.security import check_password_hash
from models import User


def test_password_hashing():
    user = User()
    user.set_password("secure_password123")
    assert user.check_password("secure_password123") is True
    assert user.check_password("wrong_password") is False
    assert len(user.password_hash) <= 256