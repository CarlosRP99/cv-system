# CV System

Sistema local para gestionar y generar CVs a partir de una base de conocimiento estructurada.

## Filosofia

El CV no es un documento que se edita. Es una **proyeccion** de tu base de conocimiento, filtrada y ordenada para una oferta laboral especifica.

- **Una sola fuente de verdad**: Toda tu informacion profesional esta en `kb/`
- **Sin duplicacion**: Skills y tecnologias se referencian por ID, no por nombre
- **Generacion automatica**: El CV se genera, nunca se edita manualmente
- **ATS-friendly**: Plantillas minimalistas, maximamente parseables

## Requisitos

- Python 3.10+
- PyYAML (`pip install pyyaml`)
- pdfplumber (`pip install pdfplumber`) — para parsear PDFs
- Pandoc (opcional, para generar PDF)

## Uso Rapido

```bash
# 0. Ingresar un CV desde PDF (auto-genera entradas en la KB)
python scripts/ingest_cv.py mi_cv.pdf
python scripts/ingest_cv.py mi_cv.pdf --dry-run   # solo previsualizar

# 1. Validar la base de conocimiento
python scripts/validate.py

# 2. Analizar una oferta laboral (acepta .md o .pdf)
python scripts/analyze.py offers/2026-07-techcorp-senior-backend.md
python scripts/analyze.py offers/2026-07-nttdata-data-engineer.pdf

# 3. Detectar gaps
python scripts/gaps.py 2026-07-techcorp-senior-backend

# 4. Generar el CV
python scripts/generate.py 2026-07-techcorp-senior-backend --lang both

# 5. Generar solo en un idioma
python scripts/generate.py 2026-07-techcorp-senior-backend --lang es
python scripts/generate.py 2026-07-techcorp-senior-backend --lang en

# 6. Generar sin PDF
python scripts/generate.py 2026-07-techcorp-senior-backend --lang both --no-pdf
```

## Estructura del Proyecto

```
cv-system/
├── kb/                          # Base de conocimiento
│   ├── profile.yaml             # Datos personales
│   ├── experience/              # Experiencias laborales
│   ├── projects/                # Proyectos
│   ├── education/               # Formacion academica
│   ├── certifications/          # Certificaciones
│   ├── skills/                  # Registro maestro de habilidades
│   └── technologies/            # Registro maestro de tecnologias
├── offers/                      # Ofertas laborales
├── templates/                   # Plantillas de CV
│   ├── es/                      # Plantillas en espanol
│   └── en/                      # Plantillas en ingles
├── outputs/                     # CVs generados
├── scripts/                     # Scripts CLI
├── config.yaml                  # Configuracion del sistema
└── requirements.txt             # Dependencias
```

## Formatos de Datos

### Profile (kb/profile.yaml)

```yaml
name: "Tu Nombre"
title:
  es: "Ingeniero de Software Senior"
  en: "Senior Software Engineer"
# ... contact info, summary, languages
```

### Experience (kb/experience/*.yaml)

```yaml
id: "exp-001"
company: "Empresa A"
role:
  es: "Desarrollador Full Stack"
  en: "Full Stack Developer"
# ... dates, highlights, skills_used (referenced by ID)
```

### Skills (kb/skills/skills.yaml)

```yaml
skills:
  - id: "python"
    name:
      es: "Python"
      en: "Python"
    category: "programming"
    level: "expert"
    years: 6
```

## Comandos CLI

| Comando | Descripcion |
|---------|-------------|
| `python scripts/ingest_cv.py <cv.pdf>` | Ingesta de CV desde PDF a la KB (auto-dedupe) |
| `python scripts/ingest_cv.py <cv.pdf> --dry-run` | Previsualizar ingesta sin escribir |
| `python scripts/validate.py` | Valida integridad de la base de conocimiento |
| `python scripts/analyze.py <oferta>` | Analiza una oferta (.md o .pdf) y extrae requisitos |
| `python scripts/gaps.py <nombre>` | Detecta gaps entre requisitos y experiencia |
| `python scripts/generate.py <nombre>` | Genera el CV (Markdown y PDF) |
| `python scripts/batch.py --list` | Lista todas las ofertas |
| `python scripts/batch.py` | Procesa ofertas pendientes |

## Configuracion

Edita `config.yaml` para:

- Cambiar idiomas por defecto
- Ajustar orden de secciones
- Limitar numero de experiencias/skills
- Configurar generacion de PDF
- Ajustar umbrales de gap detection

## Agregar Nueva Experiencia

1. Crear archivo en `kb/experience/003-nueva-empresa.yaml`
2. Usar el mismo formato que los archivos existentes
3. Referenciar skills por ID (agregar a `kb/skills/skills.yaml` si no existen)

## Ingesta de CVs desde PDF

En lugar de crear archivos YAML manualmente, podés ingestar un CV en PDF:

```bash
# Previsualizar qué se va a extraer (no escribe nada)
python scripts/ingest_cv.py mi_cv.pdf --dry-run

# Ingresar directamente a la KB
python scripts/ingest_cv.py mi_cv.pdf
```

**Qué hace:**
- Extrae texto del PDF con pdfplumber
- Detecta secciones: perfil, experiencia, skills, educación, certificaciones
- Auto-genera IDs secuenciales (`exp-002`, `edu-002`, etc.)
- Deduplicación automática (no crea entradas que ya existen)
- Matching de skills contra 60+ tecnologías conocidas
- Merge de profile (no sobrescribe datos existentes)
- Ejecuta `validate.py` al final para confirmar integridad

**Formatos de PDF soportados:**
- CVs con secciones claras (EXPERIENCE, EDUCATION, SKILLS, etc.)
- CVs en español o inglés
- Texto seleccionable (no escaneados/imagen)

## Ofertas Laborales en PDF

`analyze.py` ahora acepta archivos PDF además de Markdown:

```bash
# Analizar oferta en PDF
python scripts/analyze.py offers/mi-oferta.pdf

# El texto extraído se guarda en outputs/<nombre>/raw.txt para debugging
```

**Formato esperado del PDF:**
- Secciones `## Requisitos` / `## Valorable` (o equivalentes en inglés)
- Items con bullet points (`-`, `•`, `*`) o texto plano por línea
- El script detecta automáticamente empresa y puesto del encabezado

## Generar PDF

El sistema usa Pandoc con XeLaTeX para generar PDFs:

```bash
# Instalar Pandoc (Windows)
winget install JohnMacFarlane.Pandoc

# Instalar TeX (necesario para XeLaTeX)
# Descargar MiKTeX: https://miktex.org/download
```

## License

MIT
