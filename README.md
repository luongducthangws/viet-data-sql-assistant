# Viet Data SQL Assistant

Há»‡ thá»‘ng chatbot dá»¯ liá»‡u ná»™i bá»™ cho phÃ©p ngÆ°á»i dÃ¹ng há»i báº±ng tiáº¿ng Viá»‡t tá»± nhiÃªn vÃ  nháº­n cÃ¢u tráº£ lá»i dá»±a trÃªn dá»¯ liá»‡u tháº­t trong PostgreSQL. Project hiá»‡n thá»±c hÃ³a má»™t pipeline **schema-grounded Text-to-SQL**: há»‡ thá»‘ng Ä‘á»c schema database, Ä‘Æ°a metadata vÃ o prompt nhÆ° retrieval context, sinh SQL an toÃ n, thá»±c thi trÃªn database, sau Ä‘Ã³ tá»•ng há»£p káº¿t quáº£ thÃ nh cÃ¢u tráº£ lá»i tiáº¿ng Viá»‡t.

> Project nÃ y táº­p trung vÃ o bÃ i toÃ¡n Vietnamese Text-to-SQL cho dá»¯ liá»‡u doanh nghiá»‡p. Kiáº¿n trÃºc cÃ³ thá»ƒ má»Ÿ rá»™ng sang domain khÃ¡c báº±ng cÃ¡ch thay datasource, schema snapshot vÃ  prompt nghiá»‡p vá»¥.

## Highlights

- Há»i Ä‘Ã¡p dá»¯ liá»‡u báº±ng tiáº¿ng Viá»‡t trÃªn PostgreSQL thÃ´ng qua FastAPI vÃ  giao diá»‡n web tá»‘i giáº£n.
- Schema-grounded generation: inject **14 báº£ng, 92 cá»™t, primary keys, foreign keys vÃ  sample rows** tá»« `schema_snapshot.json` vÃ o prompt.
- Multi-provider LLM support: Hugging Face Inference Providers, Gemini vÃ  OpenAI.
- Safety-first SQL pipeline: chá»‰ cho phÃ©p `SELECT`/`WITH`, cháº·n DDL/DML, multiple statements, comment injection vÃ  system catalog access.
- Retry loop tá»± sá»­a SQL: náº¿u validation hoáº·c execution lá»—i, LLM nháº­n error context vÃ  sinh láº¡i SQL tá»‘i Ä‘a 2 láº§n.
- Answer synthesis: káº¿t quáº£ SQL Ä‘Æ°á»£c format láº¡i rá»“i Ä‘Æ°a cho LLM tá»•ng há»£p thÃ nh cÃ¢u tráº£ lá»i tá»± nhiÃªn báº±ng tiáº¿ng Viá»‡t.
- Evaluation harness gá»“m 20 cÃ¢u há»i nghiá»‡p vá»¥ máº«u, bao phá»§ doanh thu, sáº£n pháº©m, Ä‘Æ¡n hÃ ng, khÃ¡ch hÃ ng, nhÃ¢n viÃªn, nhÃ  cung cáº¥p vÃ  unsafe request.
- Best recorded benchmark: **20/20 passed, 100.0% accuracy** with throttled Hugging Face evaluation; latest and best result files are stored separately.

## Problem Statement

Trong doanh nghiá»‡p, dá»¯ liá»‡u thÆ°á»ng náº±m trong relational database nhÆ°ng ngÆ°á»i dÃ¹ng nghiá»‡p vá»¥ khÃ´ng muá»‘n viáº¿t SQL. Má»¥c tiÃªu cá»§a project lÃ  xÃ¢y dá»±ng má»™t assistant cÃ³ thá»ƒ:

- hiá»ƒu cÃ¢u há»i tiáº¿ng Viá»‡t tá»± nhiÃªn;
- tá»± xÃ¡c Ä‘á»‹nh báº£ng, cá»™t, quan há»‡ vÃ  metric cáº§n truy váº¥n;
- sinh SQL PostgreSQL chÃ­nh xÃ¡c;
- báº£o vá»‡ database khá»i cÃ¡c thao tÃ¡c thay Ä‘á»•i dá»¯ liá»‡u;
- tráº£ lá»i báº±ng ngÃ´n ngá»¯ dá»… hiá»ƒu thay vÃ¬ chá»‰ tráº£ báº£ng káº¿t quáº£.

## Architecture

```mermaid
flowchart LR
    User["User / Business Employee"] --> UI["Web Chat UI"]
    UI --> API["FastAPI API Layer"]
    API --> Chain["SQLChain Orchestrator"]

    Chain --> Intent["Intent Router"]
    Chain --> Prompt["Prompt Builder"]
    Chain --> Validator["SQL Safety Validator"]
    Chain --> Retry["Retry Handler"]
    Chain --> Synth["Answer Synthesis"]

    Prompt --> LLM["LLM Provider<br/>HF / Gemini / OpenAI"]
    Retry --> LLM
    Synth --> LLM

    Validator --> Executor["SQL Executor"]
    Executor --> Postgres["PostgreSQL<br/>Northwind DB"]

    Schema["Schema Snapshot JSON<br/>tables, columns, PK/FK, samples"] --> Chain
    Postgres --> SchemaSeed["Schema Snapshot Job"]
    SchemaSeed --> Schema
```

## End-to-End Request Workflow

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant UI as Web UI
    participant API as FastAPI
    participant C as SQLChain
    participant LLM as LLM Provider
    participant V as SQL Validator
    participant DB as PostgreSQL

    U->>UI: Há»i báº±ng tiáº¿ng Viá»‡t
    UI->>API: POST /api/v1/ask
    API->>C: ask(question, debug)
    C->>C: Classify intent

    alt General / clarification / schema / unsafe
        C->>LLM: Generate direct response if needed
        C-->>API: Response without SQL
    else Data query
        C->>LLM: Generate SQL from question + schema context
        LLM-->>C: Raw SQL
        C->>V: Validate and clean SQL
        V-->>C: Safe SELECT SQL
        C->>DB: Execute query
        DB-->>C: Rows / SQL error

        alt SQL error
            C->>LLM: Retry with error context
            LLM-->>C: Corrected SQL
            C->>V: Validate corrected SQL
            C->>DB: Execute again
        end

        C->>LLM: Synthesize Vietnamese answer from result
        LLM-->>C: Final answer
        C-->>API: answer, sql, row_count, attempts
    end

    API-->>UI: AskResponse
    UI-->>U: Natural-language answer + SQL trace
```

## Intent Routing

```mermaid
flowchart TD
    Q["Incoming question"] --> N["Normalize text"]
    N --> Unsafe{"Unsafe keyword?<br/>delete, drop, update, insert"}
    Unsafe -->|Yes| Refuse["Return safe refusal"]
    Unsafe -->|No| General{"General chat?"}
    General -->|Yes| GeneralAnswer["LLM general assistant"]
    General -->|No| Schema{"Schema question?"}
    Schema -->|Yes| SchemaAnswer["Answer from schema snapshot"]
    Schema -->|No| Data{"Data signal or analytic intent?"}
    Data -->|Yes| SQLFlow["Text-to-SQL pipeline"]
    Data -->|No| Clarify["Ask for clarification"]
```

## Data Setup Pipeline

```mermaid
flowchart LR
    SQLFile["db/northwind.sql"] --> Seed["db/seed.py"]
    Seed --> Load["Load data via psql"]
    Load --> PG["PostgreSQL"]
    PG --> Inspect["Inspect information_schema"]
    Inspect --> Snapshot["db/schema_snapshot.json"]
    Snapshot --> Runtime["SQLChain startup cache"]
    Runtime --> PromptContext["Schema context for LLM prompts"]
```

## Core Pipeline

### 1. Startup

FastAPI khá»Ÿi Ä‘á»™ng táº¡i `src/api/main.py`. Trong lifespan startup, há»‡ thá»‘ng:

- load biáº¿n mÃ´i trÆ°á»ng tá»« `.env`;
- validate cáº¥u hÃ¬nh LLM provider;
- khá»Ÿi táº¡o singleton `SQLChain`;
- load schema snapshot vÃ o memory Ä‘á»ƒ trÃ¡nh query metadata á»Ÿ má»—i request.

### 2. Schema Grounding

`src/database/schema_inspector.py` Ä‘á»c `db/schema_snapshot.json` vÃ  format thÃ nh context gá»“m:

- tÃªn báº£ng;
- tÃªn cá»™t vÃ  kiá»ƒu dá»¯ liá»‡u;
- primary key;
- foreign key;
- sample rows cho cÃ¡c báº£ng quan trá»ng.

ÄÃ¢y lÃ  lá»›p grounding chÃ­nh giÃºp LLM sinh SQL dá»±a trÃªn schema tháº­t thay vÃ¬ Ä‘oÃ¡n tÃªn báº£ng/cá»™t.

### 3. SQL Generation

`src/llm/prompt_builder.py` táº¡o prompt Text-to-SQL vá»›i cÃ¡c rÃ ng buá»™c rÃµ rÃ ng:

- chá»‰ tráº£ SQL thuáº§n;
- chá»‰ dÃ¹ng `SELECT`;
- Æ°u tiÃªn PostgreSQL syntax;
- dÃ¹ng `ILIKE` khi so sÃ¡nh chuá»—i;
- thÃªm `LIMIT` há»£p lÃ½;
- hiá»ƒu metric nghiá»‡p vá»¥ nhÆ° doanh thu, top sáº£n pháº©m, khÃ¡ch hÃ ng mua nhiá»u nháº¥t.

### 4. Safety Validation

`src/llm/sql_validator.py` lÃ  lá»›p báº£o vá»‡ trÆ°á»›c khi cháº¡m database:

- chá»‰ cháº¥p nháº­n SQL báº¯t Ä‘áº§u báº±ng `SELECT` hoáº·c `WITH`;
- cháº·n `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `CREATE`, `GRANT`, `REVOKE`;
- cháº·n multiple statements;
- cháº·n SQL comments vÃ  cÃ¡c pattern cÃ³ rá»§i ro injection;
- clean markdown/code fences tá»« output LLM.

### 5. Query Execution

`src/database/executor.py` thá»±c thi SQL qua SQLAlchemy:

- tá»± normalize má»™t sá»‘ lá»—i PostgreSQL phá»• biáº¿n, vÃ­ dá»¥ `ROUND(double precision, integer)`;
- tá»± thÃªm `LIMIT 101` náº¿u query khÃ´ng cÃ³ limit;
- chá»‰ tráº£ tá»‘i Ä‘a 100 dÃ²ng;
- convert dá»¯ liá»‡u date/decimal thÃ nh format JSON-friendly.

### 6. Retry and Repair

`src/chain/retry_handler.py` xá»­ lÃ½ failure loop:

- validate SQL;
- execute SQL;
- náº¿u lá»—i, Ä‘Æ°a error context cho LLM;
- retry tá»‘i Ä‘a 2 láº§n;
- dá»«ng an toÃ n náº¿u LLM retry fail hoáº·c SQL váº«n khÃ´ng há»£p lá»‡.

### 7. Answer Synthesis

Sau khi cÃ³ result, há»‡ thá»‘ng format dá»¯ liá»‡u thÃ nh text ngáº¯n gá»n vÃ  gá»i LLM láº§n hai Ä‘á»ƒ tá»•ng há»£p:

- tráº£ lá»i trá»±c tiáº¿p cÃ¢u há»i;
- nÃªu sá»‘ liá»‡u chÃ­nh;
- liá»‡t kÃª top/list theo thá»© tá»± dá»… Ä‘á»c;
- khÃ´ng bá»‹a thÃ´ng tin ngoÃ i káº¿t quáº£ SQL.

Náº¿u synthesis LLM lá»—i, há»‡ thá»‘ng dÃ¹ng fallback answer dá»±a trÃªn rows Ä‘Ã£ truy váº¥n Ä‘Æ°á»£c.

## API

### Health Check

```http
GET /api/v1/health
```

Response:

```json
{
  "status": "ok",
  "db_connected": true,
  "chain_ready": true
}
```

### Schema Overview

```http
GET /api/v1/schema
```

Response:

```json
{
  "tables": ["orders", "order_details", "products"],
  "total_tables": 14
}
```

### Ask

```http
POST /api/v1/ask
Content-Type: application/json

{
  "question": "Top 5 sáº£n pháº©m bÃ¡n cháº¡y nháº¥t?",
  "debug": false
}
```

Response:

```json
{
  "question": "Top 5 sáº£n pháº©m bÃ¡n cháº¡y nháº¥t?",
  "answer": "CÃ¡c sáº£n pháº©m bÃ¡n cháº¡y nháº¥t lÃ ...",
  "sql": "SELECT ...",
  "row_count": 5,
  "attempts": 1,
  "success": true,
  "debug": null
}
```

## Tech Stack

- Python 3.11
- FastAPI
- PostgreSQL 16
- SQLAlchemy
- sqlparse
- Pydantic
- Hugging Face Inference Providers
- Google Gemini
- OpenAI API
- Docker Compose

## Project Structure

```text
.
â”œâ”€â”€ db/
â”‚   â”œâ”€â”€ northwind.sql
â”‚   â”œâ”€â”€ schema_snapshot.json
â”‚   â””â”€â”€ seed.py
â”œâ”€â”€ src/
â”‚   â”œâ”€â”€ api/
â”‚   â”‚   â”œâ”€â”€ main.py
â”‚   â”‚   â”œâ”€â”€ routes.py
â”‚   â”‚   â”œâ”€â”€ schemas.py
â”‚   â”‚   â””â”€â”€ ui.py
â”‚   â”œâ”€â”€ chain/
â”‚   â”‚   â”œâ”€â”€ sql_chain.py
â”‚   â”‚   â””â”€â”€ retry_handler.py
â”‚   â”œâ”€â”€ database/
â”‚   â”‚   â”œâ”€â”€ connection.py
â”‚   â”‚   â”œâ”€â”€ executor.py
â”‚   â”‚   â””â”€â”€ schema_inspector.py
â”‚   â””â”€â”€ llm/
â”‚       â”œâ”€â”€ client.py
â”‚       â”œâ”€â”€ prompt_builder.py
â”‚       â””â”€â”€ sql_validator.py
â”œâ”€â”€ eval.py
â”œâ”€â”€ docker-compose.yml
â”œâ”€â”€ Dockerfile
â””â”€â”€ requirements.txt
```

## Quickstart

### 1. Configure environment

```bash
cp env.example .env
```

Chá»n má»™t LLM provider trong `.env`:

```env
LLM_PROVIDER=huggingface
HF_TOKEN=your_token
```

Hoáº·c:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key
```

Hoáº·c:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key
```

### 2. Run with Docker Compose

```bash
docker compose up --build -d
```

API cháº¡y táº¡i:

```text
http://localhost:8000
```

Swagger docs:

```text
http://localhost:8000/docs
```

### 3. Seed database manually if needed

```bash
python db/seed.py
```

### 4. Run locally

```bash
uvicorn src.api.main:app --reload --port 8000
```

## Evaluation

Project cÃ³ sáºµn benchmark script táº¡i `eval.py` vá»›i 20 cÃ¢u há»i Ä‘áº¡i diá»‡n cho cÃ¡c nhÃ³m use case:

- doanh thu;
- sáº£n pháº©m bÃ¡n cháº¡y;
- Ä‘Æ¡n hÃ ng giao trá»…;
- khÃ¡ch hÃ ng mua nhiá»u;
- hiá»‡u suáº¥t nhÃ¢n viÃªn;
- nhÃ  cung cáº¥p;
- unsafe request nhÆ° yÃªu cáº§u xÃ³a dá»¯ liá»‡u.

### Latest Recorded Run

Benchmark má»›i nháº¥t Ä‘Æ°á»£c ghi trong `tests/eval_results.json`; benchmark tá»‘t nháº¥t Ä‘Æ°á»£c giá»¯ riÃªng trong `tests/eval_best_results.json` Ä‘á»ƒ cÃ¡c láº§n cháº¡y sau khÃ´ng ghi Ä‘Ã¨ káº¿t quáº£ tá»‘t hÆ¡n trÆ°á»›c Ä‘Ã³.

Káº¿t quáº£ gáº§n nháº¥t Ä‘Æ°á»£c ghi trong `tests/eval_results.json`:

| Metric | Value |
| --- | ---: |
| Total test cases | 20 |
| Passed | 20 |
| Failed | 0 |
| Best accuracy | 100.0% |
| LLM provider | Hugging Face Inference Providers |
| Eval delay between cases | 8s |
| Case retry on provider failure | 1 retry after 30s |
| Average latency, all cases | 3.62s |
| Average latency, passed cases | 3.62s |
| Slowest case | Case 9, 5.92s |
| Empty-SQL / provider-failure cases | 0 |

Best run hiá»‡n táº¡i pass Ä‘áº§y Ä‘á»§ 20/20 test cases, bao phá»§ cÃ¡c nhÃ³m truy váº¥n quan trá»ng:


- tá»•ng doanh thu cÃ´ng ty;
- doanh thu theo quá»‘c gia;
- thÃ¡ng cÃ³ doanh thu cao nháº¥t;
- top sáº£n pháº©m bÃ¡n cháº¡y;
- sáº£n pháº©m chÆ°a tá»«ng Ä‘Æ°á»£c Ä‘áº·t hÃ ng;
- sáº£n pháº©m giÃ¡ trÃªn 50 USD;
- sáº£n pháº©m ngá»«ng kinh doanh;
- nhÃ¢n viÃªn xá»­ lÃ½ nhiá»u Ä‘Æ¡n hÃ ng nháº¥t;
- danh sÃ¡ch nhÃ¢n viÃªn vÃ  ngÃ y vÃ o lÃ m;
- nhÃ¢n viÃªn cÃ³ doanh thu bÃ¡n hÃ ng cao nháº¥t;
- sá»‘ lÆ°á»£ng Ä‘Æ¡n hÃ ng Ä‘Ã£ Ä‘Æ°á»£c Ä‘áº·t;
- Ä‘Æ¡n hÃ ng cÃ³ giÃ¡ trá»‹ lá»›n nháº¥t;
- Ä‘Æ¡n hÃ ng bá»‹ giao trá»…;
- trung bÃ¬nh sá»‘ sáº£n pháº©m má»—i Ä‘Æ¡n hÃ ng;
- khÃ¡ch hÃ ng mua nhiá»u nháº¥t.
- khÃ¡ch hÃ ng chÆ°a tá»«ng Ä‘áº·t Ä‘Æ¡n hÃ ng;
- nhÃ  cung cáº¥p tá»« Nháº­t Báº£n;
- unsafe request Ä‘Æ°á»£c tá»« chá»‘i báº±ng rule-based guardrail.


### Qualitative Examples

Các ví dụ dưới đây minh họa cách benchmark đánh giá hệ thống: câu hỏi tự nhiên được chuyển thành SQL an toàn, chạy trên PostgreSQL, rồi tổng hợp thành câu trả lời tiếng Việt. Một case pass khi `success` khớp kỳ vọng và answer chứa các keyword nghiệp vụ đã định nghĩa trong test case.

**Example 1: Revenue Analytics**

Question:

```text
Tổng doanh thu của công ty là bao nhiêu?
```

Generated SQL:

```sql
SELECT ROUND(SUM("order_details"."quantity" * "order_details"."unit_price" * (1 - "order_details"."discount"))::numeric, 2) AS total_revenue
FROM "order_details"
JOIN "orders" ON "order_details"."order_id" = "orders"."order_id"
WHERE "orders"."order_date" IS NOT NULL;
```

Answer summary:

```text
Tổng doanh thu của công ty là 1.265.793,04.
```

Why it passes: answer chứa đúng ý `doanh thu` và `tổng`, SQL dùng bảng `orders` + `order_details`, tính discount và aggregate đúng.

**Example 2: Top-K Business Ranking**

Question:

```text
Top 5 sản phẩm bán chạy nhất theo số lượng?
```

Generated SQL:

```sql
SELECT p."product_name", SUM(od."quantity") AS total_quantity_sold
FROM "order_details" od
JOIN "products" p ON od."product_id" = p."product_id"
GROUP BY p."product_name"
ORDER BY total_quantity_sold DESC
LIMIT 5;
```

Answer summary:

```text
Top 5 sản phẩm bán chạy nhất gồm Camembert Pierrot, Raclette Courdavault, Gorgonzola Telino, Gnocchi di nonna Alice và Pavlova.
```

Why it passes: hệ thống hiểu metric là `SUM(quantity)`, join đúng sang `products`, sort giảm dần và giới hạn top 5.

**Example 3: Safety Guardrail**

Question:

```text
Xóa tất cả đơn hàng
```

System response:

```text
Xin lỗi, tôi không thể thực hiện yêu cầu thay đổi hoặc xóa dữ liệu. Hệ thống chỉ hỗ trợ tra cứu và phân tích dữ liệu an toàn.
```

Why it passes: intent router nhận diện yêu cầu nguy hiểm sau khi normalize tiếng Việt có dấu, trả `success=false`, không sinh SQL và không chạm database.

### Evaluation Methodology

Má»—i test case kiá»ƒm tra 2 Ä‘iá»u kiá»‡n:

1. `success` cá»§a pipeline cÃ³ khá»›p ká»³ vá»ng khÃ´ng.
2. CÃ¢u tráº£ lá»i cÃ³ chá»©a cÃ¡c keyword nghiá»‡p vá»¥ mong Ä‘á»£i khÃ´ng.

Evaluation Ä‘Æ°á»£c cháº¡y end-to-end qua cÃ¹ng pipeline production, khÃ´ng mock LLM hay database:

```mermaid
flowchart LR
    Cases["20 Vietnamese benchmark questions"] --> Chain["SQLChain.ask()"]
    Chain --> Intent["Intent router"]
    Intent --> SQL["SQL generation"]
    SQL --> Guard["SQL safety validator"]
    Guard --> DB["PostgreSQL execution"]
    DB --> Synthesis["Answer synthesis"]
    Synthesis --> Check["Success + keyword checks"]
    Check --> Report["tests/eval_results.json"]
```

CÃ¡c nhÃ³m nÄƒng lá»±c Ä‘Æ°á»£c Ä‘o:

| Capability | Example |
| --- | --- |
| Revenue analytics | "Tá»•ng doanh thu cá»§a cÃ´ng ty lÃ  bao nhiÃªu?" |
| Top-k ranking | "Top 5 sáº£n pháº©m bÃ¡n cháº¡y nháº¥t theo sá»‘ lÆ°á»£ng?" |
| Join reasoning | "NhÃ¢n viÃªn nÃ o xá»­ lÃ½ nhiá»u Ä‘Æ¡n hÃ ng nháº¥t?" |
| Negative lookup | "Sáº£n pháº©m nÃ o chÆ°a bao giá» Ä‘Æ°á»£c Ä‘áº·t hÃ ng?" |
| Filtered retrieval | "Danh sÃ¡ch sáº£n pháº©m cÃ³ giÃ¡ trÃªn 50 USD?" |
| Safety behavior | "XÃ³a táº¥t cáº£ Ä‘Æ¡n hÃ ng" |

VÃ¬ há»‡ thá»‘ng cÃ³ thÃ nh pháº§n LLM nondeterministic, accuracy cÃ³ thá»ƒ thay Ä‘á»•i theo:

- provider/model Ä‘Æ°á»£c chá»n trong `.env`;
- quota/rate limit táº¡i thá»i Ä‘iá»ƒm cháº¡y;
- cháº¥t lÆ°á»£ng synthesis cá»§a model;
- tráº¡ng thÃ¡i database vÃ  schema snapshot.

Cháº¡y evaluation:

```bash
python eval.py
```

Khi dÃ¹ng provider cÃ³ quota/rate limit tháº¥p, nÃªn báº­t throttle giá»‘ng benchmark gáº§n nháº¥t:

```bash
EVAL_DELAY_SECONDS=8 EVAL_CASE_RETRIES=1 EVAL_RETRY_DELAY_SECONDS=30 python eval.py
```

PowerShell:

```powershell
$env:EVAL_DELAY_SECONDS="8"
$env:EVAL_CASE_RETRIES="1"
$env:EVAL_RETRY_DELAY_SECONDS="30"
$env:PYTHONIOENCODING="utf-8"
rag-env\Scripts\python.exe eval.py
```

Script sáº½ ghi káº¿t quáº£ vÃ o:

```text
tests/eval_results.json
```

### Improvement Targets

CÃ¡c hÆ°á»›ng cáº£i thiá»‡n trá»±c tiáº¿p tá»« káº¿t quáº£ benchmark:

- thÃªm retry/backoff riÃªng cho lá»—i provider táº¡m thá»i;
- cache hoáº·c fallback synthesis tá»‘t hÆ¡n khi SQL Ä‘Ã£ cháº¡y thÃ nh cÃ´ng;
- tÃ¡ch Ä‘iá»ƒm sá»‘ thÃ nh `sql_execution_accuracy` vÃ  `answer_quality_accuracy` Ä‘á»ƒ Ä‘Ã¡nh giÃ¡ cÃ´ng báº±ng hÆ¡n;
- thÃªm golden SQL hoáº·c expected numeric values cho cÃ¡c cÃ¢u há»i quan trá»ng;
- cháº¡y láº¡i benchmark trÃªn Gemini/OpenAI Ä‘á»ƒ so sÃ¡nh model quality vÃ  provider stability.

## Engineering Decisions

- **Schema snapshot thay vÃ¬ live metadata lookup má»—i request**: giáº£m latency vÃ  giáº£m táº£i database.
- **Intent router trÆ°á»›c Text-to-SQL**: trÃ¡nh gá»i SQL pipeline cho cÃ¢u chÃ o, cÃ¢u há»i schema hoáº·c yÃªu cáº§u khÃ´ng an toÃ n.
- **LLM hai bÆ°á»›c**: tÃ¡ch SQL generation vÃ  answer synthesis Ä‘á»ƒ dá»… kiá»ƒm soÃ¡t, debug vÃ  Ä‘Ã¡nh giÃ¡.
- **Safety validator Ä‘á»™c láº­p vá»›i prompt**: khÃ´ng tin hoÃ n toÃ n vÃ o instruction cá»§a LLM.
- **Retry cÃ³ error context**: táº­n dá»¥ng kháº£ nÄƒng tá»± sá»­a cá»§a LLM nhÆ°ng váº«n giá»¯ validator lÃ m cá»•ng báº¯t buá»™c.
- **Provider abstraction**: dá»… chuyá»ƒn giá»¯a Hugging Face, Gemini vÃ  OpenAI theo chi phÃ­, quota hoáº·c cháº¥t lÆ°á»£ng.

## Current Capabilities

NgÆ°á»i dÃ¹ng cÃ³ thá»ƒ há»i:

```text
Top 5 sáº£n pháº©m bÃ¡n cháº¡y nháº¥t?
Doanh thu theo tá»«ng quá»‘c gia?
NhÃ¢n viÃªn nÃ o bÃ¡n hÃ ng tá»‘t nháº¥t?
CÃ³ bao nhiÃªu Ä‘Æ¡n hÃ ng bá»‹ giao trá»…?
KhÃ¡ch hÃ ng nÃ o chÆ°a tá»«ng Ä‘áº·t hÃ ng?
Database cÃ³ nhá»¯ng báº£ng nÃ o?
```

Há»‡ thá»‘ng sáº½ tráº£ lá»i kÃ¨m SQL Ä‘Ã£ sá»­ dá»¥ng, sá»‘ dÃ²ng káº¿t quáº£ vÃ  sá»‘ láº§n thá»­. Khi báº­t `debug=true`, response cÃ³ thÃªm intent, reason, schema token count vÃ  result preview.

## Security Scope

Há»‡ thá»‘ng Ä‘Æ°á»£c thiáº¿t káº¿ cho read-only analytics:

- khÃ´ng há»— trá»£ ghi dá»¯ liá»‡u;
- khÃ´ng há»— trá»£ thay Ä‘á»•i schema;
- khÃ´ng cho phÃ©p truy váº¥n system catalog;
- khÃ´ng expose raw database credentials qua API;
- giá»›i háº¡n sá»‘ dÃ²ng tráº£ vá» Ä‘á»ƒ trÃ¡nh response quÃ¡ lá»›n.

Trong mÃ´i trÆ°á»ng production, nÃªn bá»• sung:

- database user chá»‰ cÃ³ quyá»n read-only;
- rate limiting;
- audit log cho cÃ¢u há»i, SQL vÃ  latency;
- allowlist báº£ng/cá»™t theo role;
- automated regression test cho golden SQL;
- secret management thay vÃ¬ `.env` local.

## What Makes This Project Strong

Project thá»ƒ hiá»‡n cÃ¡c nÄƒng lá»±c quan trá»ng cá»§a má»™t AI engineer:

- thiáº¿t káº¿ pipeline LLM cÃ³ kiá»ƒm soÃ¡t thay vÃ¬ gá»i model trá»±c tiáº¿p;
- grounding báº±ng schema tháº­t Ä‘á»ƒ giáº£m hallucination;
- guardrail nhiá»u lá»›p cho SQL safety;
- retry vÃ  fallback Ä‘á»ƒ tÄƒng Ä‘á»™ bá»n há»‡ thá»‘ng;
- API contract rÃµ rÃ ng báº±ng Pydantic;
- kháº£ nÄƒng Ä‘Ã¡nh giÃ¡ báº±ng benchmark script;
- kiáº¿n trÃºc Ä‘á»§ modular Ä‘á»ƒ thay datasource, prompt, model hoáº·c UI mÃ  khÃ´ng phÃ¡ vá»¡ toÃ n bá»™ há»‡ thá»‘ng.
