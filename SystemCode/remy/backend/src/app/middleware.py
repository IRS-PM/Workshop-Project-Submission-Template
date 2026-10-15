from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.tokens import TokenConfig, TokenError, username_of

# Reachable without a token. Everything else needs one.
PUBLIC_PATHS = frozenset(
    {
        "/health",
        "/auth/signup",
        "/auth/signin",
        # Refresh reads the token itself, including expired ones, so it has to
        # sit outside a check that rejects expired tokens.
        "/auth/refresh",
        "/auth/available",
        "/auth/logout",
        "/docs",
        "/redoc",
        "/openapi.json",
    }
)


def _is_public(path: str) -> bool:
    return path in PUBLIC_PATHS


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """Requires a valid, unexpired bearer token on every non-public route.

    On success the subject is left at `request.state.username` so handlers do
    not have to decode the token a second time.
    """

    def __init__(self, app, config: TokenConfig, cookie_name: str) -> None:
        super().__init__(app)
        self._config = config
        self._cookie_name = cookie_name

    async def dispatch(self, request: Request, call_next):
        # CORS preflight carries no Authorization header by design; CORSMiddleware
        # answers it before this runs, but allowing it here keeps the middleware
        # correct regardless of ordering.
        if request.method == "OPTIONS" or _is_public(request.url.path):
            return await call_next(request)

        token = read_token(request, self._cookie_name)
        if not token:
            return _unauthorized("Missing credentials.")

        try:
            request.state.username = username_of(token, self._config)
        except TokenError as error:
            return _unauthorized(str(error))

        return await call_next(request)


def read_token(request: Request, cookie_name: str) -> str | None:
    """The HttpOnly cookie is where browsers keep it; the Authorization header
    stays supported for curl, tests and any non-browser client."""
    cookie = request.cookies.get(cookie_name)
    if cookie:
        return cookie

    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    return token if scheme.lower() == "bearer" and token else None


def _unauthorized(detail: str) -> JSONResponse:
    return JSONResponse(
        {"detail": detail},
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
    )
