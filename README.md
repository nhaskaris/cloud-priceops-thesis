### 13.11

- Frontend is now able to run with docker. User needs to modify the .env.template wth the correct arguments.

### 23.11

- Created raw and normalized tables for data.
- Get their prices file, unzip it and put in the db (3m rows)(slow version 1)
- Reading through their code on their copy of cloud api I think they are dumbing the old prices and put the new when pulling.
- Instead of parsing row by row the csv file we unload it into a staging table and then copying it into our raw table which we then normalize it by 5k at a time.(normalization still takes time)(faster version 2)
- Had to alter decimals length since prices can have many digits(for prices per unit)
- Need to take a look at service code to not be cutted to 50 char.