# UI State Matrix

| State | Registration Screens | Attendance/Schedule Screens | Profile Screens | Notifications Screen |
|---|---|---|---|---|
| Initial loading | Step skeleton/loading indicator | Skeleton/list loader | Profile skeleton | Feed skeleton |
| Valid data loaded | Enable continue action | Render lists/cards/details | Render profile fields | Render notification feed |
| Empty state | N/A or initial form state | Show empty message and CTA | Show empty placeholders | Show no-notifications message |
| Validation error | Field errors + block next step | Filter/input errors | Field-level errors | Parse-safe fallback |
| API error | Retry + keep draft values | Retry and preserve filters | Retry + preserve unsaved edits | Reconnect/retry indicator |
| Unauthorized | Route to login | Route to login | Route to login | Reconnect or route to login |
| Offline/transient loss | Save draft locally | Show cached data if available | Keep editable local state | Show reconnecting status |
