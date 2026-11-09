# DevTrack

DevTrack is a Django application for organizing projects, tracking issues, and collaborating with project members. It provides server-rendered web pages and a Django REST Framework API.

| | |
|---|---|
| **Live application** | [devtrack-vhop.onrender.com](https://devtrack-vhop.onrender.com/) |
| **Source repository** | [github.com/shanna33/devtrack](https://github.com/shanna33/devtrack) |

The live application requires an account to view the workspace.

## Application Screenshots

| Dashboard | Projects |
|---|---|
| Project overview and recent activity. | Browse and manage project workspaces. |
| ![DevTrack dashboard](docs/screenshots/dashboard.png) | ![DevTrack projects](docs/screenshots/projects.png) |

| Project detail and issues | Project members |
|---|---|
| Review project information and its issue list. | Manage project access and member roles. |
| ![DevTrack project detail and issues](docs/screenshots/project-detail.png) | ![DevTrack project members](docs/screenshots/members.png) |

| Issue detail | Swagger API documentation |
|---|---|
| Inspect an issue and its discussion. | Explore the documented REST API. |
| ![DevTrack issue detail](docs/screenshots/issue-detail.png) | ![DevTrack Swagger documentation](docs/screenshots/swagger.png) |

## Features

- Register an account and sign in to a personal dashboard.
- Create projects, view project issues, and manage project membership.
- Use project roles: owner, manager, and member.
- Create, assign, search, filter, update, and track issues by status and priority.
- Add comments to issues.
- Search for eligible users when adding project members. Search is project-scoped and available to project owners and managers.
- Use the REST API with JWT authentication, filters, search, ordering, and page-number pagination.
- Browse the generated OpenAPI schema with Swagger UI or ReDoc.

## Technology stack

| Area | Implementation |
|---|---|
| Language and web framework | Python, Django 5.2 |
| API | Django REST Framework |
| API authentication | Simple JWT |
| API schema and UI | drf-spectacular (OpenAPI, Swagger UI, ReDoc) |
| Filtering | django-filter and DRF search/ordering filters |
| Database | SQLite by default; PostgreSQL through `DATABASE_URL` |
| Static assets | Django static files and WhiteNoise |
| Production application server | Gunicorn |
| Frontend | Django templates, Bootstrap 5.3.3, and project CSS |
| Hosting configuration | Render Blueprint (`render.yaml`) |

The dependency list is maintained in [requirements.txt](requirements.txt). The repository does not pin a separate Python runtime version.

## Application architecture

The Django project package is `config`; the domain and presentation code is organized into these installed applications:

| Application | Responsibility |
|---|---|
| `accounts` | Registration, login, and logout pages using Django authentication. |
| `dashboard` | Authenticated home page and project/issue summary metrics. |
| `projects` | Project and membership models, project pages, member management, and project-role checks. |
| `issues` | Issue and comment models, forms, pages, filtering, and issue-level access rules. |
| `api` | DRF serializers, viewsets, API endpoints, permissions, and project-scoped member search. |
| `config` | Settings, root URL configuration, and WSGI/ASGI entry points. |

Web pages are rendered with Django templates under `templates/`; shared styling and browser assets are under `static/`. The API is mounted separately at `/api/v1/`.

## Database design

The application uses Django's built-in `django.contrib.auth.models.User`; it does not define a custom user or profile model. The principal application models are `Project`, `ProjectMembership`, `Issue`, and `Comment`.

`ProjectMembership` is an explicit association model between a user and a project. It stores the role and join timestamp, and a database uniqueness constraint prevents duplicate `(project, user)` rows. This provides a user-to-project many-to-many relationship through a model, rather than a declared `ManyToManyField`. The ERD shows only the built-in user fields relevant to these relationships.

Important relationship and deletion behavior:

- Deleting a project cascades to its memberships and issues; deleting an issue cascades to its comments.
- Deleting a user cascades to their owned projects, memberships, reported issues, and comments.
- Deleting an issue assignee sets `Issue.assignee` to `NULL`, preserving the issue.
- The issue model defines indexes on `(project, status)`, `(project, priority)`, and `(project, assignee)`.

### Database ERD

The diagram reflects the Django model foreign keys, the nullable assignee, and the unique project/user membership constraint. Django's default table names are shown.

```mermaid
erDiagram
    auth_user {
        BIGINT id PK
        VARCHAR username
        VARCHAR email
    }

    projects_project {
        BIGINT id PK
        VARCHAR name
        TEXT description
        BIGINT owner_id FK
        DATETIME created_at
        DATETIME updated_at
    }

    projects_projectmembership {
        BIGINT id PK
        BIGINT project_id FK
        BIGINT user_id FK
        VARCHAR role
        DATETIME joined_at
    }

    issues_issue {
        BIGINT id PK
        BIGINT project_id FK
        VARCHAR title
        TEXT description
        VARCHAR status
        VARCHAR priority
        BIGINT reporter_id FK
        BIGINT assignee_id FK "nullable"
        DATE due_date "nullable"
        DATETIME created_at
        DATETIME updated_at
    }

    issues_comment {
        BIGINT id PK
        BIGINT issue_id FK
        BIGINT author_id FK
        TEXT content
        DATETIME created_at
        DATETIME updated_at
    }

    auth_user ||--o{ projects_project : owns
    projects_project ||--o{ projects_projectmembership : has
    auth_user ||--o{ projects_projectmembership : joins
    projects_project ||--o{ issues_issue : contains
    auth_user ||--o{ issues_issue : reports
    auth_user o|--o{ issues_issue : assigned_to
    issues_issue ||--o{ issues_comment : has
    auth_user ||--o{ issues_comment : writes
```

`ProjectMembership` has a unique constraint on `(project_id, user_id)`. The diagram's `assignee_id` is nullable and uses `SET_NULL`; the other model foreign keys use cascading deletion. A standalone copy of this ERD is available at [docs/database-erd.md](docs/database-erd.md).

## Authentication and authorization

- Web views use Django session authentication. Registration, login, and logout are at `/accounts/register/`, `/accounts/login/`, and `/accounts/logout/`.
- The REST API defaults to JWT authentication and authenticated access. Obtain an access/refresh token pair at `POST /api/v1/auth/token/`; refresh an access token at `POST /api/v1/auth/token/refresh/`.
- Send API access tokens as `Authorization: Bearer <access-token>`.
- The project member-search endpoint also accepts Django session authentication for use by the signed-in web member-management page.
- Project access is limited to the owner, project members, and Django superusers. Project queries are scoped to projects the requester may access.
- Owners and managers can edit project details and manage project members and issues. Only owners and superusers can delete projects.
- Members can participate in accessible projects. A member can edit issues assigned to them; managers and owners can edit issues in their projects.
- Issue assignees are validated against the project owner and membership roster. Comment access is likewise scoped to accessible projects; authors and project managers can edit/delete comments.
- Role and object permissions are enforced server-side. The member-search endpoint separately requires an authenticated project owner or manager.

## API documentation and endpoints

The API is rooted at `/api/v1/`. On the live application, the documentation pages are:

- [Swagger UI](https://devtrack-vhop.onrender.com/api/docs/)
- [OpenAPI schema](https://devtrack-vhop.onrender.com/api/schema/)
- [ReDoc](https://devtrack-vhop.onrender.com/api/redoc/)

The same paths are available on a local server at `http://127.0.0.1:8000/`. The API exposes the following routes:

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/auth/register/` | Register a user. |
| `POST` | `/api/v1/auth/token/` | Obtain JWT access and refresh tokens. |
| `POST` | `/api/v1/auth/token/refresh/` | Refresh an access token. |
| `GET`, `POST` | `/api/v1/projects/` | List accessible projects or create a project. |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/api/v1/projects/{project_id}/` | Retrieve, update, or delete a project, subject to role permissions. |
| `GET`, `POST` | `/api/v1/projects/{project_id}/members/` | View project memberships or add a member. |
| `DELETE` | `/api/v1/projects/{project_id}/members/{user_id}/` | Remove a project member. |
| `PATCH` | `/api/v1/projects/{project_id}/members/{user_id}/role/` | Change a member's role. |
| `GET` | `/api/v1/projects/{project_id}/members/search/?q={username}` | Search eligible users to add (owners/managers only; at least two characters; up to 10 matches). |
| `GET`, `POST` | `/api/v1/issues/` | List accessible issues or create an issue in an accessible project. |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/api/v1/issues/{issue_id}/` | Retrieve, update, or delete an issue, subject to permissions. |
| `GET`, `POST` | `/api/v1/issues/{issue_id}/comments/` | List or add comments on an accessible issue. |
| `GET`, `POST` | `/api/v1/comments/` | List accessible comments or create a comment. |
| `GET`, `PUT`, `PATCH`, `DELETE` | `/api/v1/comments/{comment_id}/` | Retrieve, update, or delete an accessible comment. |

Project list filters include `owner`; project search covers `name` and `description`; project ordering supports `created_at`, `updated_at`, and `name`. Issue filters include `project`, `status`, `priority`, and `assignee`; issue search covers `title` and `description`; issue ordering supports `created_at`, `updated_at`, `due_date`, and `priority`. DRF page-number pagination is configured with 20 results per page for paginated list views. Use `?page=2` to request another page, `?search=...` for search, and `?ordering=...` for ordering.

## Local installation

Clone the repository and create a virtual environment. Python 3.12 is a suitable development runtime; the repository does not declare a separate Python support range.

### Windows (PowerShell)

```powershell
git clone https://github.com/shanna33/devtrack.git
Set-Location devtrack
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

### Linux or macOS

```bash
git clone https://github.com/shanna33/devtrack.git
cd devtrack
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

If Python 3.12 is not available on your system, use an installed Python release supported by the pinned Django 5.2 dependency and your platform's PostgreSQL driver.

## Environment variables

`config.settings` loads `.env` from the repository root. Set a unique secret key before using the application beyond local development.

| Variable | Required | Behavior |
|---|---|---|
| `DJANGO_SECRET_KEY` | Yes | Django secret key. The settings module raises an error if it is missing. |
| `DEBUG` | No | Defaults to `True`; set to `false` in deployment. |
| `ALLOWED_HOSTS` | No | Comma-separated hostnames. Local defaults are `localhost,127.0.0.1`; wildcard hosts are rejected. |
| `DATABASE_URL` | No | Database URL parsed by `dj-database-url`; defaults to SQLite at `db.sqlite3`. |
| `CSRF_TRUSTED_ORIGINS` | No | Optional comma-separated trusted origins. |
| `RENDER_EXTERNAL_HOSTNAME` | Render-provided | When present, disables debug, adds the Render hostname to allowed hosts, and trusts its HTTPS origin. |

Example local `.env`:

```dotenv
DEBUG=True
DJANGO_SECRET_KEY=replace-with-a-unique-secret
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3
```

Generate a secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

For PostgreSQL, set `DATABASE_URL` to a connection URL, for example:

```dotenv
DATABASE_URL=postgresql://devtrack_user:change-me@localhost:5432/devtrack
```

Do not commit `.env` or production credentials.

## Database setup and migrations

Apply migrations, optionally create an administrator account, and start the development server:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The local application is served at [http://127.0.0.1:8000/](http://127.0.0.1:8000/). Use `python manage.py check` to run Django's system checks.

## Automated tests

Run the Django test suite from the repository root with the virtual environment activated:

```bash
python manage.py test
```

To run a focused app suite, pass its Django app or test module, for example:

```bash
python manage.py test projects.test_member_management
```

## Deployment architecture (Render)

The checked-in [render.yaml](render.yaml) Blueprint describes a Python web service and a PostgreSQL database. The web service installs `requirements.txt`, applies migrations, and runs `collectstatic` as part of its build command. It starts the Django WSGI application with Gunicorn (`config.wsgi:application`) on Render's `$PORT`.

Render supplies `DATABASE_URL` from the provisioned database and generates `DJANGO_SECRET_KEY`; the Blueprint sets `DEBUG` to `false`. When `RENDER_EXTERNAL_HOSTNAME` is available, `config.settings` applies HTTPS-related host and CSRF settings. In production, WhiteNoise middleware serves static files collected into `staticfiles/`, using compressed manifest storage. The database is configured with `dj-database-url` and PostgreSQL's `psycopg2-binary` driver.

To deploy from Render, create a Blueprint from the repository and review the service/database plan and environment settings in Render before applying it. The live application link above points to the currently configured deployment.

## Future improvements

- Add CI automation for Django checks and the test suite.
- Capture and maintain screenshots for the documentation.
- Consider adding user-facing notifications and project activity history.
- Evaluate additional issue workflows, such as bulk actions or roadmap views.
