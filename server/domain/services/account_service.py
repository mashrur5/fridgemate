"""UC16 accounts: register, log in, log out, change password, and load the request context.

Replaces Auth0 (see docs/design-changes.md #8). Passwords are stored only as salted PBKDF2 hashes."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta
from typing import Callable, Optional

from server.domain.errors import InvalidOperationError, PermissionDeniedError
from server.domain.model import Household, Member
from server.infrastructure.persistence import AccountRepository, HouseholdRepository, MemberRepository

SESSION_DAYS = 7
MIN_PASSWORD = 8
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthError(PermissionDeniedError):
    """Wrong login or expired session. The message never says which part was wrong."""


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()


class AccountService:
    def __init__(self, accounts: AccountRepository, members: MemberRepository, households: HouseholdRepository,
                 now: Callable[[], datetime] = datetime.now) -> None:
        self.accounts = accounts
        self.members = members
        self.households = households
        self._now = now

    def register(self, email: str, password: str, name: str) -> Member:
        email = email.strip().lower()
        if not _EMAIL.match(email):
            raise ValueError("please enter a valid email")
        if len(password) < MIN_PASSWORD:
            raise ValueError(f"password must be at least {MIN_PASSWORD} characters")
        if not name.strip():
            raise ValueError("name cannot be empty")
        if self.accounts.find_credentials(email) is not None:
            raise InvalidOperationError("this email is already registered, please log in")
        salt = secrets.token_hex(16)
        self.accounts.save_credentials(email, _hash(password, salt), salt)
        member = Member(account_id=email, name=name.strip(), email=email)
        self.members.save(member)
        return member

    def login(self, email: str, password: str) -> str:
        email = email.strip().lower()
        creds = self.accounts.find_credentials(email)
        if creds is None or not hmac.compare_digest(creds[0], _hash(password, creds[1])):
            raise AuthError("wrong email or password")
        token = secrets.token_urlsafe(32)
        self.accounts.save_session(token, email, self._now() + timedelta(days=SESSION_DAYS))
        return token

    def logout(self, token: str) -> None:
        self.accounts.delete_session(token)

    def change_password(self, member: Member, old_password: str, new_password: str) -> None:
        creds = self.accounts.find_credentials(member.account_id)
        if creds is None or not hmac.compare_digest(creds[0], _hash(old_password, creds[1])):
            raise AuthError("current password is wrong")
        if len(new_password) < MIN_PASSWORD:
            raise ValueError(f"password must be at least {MIN_PASSWORD} characters")
        salt = secrets.token_hex(16)
        self.accounts.save_credentials(member.account_id, _hash(new_password, salt), salt)

    def load_context(self, token: str) -> tuple[Member, Optional[Household]]:
        """Who owns this token. Raises AuthError when the session is unknown or expired."""
        session = self.accounts.find_session(token)
        if session is None:
            raise AuthError("please log in")
        account_id, expires_at = session
        if expires_at < self._now():
            self.accounts.delete_session(token)
            raise AuthError("your session expired, please log in again")
        member = self.members.find_by_account(account_id)
        if member is None:
            raise AuthError("please log in")
        household = self.households.find_by_id(member.household_id) if member.household_id else None
        return member, household
