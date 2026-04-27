## ADDED Requirements

### Requirement: Cache market data after market close

The system SHALL cache market data (indices, volume, statistics, sectors, limit-up stocks) to local database when:
1. Data is successfully fetched from external APIs
2. Current time is after market close (15:00) on a trading day
3. OR the requested trade date is in the past

#### Scenario: Cache data after market close
- **WHEN** user requests market data for today at 16:00 (after 15:00)
- **AND** data is successfully fetched from APIs
- **THEN** system stores all data to local database
- **AND** returns the fetched data

#### Scenario: No cache during market hours
- **WHEN** user requests market data for today at 10:30 (before 15:00)
- **AND** data is successfully fetched from APIs
- **THEN** system does NOT store data to cache
- **AND** returns the fetched data

#### Scenario: Cache historical data
- **WHEN** user requests market data for a past trading date
- **AND** data is successfully fetched from APIs
- **THEN** system stores all data to local database

### Requirement: Return cached data when available

The system SHALL return cached data when querying market data for a trade date that already has cached records.

#### Scenario: Return cached data
- **WHEN** user requests market data for a trade date
- **AND** that trade date has cached data in database
- **THEN** system returns cached data without calling external APIs

#### Scenario: Fetch when no cache
- **WHEN** user requests market data for a trade date
- **AND** that trade date has NO cached data
- **THEN** system calls external APIs to fetch data

### Requirement: Force refresh cache

The system SHALL support force refresh to bypass cache and fetch fresh data from APIs.

#### Scenario: Force refresh with --force flag
- **WHEN** user requests market data with --force flag
- **THEN** system ignores any cached data
- **AND** calls external APIs to fetch fresh data
- **AND** updates cache if caching conditions are met

### Requirement: Store indices data

The system SHALL store index data in `market_indices` table with fields:
- trade_date (unique)
- sh_index_name, sh_index_price, sh_index_change
- sz_index_name, sz_index_price, sz_index_change
- cy_index_name, cy_index_price, cy_index_change
- fetch_time

#### Scenario: Store Shanghai index
- **WHEN** indices data is cached
- **THEN** Shanghai index (000001) data is stored with name, price, and change percentage

### Requirement: Store volume data

The system SHALL store trading volume data in `market_volume` table with fields:
- trade_date (unique)
- sh_volume (in 100M yuan)
- sz_volume (in 100M yuan)
- total_volume
- fetch_time

#### Scenario: Store volume data
- **WHEN** volume data is cached
- **THEN** Shanghai and Shenzhen volumes are stored in 100M yuan units

### Requirement: Store statistics data

The system SHALL store market statistics in `market_statistics` table with fields:
- trade_date (unique)
- up_count (rising stocks count)
- down_count (falling stocks count)
- flat_count (unchanged stocks count)
- fetch_time

#### Scenario: Store statistics
- **WHEN** statistics data is cached
- **THEN** up/down/flat counts are stored

### Requirement: Store sector data

The system SHALL store sector data in `market_sectors` table with fields:
- trade_date + sector_code (unique)
- sector_name, change_pct, amount, main_inflow

#### Scenario: Store multiple sectors
- **WHEN** sector data is cached
- **THEN** each sector is stored as a separate row
- **AND** trade_date + sector_code is unique

### Requirement: Store limit-up stocks

The system SHALL store limit-up stocks in `limit_up_stocks` table with fields:
- trade_date + stock_code (unique)
- stock_name, change_pct, limit_days, industry

#### Scenario: Store limit-up stocks
- **WHEN** limit-up stocks data is cached
- **THEN** each stock is stored as a separate row
- **AND** trade_date + stock_code is unique
