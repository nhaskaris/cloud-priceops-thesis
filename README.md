# Cloud PriceOps - Technical Documentation

A full-stack cloud pricing analytics platform with multi-provider data normalization, ML model registry, and price prediction APIs.

## Architecture Overview

```
┌─────────────────┐
│   Frontend      │
│   (React/Vite)  │
└────────┬────────┘
         │ HTTP
    ┌────▼─────┐
    │   Nginx   │
    │ (Reverse  │
    │  Proxy)   │
    └────┬─────┘
         │ Port 80 → 3000 (Frontend)
         │ Port 80 → 8000 (Backend)
    ┌────▼──────────────┐
    │   Backend (Django)  │
    │   + Gunicorn       │
    └────┬───────────────┘
         │
    ┌────┴─────────────────────────┐
    │                              │
┌───▼────┐  ┌────────┐  ┌─────────▼─┐  ┌──────────┐
│PostgreSQL│  │ Redis  │  │  Celery   │  │  Flower  │
│         │  │        │  │  Worker   │  │ (Monitoring)
└─────────┘  └────────┘  └───────────┘  └──────────┘
```

**Components:**
- **Frontend**: Vite + React/TypeScript (port 3000)
- **Nginx**: Reverse proxy (port 80)
- **Backend**: Django + Gunicorn (port 8000)
- **PostgreSQL**: Primary data store (port 5432)
- **Redis**: Message broker & cache (port 6379)
- **Celery**: Async task queue for data import and ML predictions
- **Flower**: Celery task monitoring (port 5555)

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.10+ (local development)
- Node.js 22+ (local development)
- Infracost API Key ([Get here](https://www.infracost.io/docs/#2-get-api-key))

### 1. Environment Setup

```bash
# Root directory
cp .env.template .env

# Backend
cp backend/.env.template backend/.env

# Frontend  
cp frontend/.env.template frontend/.env
```

**Required Environment Variables:**

```bash
# .env (root)
POSTGRES_DB=cloud_pricing_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<secure-password>
REDIS_URL=redis://redis:6379/0

# backend/.env
SECRET_KEY=<django-secret>
DEBUG=False
INFRACOST_API_KEY=<api-key>
DATABASE_URL=postgresql://postgres:<password>@db:5432/cloud_pricing_db

# frontend/.env
VITE_APP_BACKEND_URL=http://localhost
```

### 2. Launch Services

```bash
docker compose up -d --build
```

**Access Points:**
- Frontend: http://localhost
- API (Swagger): http://localhost/api/schema/swagger-ui/
- Flower (Celery): http://localhost:5555

### 3. Initialize Database

```bash
# Run migrations
docker compose exec backend python manage.py migrate
```

### 4. Import Pricing Data

```bash
# Trigger initial pricing import (10-15 min)
docker compose exec backend python manage.py shell
>>> from cloud_pricing.tasks import weekly_pricing_dump_update
>>> weekly_pricing_dump_update.delay()
```

Subsequent updates run automatically via Celery Beat (weekly on Monday 2 AM).

## Core Services

### Backend (Django + DRF)

**Path:** `/backend/`

**Key Apps:**
- `cloud_pricing` - Pricing data models, ingestion, normalization
- `model_registry` - ML engine registry, prediction endpoints
- `core` - Django settings, Celery config, URL routing

**Running Locally:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

**API Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/normalized-pricing-data/` | GET | List pricing records |
| `/api/normalized-pricing-data/export/` | POST | Queue CSV export |
| `/api/normalized-pricing-data/export-status/` | GET | Check/download export |
| `/api/engines/` | GET, POST | List/register ML models |
| `/api/engines/summary/` | GET | All models (metadata only) |
| `/api/engines/types/` | GET | Available model types + best model per type |
| `/api/engines/predict-by-type/{type}/` | POST | Predict using best model of type |
| `/api/schema/swagger-ui/` | GET | OpenAPI documentation |

**Example Prediction:**
```bash
curl -X POST http://localhost:8000/api/engines/predict-by-type/regression/ \
  -H "Content-Type: application/json" \
  -d '{
    "vcpu": 4,
    "memory": 16,
    "region": "us-east-1",
    "operating_system": "Linux"
  }'
```

### Frontend (React + Vite)

**Path:** `/frontend/`

**Components:**
- `PredictionForm` - vCPU, memory, region input
- `ModelsDashboard` - Model comparison & metrics
- `CostOptimizer` - Price prediction & cost breakdowns
- `Documentation` - API usage guide

**Running Locally:**
```bash
cd frontend
npm install
npm run dev  # Starts on http://localhost:5173
```

**Build:**
```bash
npm run build  # Outputs to /dist
```

### Database (PostgreSQL)

**Key Tables:**
- `normalized_pricing_data` - Main pricing table (~10M+ rows)
- `raw_pricing_data` - Raw Infracost JSON payloads
- `cloud_providers`, `cloud_services`, `regions` - Reference data
- `ml_engine` - Registered models & coefficients
- `api_call_logs` - Request metrics

**Critical Indexes:**
```sql
CREATE INDEX idx_npd_matching ON normalized_pricing_data 
  (is_active, region_id, operating_system, vcpu_count, memory_gb, effective_date);
CREATE INDEX idx_npd_active_effective ON normalized_pricing_data (is_active, effective_date);
CREATE INDEX idx_npd_prov_serv_reg ON normalized_pricing_data (provider_id, service_id, region_id);
```

**Connect Locally:**
```bash
psql -h localhost -U postgres -d cloud_pricing_db
```

### Task Queue (Celery + Redis)

**Path:** `/backend/core/celery.py`

**Key Tasks:**
- `weekly_pricing_dump_update()` - Downloads Infracost dump, normalizes, imports
- `export_normalized_pricing()` - Generates CSV export
- `compute_price_prediction()` - ML inference via registered models
- `compute_tco_comparison()` - TCO analysis across cloud providers

**Monitor Tasks:**
- Flower UI: http://localhost:5555
- Terminal: `docker compose logs celery`

**Run Task Manually:**
```bash
docker compose exec backend celery -A core call cloud_pricing.tasks.weekly_pricing_dump_update
```

### Reverse Proxy (Nginx)

**Config:** `/nginx/nginx.conf`

**Routes:**
- `GET /` → Frontend (port 3000)
- `POST /api/` → Backend (port 8000)
- `/exports/` → X-Accel-Redirect protected static files

**Edit Config:**
```bash
# Make changes to /nginx/nginx.conf
docker compose exec nginx nginx -s reload
```

## Data Pipeline

### 1. Pricing Data Import

```
Infracost API (CSV.GZ, ~300MB)
    ↓
weekly_pricing_dump_update() [Celery Task]
    ├─ Download & extract
    ├─ Create staging table
    ├─ COPY/batch insert to raw_pricing_data
    ├─ Call normalize_price_unit() [PL/pgSQL]
    ├─ Call classify_domain() [PL/pgSQL]
    └─ INSERT to normalized_pricing_data
    ↓
NormalizedPricingData table
```

**Normalization Logic:**
- Provider/service lookup from JSON
- Region name standardization
- Price unit conversion (Month → Hour, GB-Second → Hour, etc.)
- Effective price per hour calculation
- Domain classification (IaaS, PaaS, Database, etc.)

**PL/pgSQL Functions:**
- `normalize_price_unit(raw_unit TEXT)` → JSONB with amount, base, period
- `classify_domain(service_name, instance_type)` → domain_label

### 2. ML Model Registration

**Workflow:**
```
Train Model (Local)
    ↓
Serialize to .pkl
    ├─ model_binary (scikit-learn OLS/Ridge)
    └─ encoder_binary (OneHotEncoder)
    ↓
POST /api/engines/ (multipart/form-data)
    ├─ model_binary
    ├─ encoder_binary
    ├─ name, version, model_type
    └─ feature_names, r_squared, mape
    ↓
MLEngine model stored in DB
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/engines/ \
  -F "name=AWS_Compute_Pricing" \
  -F "version=2025.12.18" \
  -F "model_type=hedonic_regression" \
  -F "r_squared=0.9175" \
  -F "mape=41.72" \
  -F "feature_names=[\"log_vcpu\", \"log_memory\", ...]" \
  -F "model_binary=@model.pkl" \
  -F "encoder_binary=@encoder.pkl"
```

### 3. Price Prediction

```
Frontend POST /api/engines/predict-by-type/{type}/
    ├─ Input: vcpu, memory, region, OS, tenancy
    ├─ Backend selects best model of type (by R²)
    └─ Queues compute_price_prediction task
    ↓
Celery Worker
    ├─ Load model binary from DB
    ├─ Load encoder binary from DB
    ├─ Transform input features (log-scale, encode)
    ├─ Call model.predict()
    └─ Exponentiate log(price) → price
    ↓
Return {predicted_price, monthly_cost, yearly_cost}
```

### 4. CSV Export

```
Frontend POST /api/normalized-pricing-data/export/
    ├─ Input: domain_label, filters, min_data_completeness
    └─ Queues export_normalized_pricing task
    ↓
Celery Worker
    ├─ Query filtered records
    ├─ Write to CSV (streaming for large exports)
    ├─ GZIP compress
    └─ Store in /backend/media/exports/
    ↓
Frontend GET /api/normalized-pricing-data/export-status/
    ├─ Check task status
    ├─ Return download URL
    └─ Browser downloads via X-Accel-Redirect
```

## Development Workflow

### Local Development (Without Docker)

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql://postgres:password@localhost:5432/cloud_pricing_db
python manage.py migrate
python manage.py runserver

# Separate terminal
celery -A core worker -l info
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Database Migrations

```bash
# Create migration
docker compose exec backend python manage.py makemigrations

# Apply migration
docker compose exec backend python manage.py migrate

# Rollback
docker compose exec backend python manage.py migrate cloud_pricing 0001
```

### Adding Custom Models

See `/examples/hedonic/model.py` for a complete example.

**Steps:**
1. Export pricing data via frontend export tool
2. Train model locally using scikit-learn
3. Pickle model + encoder
4. Register via `POST /api/engines/`

## Troubleshooting

### Reset Database
```bash
docker compose down -v
docker compose up -d db
docker compose exec backend python manage.py migrate
```

### View Logs
```bash
docker compose logs -f backend    # Django + Gunicorn
docker compose logs -f celery     # Task queue
docker compose logs -f nginx      # Reverse proxy
docker compose logs -f db         # PostgreSQL
```

### Django Shell
```bash
docker compose exec backend python manage.py shell
>>> from cloud_pricing.models import NormalizedPricingData
>>> NormalizedPricingData.objects.count()
```

### Clear Cache
```bash
docker compose exec redis redis-cli FLUSHALL
```

### Rebuild Containers
```bash
docker compose down
docker compose up -d --build
```

## Deployment Considerations

### Performance
- Nginx caches static assets and serves as reverse proxy
- PostgreSQL indexes on frequently filtered columns
- Celery runs async tasks to avoid blocking requests
- X-Accel-Redirect streams large exports efficiently

### Security
- Django `SECRET_KEY` must be unique per environment
- Database credentials in `.env` (never commit)
- Nginx disables version disclosure (`server_tokens off`)
- CORS configured for cross-domain requests

### Monitoring
- Flower for task queue health: http://localhost:5555
- PostgreSQL slow query log in `docker-compose.yml`
- Django request logging to stdout

### Scaling
- Horizontal: Add more Celery workers (`docker compose up -d --scale celery=3`)
- Vertical: Increase Gunicorn workers in `backend/gunicorn.conf.py`
- Database: Consider read replicas for analytics queries

### Celery Tasks Not Running

```bash
# Check worker logs
docker-compose logs celery-worker

# Inspect Redis
docker-compose exec redis redis-cli
> KEYS *
> GET celery-task-meta-<task-id>
```

### Large File Export Timeout

Increase timeouts in `nginx/nginx.conf`:

```nginx
proxy_read_timeout 300s;
proxy_send_timeout 300s;
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is part of a thesis research and is provided for educational purposes.

## Acknowledgments

- Infracost for providing the comprehensive cloud pricing APIs

## Contact

For questions or issues, please open a GitHub issue or contact the project maintainer.

---

Built with Django, React, PostgreSQL, Redis, and Celery