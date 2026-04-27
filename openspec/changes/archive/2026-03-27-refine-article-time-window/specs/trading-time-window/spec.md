## ADDED Requirements

### Requirement: Calculate next trading date
The system SHALL provide a method to find the next trading date after a given date, skipping weekends and Chinese holidays.

#### Scenario: Find next trading date from weekday
- **WHEN** given a Monday (trading day)
- **THEN** system returns Tuesday as the next trading date

#### Scenario: Find next trading date from weekend
- **WHEN** given a Friday
- **THEN** system returns the following Monday as the next trading date

#### Scenario: Find next trading date skipping holiday
- **WHEN** given a day before a Chinese holiday (e.g., National Day)
- **THEN** system returns the first trading day after the holiday period

### Requirement: Calculate article time window
The system SHALL provide a method to calculate the precise time window for filtering articles related to a trading day.

#### Scenario: Standard trading day time window
- **WHEN** given a trading day T
- **THEN** system returns time window from T 15:00:00 to next_trading_day 09:15:00

#### Scenario: Friday to Monday time window
- **WHEN** given Friday as trading day
- **THEN** system returns time window from Friday 15:00:00 to Monday 09:15:00

#### Scenario: Pre-holiday time window
- **WHEN** given a trading day before a holiday period
- **THEN** system returns time window ending at the first trading day after the holiday

### Requirement: Use chinese_calendar for holiday detection
The system SHALL use the `chinese_calendar` library to determine workdays and holidays.

#### Scenario: Detect Chinese New Year as non-trading day
- **WHEN** checking a date during Chinese New Year period
- **THEN** system correctly identifies it as a non-trading day

#### Scenario: Detect National Day as non-trading day
- **WHEN** checking October 1-7
- **THEN** system correctly identifies these as non-trading days
