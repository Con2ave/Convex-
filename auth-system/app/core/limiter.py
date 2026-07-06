from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared Rate Limiter instance based on Client IP Address
limiter = Limiter(key_func=get_remote_address)
