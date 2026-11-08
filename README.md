# DevTrack

## Project Overview

DevTrack is a full-stack Django project and issue management application inspired by Jira and Linear. It supports team collaboration, project membership, issue tracking, comments, and a JSON API with JWT authentication.

## Features

- User registration, login, and logout
- Project creation and ownership management
- Project membership management with roles
- Issue creation, assignment, status tracking, and priorities
- Comment threads and project-scoped access control
- Responsive dashboard with project and issue metrics
- REST API with JWT authentication, filtering, pagination, and docs

## Technology Stack

- Python 3.12+
- Django 5.2 LTS
- Django REST Framework
- django-filter
- Simple JWT
- drf-spectacular
- SQLite by default, PostgreSQL-ready config
- Bootstrap 5 + custom CSS

## Architecture

The project is organized into clear apps:

- `accounts`: user authentication and registration flow
- `projects`: project and membership models, permissions, and views
- `issues`: issue and comment models, forms, and views
- `dashboard`: overview and KPI calculations
- `api`: REST API, serializers, permissions, and docs
- `config`: project settings and URL routing

## Database Model Summary

### Project
- `name`, `description`, `owner`, timestamps
- Owners have full project control, including project details, members, issues, and project deletion
- Memberships tracked in `ProjectMembership`

### ProjectMembership
- Prevents duplicate membership records per project/user
- Stores `owner`, `manager`, or `member` role
- Managers can edit project details, manage members, and create, assign, edit, and delete project issues; they cannot delete projects or change ownership
- Members can view their projects, create issues and comments, and edit issues assigned to them

### Issue
- Belongs to a project
- Includes status, priority, reporter, assignee, due date
- Assignee must be either the project owner or a project member

### Comment
- Belongs to an issue and has an author
- Threaded discussion on issue detail pages

## Installation

### Windows PowerShell

```powershell
cd C:\path\to\devtrack
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

### Linux/macOS

```bash
cd /path/to/devtrack
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

## Environment Configuration

Copy `.env.example` to `.env` and replace the `DJANGO_SECRET_KEY` placeholder with a unique random value before running the app. Keep `.env` local; it is excluded from Git. The other values in the example are development defaults.

### `.env`

Example values:

```dotenv
DEBUG=True
DJANGO_SECRET_KEY=replace-with-a-unique-random-secret
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3
```

Generate a secret key with Django:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

To use PostgreSQL:

```dotenv
DATABASE_URL=postgresql://user:password@host:5432/devtrack
```

## Database Setup

```bash
python manage.py migrate
```

## Create a Superuser

```bash
python manage.py createsuperuser
```

## Running the App

### Local development server

```bash
python manage.py runserver
```

Open the app at:

- http://127.0.0.1:8000/

## Running Tests

```bash
python manage.py test
```

## API Endpoints

The API is mounted under `/api/v1/`.

### Authentication
- `POST /api/v1/auth/token/`
- `POST /api/v1/auth/token/refresh/`
- `POST /api/v1/auth/register/`

### Projects
- `GET /api/v1/projects/`
- `POST /api/v1/projects/`
- `GET /api/v1/projects/{id}/`
- `PUT /api/v1/projects/{id}/`
- `PATCH /api/v1/projects/{id}/`
- `DELETE /api/v1/projects/{id}/`
- `GET /api/v1/projects/{id}/members/`
- `POST /api/v1/projects/{id}/members/`
- `DELETE /api/v1/projects/{id}/members/{user_id}/`
- `PATCH /api/v1/projects/{id}/members/{user_id}/role/`

### Issues
- `GET /api/v1/issues/`
- `POST /api/v1/issues/`
- `GET /api/v1/issues/{id}/`
- `PUT /api/v1/issues/{id}/`
- `PATCH /api/v1/issues/{id}/`
- `DELETE /api/v1/issues/{id}/`

### Comments
- `GET /api/v1/issues/{id}/comments/`
- `POST /api/v1/issues/{id}/comments/`

## API Documentation

Swagger UI is available at:

- http://127.0.0.1:8000/api/docs/

OpenAPI schema: `http://127.0.0.1:8000/api/schema/`
ReDoc: `http://127.0.0.1:8000/api/redoc/`

## Authentication and Security

- Session authentication protects web pages.
- JWT authentication secures API requests; a Django web session alone does not authenticate API requests.
- Send API access tokens as `Authorization: Bearer <access_token>`. Protected API endpoints return HTTP 401 when no valid JWT is provided.
- Web views and API endpoints enforce role-based project authorization.
- Project owners and managers can manage project memberships; managers cannot modify the owner or assign the owner role.
- Django superusers retain access across projects.
- Objects are filtered by project access before use.
- Password validation is handled by Django's built-in validators.

## Screenshots

Screenshots are intentionally left as placeholders for future capture.

- Dashboard screenshot: pending
- Project list screenshot: pending
- Issue detail screenshot: pending

## Future Improvements

- Team activity feed
- Email notifications
- Sprint and roadmap views
- Bulk issue actions
- File attachments
- CI/CD automation for deployments

## Deployment

A basic deployment configuration is included via `Procfile` and `render.yaml`. These are suitable for a platform like Render or similar hosting services.

Do not treat this as an active production deployment, but the project is ready to be configured for deployment with environment variables and a PostgreSQL-backed database.
