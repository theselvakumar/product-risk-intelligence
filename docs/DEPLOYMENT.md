# DRISHTI Platform — Production Deployment & Infrastructure Runbook

**Document Version:** 1.0.0  
**Effective Date:** September 2026  
**Classification:** Official Infrastructure Standard — FSSAI Digital Surveillance  
**Applicability:** Production Cloud Environments, Government Data Centers, Hybrid Deployments

---

## 1. System Architecture & Component Overview

The **DRISHTI** production topology consists of four containerized tiers deployed behind an enterprise TLS-terminating reverse proxy (NGINX / Cloudflare):

```
                       [ Internet / Gov-WAN ]
                                 │
                         (HTTPS / Port 443)
                                 ▼
                     [ NGINX Reverse Proxy / WAF ]
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
       [ Frontend Service ]            [ Backend Service ]
       Next.js 16 (Port 3000)          FastAPI ASGI (Port 8000)
       Tailwind CSS / React 19         Uvicorn Workers / Pydantic
                 │                               │
                 └───────────────┬───────────────┘
                                 ▼
                    [ PostgreSQL 16 Database ]
                    Async SQLAlchemy / Connection Pooling
                                 │
                                 ▼
                        [ Persistent Storage ]
                        /uploads/cases/{case_id}
```

---

## 2. Infrastructure & Hardware Prerequisites

| Resource | Minimum Requirement (Staging) | Recommended Production Spec |
| :--- | :--- | :--- |
| **CPU Architecture** | x86_64, 4 vCPUs | x86_64, 8+ vCPUs |
| **System Memory (RAM)**| 8 GB | 16 GB - 32 GB |
| **Storage (Database)** | 50 GB SSD (NVMe preferred) | 250 GB+ SSD with automated snapshots |
| **Storage (Evidence)** | 100 GB persistent block storage | 1 TB+ dedicated volume or S3-compatible bucket |
| **Operating System** | Ubuntu 22.04 LTS / Debian 12 | Enterprise Linux (RHEL 9 / Ubuntu 24.04 LTS) |
| **Container Engine** | Docker Engine 24.0+ & Compose v2 | Docker Engine 26.0+ or Kubernetes 1.28+ |

---

## 3. Environment Configuration Specifications

### 3.1 Backend Configuration (`backend/.env`)

```env
# Application Runtime
PROJECT_NAME="DRISHTI Regulatory Intelligence Platform"
VERSION="1.0.0"
ENVIRONMENT="production"
DEBUG=false
HOST="0.0.0.0"
PORT=8000

# Security & Cryptography
# Generate with: openssl rand -hex 32
SECRET_KEY="replace-with-ultra-secure-256-bit-cryptographic-key-in-production"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Database Connectivity (PostgreSQL 16 Async)
POSTGRES_SERVER="db"
POSTGRES_PORT=5432
POSTGRES_USER="drishti_admin"
POSTGRES_PASSWORD="secure-prod-db-password-fssai"
POSTGRES_DB="drishti_prod"
DATABASE_URL="postgresql+asyncpg://drishti_admin:secure-prod-db-password-fssai@db:5432/drishti_prod"

# CORS Allowed Origins
CORS_ORIGINS=["https://drishti.fssai.gov.in","https://surveillance.fssai.gov.in"]

# File Storage Configuration
MAX_FILE_SIZE_BYTES=15728640
UPLOAD_DIRECTORY="/app/uploads"
```

### 3.2 Frontend Configuration (`frontend/.env.local`)

```env
# API Endpoint Target
NEXT_PUBLIC_API_URL="https://drishti.fssai.gov.in/api/v1"
NODE_ENV="production"
PORT=3000
```

---

## 4. Docker Compose Deployment Procedure

### 4.1 Step 1: Clone and Configure Environment
```bash
git clone https://github.com/fssai/drishti.git /opt/drishti
cd /opt/drishti

# Configure environment secrets
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
# Edit backend/.env and frontend/.env.local with production credentials
```

### 4.2 Step 2: Build and Launch Containers
```bash
cd docker
docker compose -f docker-compose.yml build --no-cache
docker compose -f docker-compose.yml up -d
```

### 4.3 Step 3: Verify Container Health
```bash
docker compose ps
```
Expected output:
- `drishti-postgres`: `healthy`
- `drishti-backend`: `healthy` (listening on `:8000`)
- `drishti-frontend`: `healthy` (listening on `:3000`)

---

## 5. Reverse Proxy & TLS Hardening (NGINX Configuration)

Deploy NGINX on the host server or ingress controller:

```nginx
server {
    listen 80;
    server_name drishti.fssai.gov.in;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name drishti.fssai.gov.in;

    ssl_certificate /etc/ssl/certs/drishti.crt;
    ssl_certificate_key /etc/ssl/private/drishti.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security Headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Frontend Application
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API & Health Gateway
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 20M;
    }

    location /auth/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Uploads Serving
    location /uploads/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

---

## 6. Database Backups & Disaster Recovery

### 6.1 Automated Daily Database Dumps
Configure a daily cron task:
```bash
0 2 * * * docker exec drishti-postgres pg_dump -U drishti_admin drishti_prod | gzip > /opt/backups/drishti_db_$(date +\%F).sql.gz
```

### 6.2 Evidence Storage Backup
Sync the physical packaging image storage directory to offsite secure cold storage:
```bash
0 3 * * * rsync -avz --delete /opt/drishti/backend/uploads/ backup-server:/mnt/storage/drishti-evidence/
```

---

## 7. Health Probes & Monitoring Telemetry

- **Liveness Probe**:
  `GET /health?check_db=false`  
  Returns `200 OK` with JSON `{ "status": "ok" }`. Used by load balancer health checks.
- **Readiness Probe**:
  `GET /health?check_db=true`  
  Tests real async connection latency to PostgreSQL. Returns database roundtrip latency in milliseconds.
