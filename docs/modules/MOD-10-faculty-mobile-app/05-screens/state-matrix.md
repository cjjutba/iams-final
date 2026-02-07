# UI State Matrix

| State | Schedule/Home Screens | Live/Class Screens | Manual Entry Screen | Profile Screens | Notifications Screen |
|---|---|---|---|---|---|
| Initial loading | Show schedule/home skeleton | Show roster/detail skeleton | Show form loading state | Show profile skeleton | Show feed skeleton |
| Data loaded | Render classes and active indicator | Render roster/summary/alerts | Enable submit with valid inputs | Render profile fields | Render event feed |
| Empty state | Show no-classes message | Show inactive-session or no-alerts message | Show no-edit-needed guidance | Show empty profile placeholders | Show no-notifications message |
| Validation error | N/A | N/A | Field-level errors + block submit | Field-level errors | Parse-safe event fallback |
| API error | Retry and preserve filter/context | Retry and preserve selected class | Show error, keep draft values | Retry and preserve edits | Reconnect/retry indicator |
| Unauthorized | Route to login | Route to login | Route to login | Route to login | Route to login/reconnect |
| Offline/transient loss | Show cached data if available | Show reconnecting status | Keep local draft until network restore | Keep editable local state | Show reconnecting status |
