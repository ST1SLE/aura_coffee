## ADDED Requirements

### Requirement: Issue token pair
Tests SHALL verify that `AuthService.issue_tokens` returns a `TokenPair` with a valid JWT access token and a refresh token stored in Redis.

#### Scenario: Access token is decodable
- **WHEN** `issue_tokens(user_id, "customer")` is called
- **THEN** the returned `access_token` decodes to a payload with `sub == str(user_id)` and `role == "customer"`

#### Scenario: Refresh token exists in Redis
- **WHEN** `issue_tokens(user_id)` is called
- **THEN** Redis key `session:{refresh_token}` exists and contains JSON with `user_id`

### Requirement: Refresh token rotation
Tests SHALL verify that `AuthService.refresh_tokens` deletes the old token, issues a new pair, and the new pair is valid.

#### Scenario: Successful rotation
- **WHEN** a valid refresh token is passed to `refresh_tokens`
- **THEN** the old `session:{old_token}` key is deleted, a new `TokenPair` is returned, and `session:{new_refresh_token}` exists in Redis

#### Scenario: New access token contains same user_id
- **WHEN** rotation succeeds
- **THEN** the new access token's `sub` claim matches the original `user_id`

### Requirement: Double-use of rotated refresh token
Tests SHALL verify that using an already-rotated refresh token returns `None`.

#### Scenario: Reuse after rotation
- **WHEN** `refresh_tokens(old_token)` is called after the token has already been rotated
- **THEN** the result is `None`

### Requirement: Logout deletes session
Tests SHALL verify that `AuthService.logout` removes the refresh token from Redis and returns `True`.

#### Scenario: Successful logout
- **WHEN** `logout(refresh_token)` is called with a valid token
- **THEN** `session:{refresh_token}` is deleted from Redis and the method returns `True`

#### Scenario: Logout with invalid token
- **WHEN** `logout("nonexistent-token")` is called
- **THEN** the method returns `False`
