# Test password hashing and login tokens
from src.auth import make_password_hash, check_password_match, create_login_token, get_user_id_from_token

# Check hashing works
def test_password_hash():
    # Make a hash from plain text
    h = make_password_hash("hello123")
    # Correct password should pass
    assert check_password_match("hello123", h) is True
    # Wrong password should fail
    assert check_password_match("wrong", h) is False

# Check token keeps user id
def test_login_token():
    # Make token for user 5
    token = create_login_token(5)
    # Reading it back should give 5
    assert get_user_id_from_token(token) == 5

# Check bad token gives None
def test_bad_token():
    # Broken token should not crash, just give None
    assert get_user_id_from_token("bad.token.here") is None
