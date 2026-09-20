# ==============================
# IMPORT REQUIRED LIBRARIES
# ==============================

import os
# datetime helps us set token expiry time
# timezone makes the time correct for all countries
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext


# ==============================
# LOAD ENVIRONMENT VARIABLES
# ==============================

# Loads values from the .env file
load_dotenv()

# Secret key to sign tokens. Comes from .env file.
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")

# Signing method. Comes from .env file.
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# How many minutes login lasts. Comes from .env file.
TOKEN_VALID_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))


# ==============================
# PASSWORD HASHING SETUP
# ==============================

# CryptContext manages password hashing.
# bcrypt is used because it is slow by design,
# making brute-force attacks much harder.
password_hasher = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


# ==============================
# FUNCTION 1: HASH A PASSWORD
# ==============================

def make_password_hash(plain_password: str) -> str:
    """
    Converts a plain-text password into a secure bcrypt hash.

    The original password is never stored in the database.
    Only the generated hash is saved.

    Args:
        plain_password (str): User's original password.

    Returns:
        str: Secure bcrypt hash.
    """
    return password_hasher.hash(plain_password)


# ==============================
# FUNCTION 2: VERIFY PASSWORD
# ==============================

def check_password_match(plain_password: str, stored_hash: str) -> bool:
    """
    Checks whether the entered password matches
    the stored bcrypt hash.

    Args:
        plain_password (str): Password entered by the user.
        stored_hash (str): Password hash stored in the database.

    Returns:
        bool: True if the password is correct,
              False otherwise.
    """
    return password_hasher.verify(plain_password, stored_hash)


# ==============================
# FUNCTION 3: CREATE LOGIN TOKEN
# ==============================

# Make a login token for one user
def create_login_token(user_id: int) -> str:
    # Token holds user id and expiry time
    payload = {
        # Save user id as text
        "sub": str(user_id),
        # Expiry = now + minutes from settings
        "exp": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_VALID_MINUTES)
    }

    token = jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=ALGORITHM
    )

    return token


# ==============================
# FUNCTION 4: READ USER ID
# FROM JWT TOKEN
# ==============================

def get_user_id_from_token(token: str) -> int | None:
    """
    Verifies a JWT token and extracts the user ID.

    If the token is invalid, expired,
    or has been modified,
    None is returned.

    Args:
        token (str): JWT token.

    Returns:
        int | None: User ID if valid,
                    otherwise None.
    """

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[ALGORITHM]
        )

        user_id = int(payload.get("sub"))
        return user_id

    except JWTError:
        return None


# ==============================
# TEST THE FUNCTIONS
# ==============================

if __name__ == "__main__":

    print("\n===== PASSWORD TEST =====")

    hashed = make_password_hash("mypassword123")

    print("Hashed Password:", hashed)
    print("Correct Password:",
          check_password_match("mypassword123", hashed))
    print("Wrong Password:",
          check_password_match("wrongpassword", hashed))

    print("\n===== JWT TOKEN TEST =====")

    token = create_login_token(user_id=1)

    print("Generated Token:", token)
    print("User ID From Token:",
          get_user_id_from_token(token))