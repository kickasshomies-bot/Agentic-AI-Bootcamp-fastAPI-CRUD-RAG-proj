# pip install fastapi uvicorn requests pyjwt cryptography

import requests
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt
from jwt import PyJWKClient

app = FastAPI(title="Supabase JWT Auth Demo")

# ── Supabase project config ──────────────────────────────────────────
SUPABASE_URL = "https://nebbedzehvrobugqisju.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_vaLyuBx0wsgZy3snbrx-pQ_2AbTNn_7"
JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
SUPABASE_AUDIENCE = "authenticated"

# Fetches + caches Supabase's public signing keys automatically
jwks_client = PyJWKClient(JWKS_URL)

bearer_scheme = HTTPBearer()


# Request/response models 
class AuthRequest(BaseModel):
    email: str
    password: str


#  Step 1: Signup — proxies to Supabase Auth 
@app.post("/signup")
def signup(payload: AuthRequest):
    url = f"{SUPABASE_URL}/auth/v1/signup"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
    }
    response = requests.post(
        url, headers=headers, json={"email": payload.email, "password": payload.password}
    )
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())
    return response.json()


# Step 2: Login — proxies to Supabase Auth, returns the JWT 
@app.post("/login")
def login(payload: AuthRequest):
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
    }
    response = requests.post(
        url, headers=headers, json={"email": payload.email, "password": payload.password}
    )
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())
    data = response.json()
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "token_type": data["token_type"],
        "expires_in": data["expires_in"],
    }


#  Step 3: Dependency that verifies the Supabase-issued JWT 
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = credentials.credentials
    try:
        # Looks at the token's "kid" header, fetches the matching public key from Supabase's JWKS
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],  # pin accepted algorithms
            audience=SUPABASE_AUDIENCE,
        )
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {e}")
    return payload


# Step 4: Protected route 
@app.get("/me")
def read_profile(user: dict = Depends(get_current_user)):
    return {
        "user_id": user["sub"],
        "email": user.get("email"),
        "role": user.get("role"),
        "issued_at": user.get("iat"),
        "expires_at": user.get("exp"),
    }


#  Public route, for comparison 
@app.get("/")
def root():
    return {"message": "This route is public — no token required."}