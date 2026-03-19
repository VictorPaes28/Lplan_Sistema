import hashlib
import hmac


def validate_hmac_sha256(raw_body: bytes, expected_signature: str, secret: str) -> bool:
    if not expected_signature or not secret:
        return False
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, expected_signature)

