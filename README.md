# Cloud PriceOps Thesis

A comprehensive cloud pricing analytics and Total Cost of Ownership (TCO) estimation platform leveraging machine learning for intelligent pricing predictions across AWS, Azure, and GCP.

## 🎯 Overview

Cloud PriceOps is a full-stack application that ingests, normalizes, and analyzes cloud pricing data from multiple providers through the Infracost API. It features a Django REST backend with Celery task processing, PostgreSQL database, and a React + TypeScript frontend for TCO estimation and price comparison.

### Key Features

- **Multi-Cloud Price Normalization**: Automated ingestion and normalization of pricing data from AWS, Azure, and GCP
- **ML-Powered Price Prediction**: Hedonic regression models for intelligent price forecasting
- **TCO Estimation**: Interactive frontend for comparing Total Cost of Ownership across cloud providers
- **Data Export Pipeline**: Asynchronous CSV export with Nginx X-Accel-Redirect for efficient large file delivery
- **Domain Classification**: Automatic service classification (IaaS, PaaS, SaaS, Utility, etc.)
- **API Documentation**: Comprehensive OpenAPI/Swagger documentation via DRF Spectacular

## 🏗️ Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  React Frontend │ ───► │  Nginx Reverse   │ ───► │ Django Backend  │
│  (Vite + TS)    │      │     Proxy        │      │   REST API      │
└─────────────────┘      └──────────────────┘      └─────────────────┘
                                                             │
                         ┌───────────────────────────────────┼────────┐
                         │                                   │        │
                    ┌────▼─────┐      ┌──────────────┐  ┌───▼────┐  │
                    │PostgreSQL│      │ Redis Cache  │  │ Celery │  │
                    │ Database │      │  + Broker    │  │Workers │  │
                    └──────────┘      └──────────────┘  └────────┘  │
                                                                     │
                                      ┌──────────────────────────────▼───┐
                                      │  Infracost API (External Source)  │
                                      └────────────────────────────────────┘
```

## 📋 Prerequisites

- Docker & Docker Compose
- Python 3.10+ (for local development)
- Node.js 22+ (for local development)
- Infracost API Key ([Get one here](https://www.infracost.io/docs/#2-get-api-key))

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd cloud-priceops-thesis
```

### 2. Environment Configuration

Create environment files from templates:

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
# backend/.env
SECRET_KEY=your-django-secret-key
INFRACOST_API_KEY=your-infracost-api-key
POSTGRES_DB=cloud_pricing_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-secure-password
DATABASE_URL=postgresql://postgres:your-secure-password@db:5432/cloud_pricing_db
REDIS_URL=redis://redis:6379/0

# frontend/.env
VITE_APP_BACKEND_URL=http://localhost:8000
```

### 3. Launch with Docker Compose

```bash
docker-compose up --build
```

This will start:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/api/schema/swagger-ui/
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### 4. Initialize Database

```bash
# Run migrations
docker-compose exec backend python manage.py migrate

# Create initial cloud provider data
docker-compose exec backend python manage.py init_cloud_data
```

### 5. Import Pricing Data

Trigger the weekly pricing dump import (initial run may take 10-15 minutes):

```bash
docker-compose exec backend python manage.py shell
>>> from cloud_pricing.tasks import weekly_pricing_dump_update
>>> weekly_pricing_dump_update.delay()
```

Or via Django admin/Celery Beat (configured for weekly automatic updates).

## 📊 Data Flow

### 1. Pricing Data Ingestion

```python
# backend/cloud_pricing/tasks.py

@shared_task
def weekly_pricing_dump_update():
    """
    1. Downloads Infracost pricing dump (CSV.GZ, ~300MB compressed)
    2. Creates PostgreSQL staging table
    3. Loads data via COPY or batch insert
    4. Normalizes provider/service/region/pricing models
    5. Parses JSON pricing arrays and inserts to RawPricingData
    6. Transforms and inserts to NormalizedPricingData with domain classification
    """
```

**Key Normalization Steps:**
- Unified pricing model detection (On-Demand, Spot, Reserved, etc.)
- Term length extraction from multiple fields
- Price-per-hour conversion from various units (Month, GB, Count, etc.)
- Domain label classification via PostgreSQL function (`classify_domain()`)

### 2. Domain Classification

Automatic service categorization using SQL function:

```sql
-- backend/cloud_pricing/sql/generate_domain_label.sql

CREATE OR REPLACE FUNCTION classify_domain(
    service_name TEXT,
    instance_type TEXT
) RETURNS TEXT AS $$
    -- Returns: 'iaas', 'paas', 'saas', 'database', 'storage', 'ml', 'utility', 'other'
```

**Categories:**
- **IaaS**: EC2, Virtual Machines, Compute Engine
- **PaaS**: App Service, Cloud Run, Lambda
- **SaaS**: GitHub AE, Power BI
- **Database**: RDS, Cloud SQL, Cosmos DB
- **Storage**: S3, Blob Storage, Cloud Storage
- **ML/AI**: SageMaker, AI Platform
- **Utility**: Bandwidth, Data Transfer

### 3. ML Model Registry

Train and register hedonic regression models for price prediction:

```python
# examples/hedonic/model.py

# 1. Load and clean pricing export
df = pd.read_csv("pricing_export.csv")

# 2. Feature engineering
# - Log-transform continuous features (vCPU, memory, term length)
# - One-hot encode categorical features (provider, region, OS, etc.)

# 3. Feature selection via Lasso
lasso = LassoCV(cv=5).fit(X_train, Y_train)
selected_features = X_train.columns[lasso.coef_ != 0]

# 4. Train OLS with robust standard errors
model = sm.OLS(Y_final, X_ols).fit(cov_type='HC3')

# 5. Register via API
files = {
    "model_binary": open("hedonic_model.pkl", "rb"),
    "encoder_binary": open("encoder.pkl", "rb")
}
requests.post("http://localhost:8000/engines/", data=payload, files=files)
```

### 4. Price Prediction Flow

```
Frontend → Backend: POST /engines/predict/AWS_Compute_Pricing
Backend → Celery: compute_price_prediction.delay(engine_id, specs)
Celery: Load model & encoder binaries
Celery: Transform features (log-scale, encode)
Celery: Predict log(price), exponentiate
Celery → Backend: Return predicted price
Backend → Frontend: {"predicted_price": 0.052}
```

## 🔌 API Endpoints

### Pricing Data

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/normalized-pricing-data/` | GET | List normalized pricing records |
| `/normalized-pricing-data/export/` | POST | Queue CSV export task |
| `/normalized-pricing-data/export-status/` | GET | Check export status / download file |

**Export Example:**

```bash
# 1. Start export (with optional domain filter)
curl -X POST "http://localhost:8000/normalized-pricing-data/export/?domain_label=iaas&min_data_completeness=true"
# Response: {"task_id": "550e8400-e29b-41d4-a716-446655440000", "status": "Task queued"}

# 2. Check status
curl "http://localhost:8000/normalized-pricing-data/export-status/?task_id=550e8400-e29b-41d4-a716-446655440000"

# 3. Download file (when status=SUCCESS)
curl "http://localhost:8000/normalized-pricing-data/export-status/?task_id=550e8400-e29b-41d4-a716-446655440000&download=true" -o export.csv
```

### ML Engine

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/engines/` | GET | List registered ML engines |
| `/engines/` | POST | Register new model (multipart/form-data) |
| `/engines/predict/<engine_name>/` | POST | Get price prediction |

**Prediction Example:**

```bash
curl -X POST http://localhost:8000/engines/predict/AWS_Compute_Pricing/ \
  -H "Content-Type: application/json" \
  -d '{
    "vcpu": 4,
    "memory": 16,
    "region": "us-east-1",
    "os": "Linux",
    "tenancy": "shared"
  }'

# Response: {"predicted_price": 0.0524}
```

## 🎨 Frontend - ML Price Prediction Interface

### Overview

The frontend is a clean, modern React + TypeScript application built with Vite that provides an intuitive interface for ML-powered cloud price predictions. Users can input resource specifications and receive instant price estimates using trained hedonic regression models.

### Features

- **ML Engine Selection**: Choose from registered prediction models with real-time performance metrics (R², MAPE)
- **Smart Form Validation**: Required fields (vCPU, Memory) with optional parameters for refined predictions
- **Real-time Predictions**: Instant price estimates with monthly and yearly cost projections
- **Clean UI/UX**: Professional design with clear visual hierarchy and responsive layout

### Usage

1. **Navigate to** http://localhost:3000

2. **Configure your prediction:**
   - **Required Fields:**
     - **vCPU** - Number of virtual CPUs (e.g., 4)
     - **Memory (GB)** - RAM in gigabytes (e.g., 16)
   
   - **Optional Fields:**
     - **Region** - Cloud region code (e.g., us-east-1, eastus)
     - **Operating System** - Linux, Windows, RHEL, SUSE
     - **Tenancy** - Shared, Dedicated, or Dedicated Host
     - **Term Length** - Contract length in months for reserved instances
     - **Payment Options** - All Upfront, Partial Upfront, No Upfront
     - **Additional Parameters** - Custom key-value pairs for specialized features

3. **Get prediction results:**
   - Predicted hourly price ($/hour)
   - Monthly cost estimate (price × 730 hours)
   - Yearly cost estimate (price × 8,760 hours)
   - Engine version and metadata

### Example Workflow

**Input:**
```
vCPU: 4
Memory: 16 GB
Region: us-east-1 (optional)
OS: Linux (optional)
Tenancy: Shared (optional)
```

**Output:**
```
┌──────────────────────────────────────────────────┐
│  Predicted Price: $0.052400 USD / hour           │
│  Monthly Cost: $38.25 USD                        │
│  Yearly Cost: $459.00 USD                        │
│  Engine: AWS_Compute_Pricing v2025.12.18.06      │
└──────────────────────────────────────────────────┘
```

### Model Information Display

The interface shows live model performance metrics:
- **Type**: Hedonic_Regression
- **R² Score**: 0.9175 (91.75% variance explained)
- **MAPE**: 41.72% (mean absolute percentage error)
- **Log Features**: term_length_years, vcpu_count, memory_gb
- **Categorical Features**: provider, region, OS, tenancy, etc.

### API Integration

Frontend communicates with backend via REST API:

```javascript
POST /engines/predict/{engine_name}/
Content-Type: application/json

{
  "vcpu_count": 4,
  "memory_gb": 16,
  "region": "us-east-1",
  "operating_system": "Linux",
  "tenancy": "shared",
  "term_length_years": 1
}
```

**Response:**
```json
{
  "engine_version": "AWS_Compute_Pricing-v2025.12.18.06",
  "predicted_price": 0.052400,
  "currency": "USD"
}
```

## 📁 Project Structure

```
cloud-priceops-thesis/
├── backend/
│   ├── cloud_pricing/          # Main pricing app
│   │   ├── api/                # REST API views & serializers
│   │   ├── management/         # Django commands (init_cloud_data)
│   │   ├── migrations/         # Database migrations
│   │   ├── sql/                # PostgreSQL functions (domain classification)
│   │   ├── models.py           # ORM models (NormalizedPricingData, etc.)
│   │   └── tasks.py            # Celery tasks (ingestion, export)
│   ├── model_registry/         # ML model management
│   │   ├── api/                # ML engine API
│   │   ├── models.py           # MLEngine, ModelCoefficient
│   │   └── tasks.py            # Prediction workers
│   ├── core/                   # Django settings & config
│   ├── manage.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/         # React components (ComparisonChart)
│   │   ├── App.tsx             # Main TCO estimation interface
│   │   └── main.tsx
│   ├── package.json
│   └── Dockerfile
├── nginx/                      # Reverse proxy configuration
├── examples/
│   └── hedonic/                # ML model training scripts
│       └── model.py            # Hedonic regression example
├── docker-compose.yml
└── README.md
```

## 🔧 Development

### Local Backend Development

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start dev server
python manage.py runserver

# Start Celery worker (separate terminal)
celery -A core worker -l info
```

### Local Frontend Development

```bash
cd frontend
npm install
npm run dev  # Starts on http://localhost:5173
```

### Running Tests

```bash
# Backend
docker-compose exec backend python manage.py test

# Frontend
docker-compose exec frontend npm test
```

## 📊 Database Schema

### Key Models

**NormalizedPricingData**
- Normalized pricing records from all providers
- Foreign keys: `CloudProvider`, `CloudService`, `Region`, `PricingModel`, `Currency`
- Price fields: `price_per_unit`, `effective_price_per_hour`, `price_unit`
- Metadata: `vcpu_count`, `memory_gb`, `storage_type`, `domain_label`
- Lifecycle: `effective_date`, `is_active`, `created_at`, `updated_at`

**RawPricingData**
- Stores raw JSON payloads from Infracost
- Unique constraint on `product_hash` for deduplication
- Linked to `NormalizedPricingData` via `raw_entry` FK

**MLEngine**
- Stores trained model binaries and metadata
- Fields: `name`, `version`, `model_type`, `feature_names`, `r_squared`, `mape`
- One active "Champion" model per name

### Indexes

```sql
-- Performance-critical indexes
CREATE INDEX idx_npd_active_effective ON normalized_pricing_data (is_active, effective_date);
CREATE INDEX idx_npd_prov_serv_reg ON normalized_pricing_data (provider_id, service_id, region_id);
CREATE INDEX idx_price_positive ON normalized_pricing_data (price_per_unit) WHERE price_per_unit > 0;
CREATE INDEX idx_npd_domain_label ON normalized_pricing_data (domain_label);
```

## 🛠️ Advanced Features

### X-Accel-Redirect Export

Large CSV exports (>300MB) use Nginx's X-Accel-Redirect for efficient streaming:

```python
# backend/cloud_pricing/api/views.py

response = HttpResponse()
response['Content-Type'] = 'text/csv'
response['Content-Disposition'] = f'attachment; filename="{file_name}"'
response['Content-Length'] = file_size
response['X-Accel-Redirect'] = f'/protected/exports/{file_name}'
return response
```

### Celery Periodic Tasks

```python
# backend/core/celery.py

app.conf.beat_schedule = {
    'weekly-pricing-update': {
        'task': 'cloud_pricing.tasks.weekly_pricing_dump_update',
        'schedule': crontab(day_of_week=1, hour=2, minute=0),  # Every Monday at 2 AM
    },
}
```

## 🐛 Troubleshooting

### Database Connection Issues

```bash
# Check if PostgreSQL is running
docker-compose ps db

# View logs
docker-compose logs db

# Reset database (WARNING: destroys data)
docker-compose down -v
docker-compose up -d db
docker-compose exec backend python manage.py migrate
```

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

## 📝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is part of a thesis research and is provided for educational purposes.

## 🙏 Acknowledgments

- **Infracost** for providing the comprehensive cloud pricing APIs

## 📧 Contact

For questions or issues, please open a GitHub issue or contact the project maintainer.

---

**Built with** ❤️ **using Django, React, PostgreSQL, Redis, and Celery**