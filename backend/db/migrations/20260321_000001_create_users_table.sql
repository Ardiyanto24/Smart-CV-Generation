-- Migration: Create users table
-- Cluster 1 — Master Data
-- Root anchor for all user-owned data in the system.

CREATE TABLE IF NOT EXISTS public.users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    email       VARCHAR(255) NOT NULL UNIQUE,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE public.users IS 'User profile data. Linked to auth.users via same UUID.';