"""
Auth Router — cv-agent backend

Handles all authentication endpoints:
    POST /auth/register  — create new user account
    POST /auth/login     — authenticate and set session cookie
    POST /auth/logout    — invalidate session and clear cookie
    GET  /auth/me        — get current authenticated user profile

All routes delegate credential validation to Supabase Auth.
JWT tokens are stored exclusively in httpOnly cookies — never in
localStorage or response bodies.
"""