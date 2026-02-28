# Extractly

A FastAPI-based web-scraping API that extracts clean, structured Markdown content
from any web page – including modern JavaScript-rendered Single Page Applications
via the **Playground** endpoint.

---

## Table of Contents / Tabla de Contenidos

- [English Documentation](#english-documentation)
- [Documentación en Español](#documentación-en-español)
- [Roadmap](#roadmap)

---

## English Documentation

### Requirements

- Python 3.12+
- FastAPI 0.134.0
- Playwright 1.50.0 (for the Playground endpoint)

### Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

### Running the application

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.  
Interactive docs (Swagger UI) are available at `http://localhost:8000/docs`.

### Running with Docker

```bash
docker-compose up --build
```

### Endpoints

#### `POST /scrape` – Static scraper

Fetches a URL with a plain HTTP client and returns structured Markdown.

**Request body**

```json
{
  "url": "https://example.com",
  "include_images": true,
  "include_links": true,
  "format": "markdown"
}
```

**Response**

```json
{
  "url": "https://example.com",
  "title": "Example Title",
  "description": "Meta description if available",
  "content_markdown": "# Title\n\nContent...",
  "images": ["https://example.com/image.webp"],
  "videos": [],
  "links": ["https://example.com/about"],
  "word_count": 1240
}
```

Rate limit: **10 requests / minute**.

---

#### `POST /playground/scrape` – Dynamic scraper (Playground)

Renders the target URL in a headless **Chromium** browser so that
JavaScript-heavy / SPA pages are fully executed before content is extracted.

Accepts the same fields as `/scrape`, plus:

| Field | Type | Default | Description |
|---|---|---|---|
| `wait_for_selector` | `string \| null` | `null` | CSS selector to wait for before capturing HTML |
| `wait_ms` | `int` | `0` | Extra milliseconds to wait after page load (max 10 000) |

**Example request**

```json
{
  "url": "https://example-spa.com",
  "wait_for_selector": "#app",
  "wait_ms": 500
}
```

The response schema is identical to `/scrape`.

Rate limit: **5 requests / minute** (browser rendering is resource-intensive).

---

## Documentación en Español

### Requisitos

- Python 3.12+
- FastAPI 0.134.0
- Playwright 1.50.0 (para el endpoint Playground)

### Instalación

```bash
pip install -r requirements.txt
playwright install chromium
```

### Ejecución de la aplicación

```bash
uvicorn main:app --reload
```

La API estará disponible en `http://localhost:8000`.  
La documentación interactiva (Swagger UI) se encuentra en `http://localhost:8000/docs`.

### Ejecución con Docker

```bash
docker-compose up --build
```

### Endpoints

#### `POST /scrape` – Scraper estático

Descarga la URL con un cliente HTTP simple y devuelve Markdown estructurado.

**Cuerpo de la solicitud**

```json
{
  "url": "https://ejemplo.com",
  "include_images": true,
  "include_links": true,
  "format": "markdown"
}
```

**Respuesta**

```json
{
  "url": "https://ejemplo.com",
  "title": "Título de ejemplo",
  "description": "Meta descripción si está disponible",
  "content_markdown": "# Título\n\nContenido...",
  "images": ["https://ejemplo.com/imagen.webp"],
  "videos": [],
  "links": ["https://ejemplo.com/acerca-de"],
  "word_count": 1240
}
```

Límite de tasa: **10 solicitudes / minuto**.

---

#### `POST /playground/scrape` – Scraper dinámico (Playground)

Renderiza la URL destino en un navegador **Chromium** sin cabeza para que las
páginas JavaScript / SPA sean completamente ejecutadas antes de extraer el
contenido.

Acepta los mismos campos que `/scrape`, además de:

| Campo | Tipo | Por defecto | Descripción |
|---|---|---|---|
| `wait_for_selector` | `string \| null` | `null` | Selector CSS a esperar antes de capturar el HTML |
| `wait_ms` | `int` | `0` | Milisegundos extra a esperar tras la carga (máx. 10 000) |

**Ejemplo de solicitud**

```json
{
  "url": "https://ejemplo-spa.com",
  "wait_for_selector": "#app",
  "wait_ms": 500
}
```

El esquema de respuesta es idéntico al de `/scrape`.

Límite de tasa: **5 solicitudes / minuto** (el renderizado del navegador consume más recursos).

---

## Roadmap

### ✅ Done

- [x] Static HTTP scraper (`POST /scrape`) with SSRF protection, rate limiting, and structured Markdown output
- [x] HTML sanitization (removes scripts, ads, nav, banners, etc.)
- [x] Docker / docker-compose support
- [x] **Playground** dynamic scraper (`POST /playground/scrape`) powered by headless Chromium

### 🚧 Planned

- [ ] `format: "html"` and `format: "text"` output options for `/scrape` and `/playground/scrape`
- [ ] Screenshot capture option in Playground (`include_screenshot: true`)
- [ ] Configurable user-agent and viewport size for Playground
- [ ] Caching layer (Redis) to avoid redundant fetches of the same URL
- [ ] Webhook / callback support for long-running Playground scrapes
- [ ] Authentication (API key) for production deployments
- [ ] OpenTelemetry tracing
- [ ] Kubernetes Helm chart
