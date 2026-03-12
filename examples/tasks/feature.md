# New Feature: User Notification Preferences

## Summary

Users want to control which types of email notifications they receive. Currently all
notifications are sent to all users. We need a preferences page and backend support
for opting in/out of notification categories.

## Feature Description

### User-Facing

- New settings page: `/settings/notifications`
- Categories to toggle:
  - Product updates
  - Security alerts (cannot be disabled)
  - Weekly digest
  - Marketing emails
- Changes take effect immediately

### Technical Requirements

- New database table: `notification_preferences`
- API endpoint: `PATCH /api/v1/users/me/notification-preferences`
- Integrate with existing email dispatch pipeline (`src/notifications/`)
- Security alerts must always be sent (server-side enforcement)

## Architecture Notes

- `src/users/` — user model lives here
- `src/notifications/dispatcher.py` — email dispatch
- `migrations/` — database migrations go here
- `src/api/users.py` — existing user API endpoints

## Acceptance Criteria

- [ ] User can toggle notification categories via the API
- [ ] Security alerts cannot be disabled
- [ ] Preferences persist across sessions
- [ ] All existing notification tests pass
- [ ] New tests cover preferences CRUD and dispatch gating
- [ ] API documented in OpenAPI spec
- [ ] Migration is reversible

## Non-Goals

- SMS notifications (future work)
- Per-project notification settings (future work)
