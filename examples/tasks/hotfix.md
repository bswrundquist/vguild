# Hotfix Task: NullPointerException in Authentication

## Summary

Production users are receiving a `500 Internal Server Error` when logging in with certain
email addresses that contain uppercase characters. The error is a `NullPointerException`
in the authentication service.

## Symptoms

- Error rate: ~2% of login attempts
- First seen: after last week's deploy of the email normalisation feature
- Affected endpoint: `POST /api/v1/auth/login`
- Error message in logs: `NullPointerException at auth.UserRepository.findByEmail(line 87)`

## Reproduction Steps

1. Create a user with email `User@Example.com`
2. Attempt login with `user@example.com` (lowercase)
3. Observe 500 error

## Expected Behaviour

Login should succeed regardless of email case; normalisation should happen before the
database lookup.

## Context

- Service: `auth-service` in `src/auth/`
- Repository: `src/auth/user_repository.py`
- Last changed by: email normalisation PR #312 (merged 2024-01-15)

## Acceptance Criteria

- [ ] Login works for all email capitalisation variants
- [ ] Existing tests pass
- [ ] New test added covering mixed-case email login
- [ ] No performance regression
