"""
Debug Clerk JWT verification
"""
import jwt as pyjwt
from jwt import PyJWKClient
import httpx

CLERK_JWKS_URL = "https://popular-spaniel-5660.clerk.accounts.dev/.well-known/jwks.json"
test_token = "eyJhbGciOiJSUzI1NiIsImNhdCI6ImNsX0I3ZDRQRDExMUFBQSIsImtpZCI6Imluc18zSTMwVmdRYTRYeEpCeXBaZ2NrME1yV09UUmIiLCJvaWF0IjoxNzg2OTgwNjc0LCJ0eXAiOiJKV1QifQ.eyJleHAiOjE3ODY5ODA3MzQsImZ2YSI6Wzk5OTk5LC0xXSwiaWF0IjoxNzg2OTgwNjc0LCJpc3MiOiJodHRwczovL3BvcHVsYXItc3BhbmllbC01NjYwLmNsZXJrLmFjY291bnRzLmRldiIsIm5iZiI6MTc4Njk4MDY2NCwic2lkIjoic2Vzc18zSTM1eldyZmVzc1B1a2NSSWxFWldacHZEUkgiLCJzdHMiOiJhY3RpdmUiLCJzdWIiOiJ1c2VyXzNJMzV6SUJ2WDVnSEd1cnIySmp4VktaVlNWOCIsInYiOjJ9.ruQIQjNACZs81OjalpwnLNRmDafh_CUV6yJoQMniKR_GH5u0yFe7TLEgHGslRz0jdZVBe6HnxuruBLMOG0wvvJcVAcDneesSdKA8GQ3eO7xijpCTOv8nYh3FIX5IBmhLHbZ2GUOrME81LSMnU-54TOKTSxLP2dBZrTwgxKtS-36ZirHYHYAg2f0PsFL-3KTjLttHY8K-dxypmg2jzZLckv_qyZgIzSg_8ErKhdd-0HIwsLw-D978s7PtV1G44ynEHAvCvEwa1J-pgyjPRL7ZkHIyDxn_yTYbwylMs1IvVN_WT4Wr3ug74el9iX6i_S_tcdm4fx7fHnXfRBvFyN8Frg"

print("Testing Clerk JWT verification...")
print(f"JWKS URL: {CLERK_JWKS_URL}")

try:
    # First, let's decode without verification to see the structure
    decoded_no_verify = pyjwt.decode(test_token, options={"verify_signature": False})
    print(f"Decoded without verification: {decoded_no_verify}")

    # Now try with JWKS verification
    jwks_client = PyJWKClient(CLERK_JWKS_URL)
    print("JWKS client created successfully")

    signing_key = jwks_client.get_signing_key_from_jwt(test_token)
    print(f"Signing key found: {signing_key.key}")

    payload = pyjwt.decode(
        test_token,
        signing_key.key,
        algorithms=["RS256", "ES256"],
        options={"verify_aud": False, "verify_exp": False},  # Disable exp check for testing
    )
    print(f"SUCCESS: JWT verified successfully: {payload}")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
