# Wilhelm

A Spring Boot application that provides backend services for AI-assisted nursing, including patient management, visit tracking, and per-visit document storage (triage PDFs, medical report PDFs, X-ray images).

## Requirements

| Tool | Minimum version |
|------|----------------|
| JDK | 21 |
| Maven | 3.9+ (or use `./mvnw`) |
| PostgreSQL | 14+ |

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd Wilhelm
```

### 2. Set up the database

Create a PostgreSQL database and user:

```sql
CREATE DATABASE wilhelm;
CREATE USER wilhelm_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE wilhelm TO wilhelm_user;
```

### 3. Configure the application

Edit `src/main/resources/application.properties` (see [Configuration](#configuration) below).

### 4. Create the reports directory

The application creates per-patient/per-visit subfolders automatically, but the root must exist:

```bash
mkdir -p reports
```

### 5. Build and run

```bash
./mvnw spring-boot:run
```

Or build a JAR and run it:

```bash
./mvnw package
java -jar target/Wilhelm-0.0.1-SNAPSHOT.jar
```

### 6. Run with Docker

```bash
docker compose up --build
```

---

## Configuration

All properties live in `src/main/resources/application.properties`.

### Datasource

| Property | Default | Description |
|----------|---------|-------------|
| `spring.datasource.url` | `jdbc:postgresql://localhost:5432/wilhelm` | JDBC connection URL to the PostgreSQL database |
| `spring.datasource.username` | `postgres` | Database user |
| `spring.datasource.password` | `postgres` | Database password |
| `spring.datasource.driver-class-name` | `org.postgresql.Driver` | JDBC driver class; do not change unless switching databases |

### JPA / Hibernate

| Property | Default | Description |
|----------|---------|-------------|
| `spring.jpa.hibernate.ddl-auto` | `update` | Schema management strategy. `update` applies incremental changes on startup. Use `validate` in production to prevent automatic schema changes |
| `spring.jpa.show-sql` | `false` | Set to `true` to print all SQL statements to stdout; useful for debugging |
| `spring.jpa.properties.hibernate.dialect` | `org.hibernate.dialect.PostgreSQLDialect` | Hibernate dialect that matches the database engine |

### File storage

| Property | Default | Description |
|----------|---------|-------------|
| `app.reports.directory` | `reports` | Root directory on the filesystem where per-patient/per-visit subfolders are created |
| `spring.servlet.multipart.max-file-size` | `50MB` | Maximum size of a single uploaded file |
| `spring.servlet.multipart.max-request-size` | `50MB` | Maximum size of the entire multipart request |

### General

| Property | Default | Description |
|----------|---------|-------------|
| `spring.application.name` | `Wilhelm` | Logical name of the application, used in logging and Spring Cloud service discovery |

---

## Data model

### Patient

Stored in the `patients` table.

| Field | Column | Type | Nullable | Description |
|-------|--------|------|----------|-------------|
| `id` | `id` | `BIGINT` | No | Auto-generated primary key |
| `firstName` | `first_name` | `VARCHAR` | No | Patient's first name |
| `lastName` | `last_name` | `VARCHAR` | No | Patient's last name |
| `ehrId` | `ehr_id` | `VARCHAR` | No (unique) | Electronic Health Record identifier; used in all API URLs |
| `age` | `age` | `INT` | No | Patient's age in years |
| `gender` | `gender` | `VARCHAR` | No | Patient's gender: `MALE`, `FEMALE`, or `OTHER` |

### Visit

Stored in the `visits` table. Each patient can have multiple visits, including multiple visits on the same date.

| Field | Column | Type | Nullable | Description |
|-------|--------|------|----------|-------------|
| `id` | `id` | `BIGINT` | No | Auto-generated primary key; also used as the visit's folder name |
| `patient` | `patient_id` | `BIGINT` | No | Foreign key to the `patients` table |
| `visitDate` | `visit_date` | `DATE` | No | The date of the visit; used for filtering |
| `createdAt` | `created_at` | `TIMESTAMP` | No | Exact timestamp when the visit record was created |
| `triageFiles` | `triage_files` | `VARCHAR` | No | Comma-separated list of uploaded triage PDF filenames |
| `reportFiles` | `report_files` | `VARCHAR` | No | Comma-separated list of uploaded medical report PDF filenames |
| `xrayFiles` | `xray_files` | `VARCHAR` | No | Comma-separated list of uploaded X-ray image filenames |

### Filesystem layout

Each visit gets its own subfolder nested under the patient's EHR ID folder. Every uploaded file gets a unique timestamped filename so multiple uploads of the same document type never overwrite each other.

```
reports/
└── {ehrId}/
    └── {visitId}/
        ├── triage_20260418T120000.pdf
        ├── triage_20260418T143000.pdf
        ├── report_20260418T120500.pdf
        └── xray_20260418T121000.png
```

---

## API endpoints

Base URL: `http://localhost:8080`

### Patients

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/patients` | Create a new patient. Returns `201 Created` |
| `GET` | `/api/patients` | List all patients (paginated) |
| `GET` | `/api/patients/{ehrId}` | Get a single patient by EHR ID |
| `DELETE` | `/api/patients/{ehrId}` | Delete a patient, all their visits, and their entire folder. Returns `204 No Content` |

#### POST /api/patients — request body

```json
{
  "firstName": "Ana",
  "lastName": "Novak",
  "ehrId": "EHR-00042",
  "age": 34,
  "gender": "FEMALE"
}
```

#### GET /api/patients — query parameters

| Parameter | Example | Description |
|-----------|---------|-------------|
| `page` | `?page=0` | Page number, zero-based (default: `0`) |
| `size` | `?size=10` | Items per page (default: `20`) |
| `sort` | `?sort=lastName,asc` | Field and direction to sort by |

### Visits

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/patients/{ehrId}/visits` | Create a new visit for the patient. Returns `201 Created` |
| `GET` | `/api/patients/{ehrId}/visits` | List all visits for a patient |
| `GET` | `/api/patients/{ehrId}/visits?date=2026-04-18` | List all visits for a patient on a specific date |
| `GET` | `/api/patients/{ehrId}/visits/{visitId}` | Get a single visit |
| `DELETE` | `/api/patients/{ehrId}/visits/{visitId}` | Delete a visit and its document folder. Returns `204 No Content` |

#### POST /api/patients/{ehrId}/visits — request body

```json
{
  "visitDate": "2026-04-18"
}
```

#### Visit response

```json
{
  "id": 1,
  "patientEhrId": "EHR-00042",
  "visitDate": "2026-04-18",
  "createdAt": "2026-04-18T12:00:00Z",
  "triageFiles": ["triage_20260418T120000.pdf", "triage_20260418T143000.pdf"],
  "reportFiles": ["report_20260418T120500.pdf"],
  "xrayFiles": ["xray_20260418T121000.png"]
}
```

### Documents

Upload with `multipart/form-data`, field name `file`. Every upload creates a new timestamped file — existing files are never overwritten.

| Method | Path | Description |
|--------|------|-------------|
| `PUT` | `/api/patients/{ehrId}/visits/{visitId}/triage` | Upload a triage PDF |
| `GET` | `/api/patients/{ehrId}/visits/{visitId}/triage/{filename}` | Download a specific triage PDF |
| `PUT` | `/api/patients/{ehrId}/visits/{visitId}/report` | Upload a medical report PDF |
| `GET` | `/api/patients/{ehrId}/visits/{visitId}/report/{filename}` | Download a specific medical report PDF |
| `PUT` | `/api/patients/{ehrId}/visits/{visitId}/xray` | Upload an X-ray image |
| `GET` | `/api/patients/{ehrId}/visits/{visitId}/xray/{filename}` | Download a specific X-ray image |

---

## Typical flow

```bash
# 1. Create a patient
curl -X POST http://localhost:8080/api/patients \
     -H "Content-Type: application/json" \
     -d '{"firstName":"Ana","lastName":"Novak","ehrId":"EHR-00042","age":34,"gender":"FEMALE"}'

# 2. Create a visit for that patient
curl -X POST http://localhost:8080/api/patients/EHR-00042/visits \
     -H "Content-Type: application/json" \
     -d '{"visitDate":"2026-04-18"}'

# 3. Upload documents — each upload creates a new timestamped file
curl -X PUT http://localhost:8080/api/patients/EHR-00042/visits/1/triage -F "file=@triage.pdf"
curl -X PUT http://localhost:8080/api/patients/EHR-00042/visits/1/report -F "file=@report.pdf"
curl -X PUT http://localhost:8080/api/patients/EHR-00042/visits/1/xray   -F "file=@xray.png"

# 4. Upload a second triage for the same visit — does not overwrite the first
curl -X PUT http://localhost:8080/api/patients/EHR-00042/visits/1/triage -F "file=@triage2.pdf"

# 5. Get the visit to see all uploaded filenames
curl http://localhost:8080/api/patients/EHR-00042/visits/1

# 6. Download a specific file using the filename from the response
curl http://localhost:8080/api/patients/EHR-00042/visits/1/triage/triage_20260418T120000.pdf -O

# 7. Find all visits for a patient on a specific date
curl "http://localhost:8080/api/patients/EHR-00042/visits?date=2026-04-18"
```
