# Clean Scraper API

## 🎯 Objetivo

Construir un API en FastAPI que:

-   Reciba una URL
-   Extraiga el contenido principal
-   Limpie el HTML
-   Normalice los recursos
-   Devuelva contenido estructurado en formato Markdown
-   Sea segura y robusta

No utiliza IA.\
No reconstruye diseño.\
No replica sitios.\
Solo extrae contenido limpio y estructurado.

------------------------------------------------------------------------

## 🧩 Endpoint Principal

### POST /scrape

### Request

``` json
{
  "url": "https://example.com"
}
```

------------------------------------------------------------------------

## 📦 Response

``` json
{
  "url": "https://example.com",
  "title": "Example Title",
  "description": "Meta description if available",
  "content_markdown": "# Title\n\nContent...",
  "images": [
    "https://example.com/image1.webp"
  ],
  "videos": [],
  "links": [
    "https://example.com/contact"
  ],
  "word_count": 1240
}
```

------------------------------------------------------------------------

## 🏗 Flujo Interno

1.  Validación de URL
2.  Protección contra SSRF
3.  Fetch con timeout y límites
4.  Eliminación de scripts y estilos
5.  Extracción de contenido principal
6.  Normalización de URLs
7.  Conversión a Markdown
8.  Respuesta estructurada

------------------------------------------------------------------------

## 🔒 Seguridad Obligatoria

-   Bloquear localhost y redes privadas
-   Solo permitir http/https
-   Timeout máximo
-   Límite de tamaño de respuesta
-   Rate limiting
-   Manejo correcto de errores

------------------------------------------------------------------------

## 🧼 Limpieza del Contenido

Eliminar:

-   `<script>`
-   `<style>`
-   `<noscript>`
-   Banners
-   Popups
-   Tracking
-   Navegación repetitiva

Conservar:

-   Títulos (H1--H6)
-   Párrafos
-   Listas
-   Tablas
-   Imágenes
-   Videos
-   Enlaces relevantes

------------------------------------------------------------------------

## 🧱 Arquitectura del Proyecto

    app/
      main.py
      routers/
        scrape.py
      services/
        fetcher.py
        extractor.py
        sanitizer.py
      models/
        request.py
        response.py

Separación clara de responsabilidades.\
Nada de lógica mezclada.

------------------------------------------------------------------------

## ⚙ Requisitos Técnicos

-   Async
-   Validación con Pydantic
-   Manejo centralizado de excepciones
-   Logging estructurado
-   Respuestas consistentes
-   No bloquear el event loop

------------------------------------------------------------------------

## 📈 Extensibilidad Futura

``` json
{
  "url": "...",
  "include_images": true,
  "include_links": true,
  "format": "markdown"
}
```

Permite evolucionar el servicio sin romper contrato.

------------------------------------------------------------------------

## 🚀 Resultado Esperado

Un servicio:

-   Seguro
-   Determinístico
-   Reutilizable
-   Escalable
-   Fácil de integrar
-   Sin dependencias innecesarias
