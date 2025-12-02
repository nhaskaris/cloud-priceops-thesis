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

### DOC
```docker exec -it priceops_celery_worker \
  celery -A core call cloud_pricing.tasks.weekly_pricing_dump_update
```

```
docker exec -it priceops_celery_worker \
  celery -A core call cloud_pricing.tasks.materialize_features
```

```
feast apply
``` in the direectory of feature_repo