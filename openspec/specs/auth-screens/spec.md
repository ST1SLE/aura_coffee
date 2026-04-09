## ADDED Requirements

### Requirement: Phone input screen
The system SHALL display a phone input screen at `/login` with a phone number field (fixed `+7` prefix, mask `(XXX) XXX-XX-XX`), a submit button, and bilingual labels (RU/EN via i18n). The phone field SHALL accept exactly 10 digits after the prefix. The submit button SHALL be disabled until a valid phone number is entered.

#### Scenario: Valid phone number submission
- **WHEN** user enters a valid 10-digit phone number and clicks submit
- **THEN** the system sends a `send-code` request with the phone normalized to E.164 format (`+7XXXXXXXXXX`) and navigates to the OTP verification screen

#### Scenario: Invalid phone number
- **WHEN** user enters fewer than 10 digits
- **THEN** the submit button remains disabled

#### Scenario: API error on send-code
- **WHEN** user submits a valid phone and the API returns an error (rate-limit exceeded, server error)
- **THEN** an error message is displayed on the same screen without navigation

### Requirement: OTP verification screen
The system SHALL display an OTP verification screen at `/login/verify` with 6 separate digit input fields, a countdown timer (60s), a "Resend code" button, and the masked phone number. Each input field SHALL accept one digit and auto-advance focus to the next field on input.

#### Scenario: Correct OTP code
- **WHEN** user enters all 6 digits and the code is correct
- **THEN** the system stores the received tokens, sets the user as authenticated, and redirects to the return URL (or `/` if none)

#### Scenario: Incorrect OTP code
- **WHEN** user enters all 6 digits and the code is incorrect
- **THEN** an error message "Неверный код" / "Invalid code" is displayed, input fields are cleared, and focus returns to the first field

#### Scenario: Auto-submit on complete input
- **WHEN** user fills the 6th digit
- **THEN** the verification request is sent automatically without requiring a separate submit button click

#### Scenario: Backspace navigation
- **WHEN** user presses Backspace on an empty digit field
- **THEN** focus moves to the previous field and clears its value

#### Scenario: Paste OTP code
- **WHEN** user pastes a 6-digit string into any input field
- **THEN** all 6 fields are filled with the pasted digits and verification is triggered

### Requirement: Resend OTP timer
The system SHALL display a countdown timer starting at 60 seconds after a code is sent. The "Resend code" button SHALL be disabled during the countdown and enabled when the timer reaches zero. Clicking "Resend" SHALL restart the timer and call `send-code` again.

#### Scenario: Timer countdown
- **WHEN** code is sent successfully
- **THEN** a timer displays remaining seconds (e.g., "Отправить повторно через 45с") and the resend button is disabled

#### Scenario: Resend after timer expires
- **WHEN** the 60-second timer reaches zero and user clicks "Resend code"
- **THEN** a new `send-code` request is sent, timer restarts at 60 seconds

### Requirement: Loading states
The system SHALL display a loading indicator (spinner or disabled button with loading text) during API calls on both phone input and OTP verification screens. Form inputs SHALL be disabled during loading to prevent duplicate submissions.

#### Scenario: Loading during send-code
- **WHEN** user submits phone number
- **THEN** the submit button shows a loading state and inputs are disabled until the API responds

#### Scenario: Loading during verify-code
- **WHEN** OTP auto-submits
- **THEN** all digit inputs are disabled and a loading indicator is shown until the API responds

### Requirement: Bilingual auth screens
All text on auth screens SHALL support RU and EN via react-i18next. Translation keys SHALL be namespaced under `auth` (e.g., `auth.phone.title`, `auth.otp.resend`).

#### Scenario: Language switch on login page
- **WHEN** user switches language via the language switcher
- **THEN** all labels, placeholders, error messages, and button text on auth screens update to the selected language
