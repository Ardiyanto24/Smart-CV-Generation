from slowapi import Limiter
from slowapi.util import get_remote_address

# ── Rate Limiter Singleton ────────────────────────────────────────────────────
# Uses IP address as the key function — works for both authenticated
# and unauthenticated requests.
#
# Usage in any router:
#   from db.limiter import limiter
#
#   @router.post("/endpoint")
#   @limiter.limit("5/hour")
#   async def endpoint(request: Request):
#       ...
#
# Note: The `request: Request` parameter is required in the route handler
# when using slowapi — slowapi reads it to extract the client IP.

limiter = Limiter(key_func=get_remote_address)