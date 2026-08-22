from app.security import decrypt_secret, encrypt_secret, hash_password, token_hash, verify_password


def test_passwords_use_argon2_and_verify() -> None:
    hashed = hash_password("a-long-and-safe-test-password")
    assert hashed.startswith("$argon2id$")
    assert verify_password(hashed, "a-long-and-safe-test-password")
    assert not verify_password(hashed, "wrong-password")


def test_encrypted_secret_round_trip_is_not_plaintext() -> None:
    plaintext = "unique-rcon-password"
    encrypted = encrypt_secret(plaintext)
    assert plaintext not in encrypted
    assert decrypt_secret(encrypted) == plaintext


def test_token_hash_is_deterministic_without_storing_token() -> None:
    value = "session-value"
    assert token_hash(value) == token_hash(value)
    assert value not in token_hash(value)
