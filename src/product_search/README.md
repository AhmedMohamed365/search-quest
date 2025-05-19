# Product Search API

An efficient product search API using Django and PostgreSQL, designed to handle multilingual product searches with high accuracy and performance.

## Features

- **Advanced Search Functionality**:
  - Partial keyword matching
  - Misspelling tolerance
  - Multilingual support (English/Arabic)
  - Full-text search with PostgreSQL

- **Performance Optimizations**:
  - Rate limiting (30 requests per minute)
  - Response caching (5 minutes)
  - Efficient database queries using PostgreSQL search vectors

- **Advanced Filtering**:
  - Filter by category, brand
  - Filter by nutrition facts (calories, protein, etc.)

- **API Documentation**:
  - Swagger UI
  - ReDoc
  - DRF Browsable API

## Setup Instructions

1. Make sure PostgreSQL is installed and running
2. Install required packages:
   ```
   pip install -r requirements.txt
   ```
3. Configure PostgreSQL in settings.py
4. Run migrations:
   ```
   python manage.py migrate
   ```
5. Start the server:
   ```
   python manage.py runserver
   ```

## API Usage

### Versioned API Endpoints

The API follows versioning best practices with endpoints prefixed by `/api/v1/`.

### Search Products

```
GET /api/v1/products/search/?q=<search_term>
```

#### Parameters:

- `q` (required): Search query
- `category`: Filter by category
- `brand`: Filter by brand
- `max_calories`: Filter products with calories less than or equal to value
- `min_protein`: Filter products with protein greater than or equal to value

### Examples

1. Basic search:
   ```
   GET /api/v1/products/search/?q=chocolate
   ```

2. Search with filters:
   ```
   GET /api/v1/products/search/?q=chocolate&category=snacks&max_calories=200
   ```

3. Arabic search:
   ```
   GET /api/v1/products/search/?q=شوكولاتة
   ```

## Documentation

- Swagger UI: `/swagger/`
- ReDoc: `/redoc/`
- DRF Docs: `/docs/` 