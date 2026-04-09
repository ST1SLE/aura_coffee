## auth-ui

### MODIFIED: Root route protection
- **Previously:** `/` (HomePage) is a public route outside `ProtectedRoute`
- **Now:** `/` is wrapped in `ProtectedRoute`, unauthenticated users redirected to `/login`
- **File:** `web/customer/src/App.tsx`
