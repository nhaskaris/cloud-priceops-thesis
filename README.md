### 13.11

- Frontend is now able to run with docker. User needs to modify the .env.template wth the correct arguments.

### 23.11

- Created raw and normalized tables for data.
- Get their prices file, unzip it and put in the db (3m rows)(slow version 1)
- Reading through their code on their copy of cloud api I think they are dumbing the old prices and put the new when pulling.
- Instead of parsing row by row the csv file we unload it into a staging table and then copying it into our raw table which we then normalize it by 5k at a time.(normalization still takes time)(faster version 2)
- Had to alter decimals length since prices can have many digits(for prices per unit)
- Need to take a look at service code to not be cutted to 50 char.

### 26.11
- Change service_code to be 100 char instead of 50 so it doesnt get cut down.
- Celery worker was crushing when parsing the data so we lowered to 1 child with 50 max tasks and avoiding extra tasks.
- When we fetch now new data we check if there were any changes and skip duplicate records(if raw was the same as before), if not we add a new row and on old one we set it as inactive and with an end date and add a row on price history.


### 27.11

- Added a Feature Store for users to use for ml training
- Created endpoinds for users to access the feature store.
- We update our features every time we get new prices. (every week practically)
- We use redis for the online access and duckdb for offline. Basically online access means its the latest data features for users to get. Offline's purpose is for training and historical prices.
- Features accessible right now (
    Latest price per unit.
    previous_price
    price_diff_abs
    price_diff_pct
    days_since_price_change
    price_change_frequency_90d
  )
- Added reference to raw data from norm instead of saving raw json on norm alongside raw table 
- Add a ML registry(future)/MLFlow

### 28.11

- Removed on startup run of events.
- Added on readme the commands to run the tasks manually.
- Removed soft kill of tasks

### 29.11
- Replaced auto_add_now for date times with default=timezone.now
- Optimized celery task to not  over use ram and cpu but opening a cursor with select all from staging. We then fetch a batch of them(1000) to control how many rows we keep in memory. This makes it a bit slow but allows us to not over use resources and crash the system.

### 1.12
- Each child celery worker should only handle 1 task so it can restart and empty ram after each task is done.(Was using 8gb of ram)
- Introduced feast, using redis for online and postgres for offline. We cant push to postgres directly so we use the django orm to do that and then we just push to online. We need offline for training so we can retrieve. Created new app for the feast_offline

### 2.12
- Delete infracost staging table afterwards
- Price history was missing when inserting new data

### 3.12
- Re-worked models
- Re-working weekly dump

# 6.12
- Finally done with weekly dump, switched everything to use sql statements directly and we slowly fill step by step each table.
- Added description & term_length to normalized table because amazon has multiple price points for same product but changes a few things.

# 8.12
- Re-worked feature store and we are currently saving the price of products. If same product come with different price it will create a new row. (This will help our postgres offline store)
- Created model registry app

# 9.12
- Added support for api doc
- Added logging for download of file progress
- Added a check to not download the file again if its locally so we dont spam infracost from dev.

# 11.12
- Normalized term_length
- Download file locally if it doesnt exist so we dont spam call their api.
- Normalized cpu & storage_type into our columns

# 12.12
- Added domain_label
- Created a function to calculate domain_label sql
- If the env is DEV it will only use 10k rows to be able to debug easier
- Normalized memory into memory_gb column
- Normalized price_unit into effective_price_per_hour

# 13.12
- 1.828.73 rows have in price_unit hrs with price 0 which means we can ignore these rows and their price_unit because it is for offers
- The quantity price_unit means that you buy the whole thing for the term_length_year (it is always non null). That way we can normalize the price to per hour and also keep the columns that show if its reserved, partial, non-partial. That means we can use our pricing-model column to show that they fall under the category reserved etc. And create a new column if its upfront the cost from the description
- By reading `termPurchaseOption` field from prices we can check if its partial, upfront, or none and we insert into 3 boolean columns
- We normalize the pricing_model. Any CommitXm/y will be turned into column term_length_years. Also pricing model that are similar scoped but different named by different providers are grouped into one. Rest are keeped as is.

# 15.12
- Created an endpoint for models to retrieve data for their training/feature creation.

# 16.12
- Endpoind now returns a basic csv file with the columns
- Introduced an nginx service for delivering files (Takes a lot of time)

# 17.12
- Hardcoding categories of iaas/paas etc of services for normalizing data.

### DOC
```docker exec -it priceops_celery_worker \
  celery -A core call cloud_pricing.tasks.weekly_pricing_dump_update
```

```
docker exec -it priceops_celery_worker \
  celery -A core call feast_offline.tasks.materialize_features
```

```
feast apply
``` in the direectory of feature_repo