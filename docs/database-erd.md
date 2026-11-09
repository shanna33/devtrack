# DevTrack database ERD

This diagram is derived from the Django models in `projects/models.py` and `issues/models.py`. The user table is Django's built-in `auth_user` model; DevTrack does not define a custom user/profile model. Names below are Django's default database table names.

Only the built-in user fields relevant to the application relationships (`id`, `username`, and `email`) are shown; Django's other standard user fields are omitted for clarity.

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

## Relationship and constraint notes

- A project has one owner (`Project.owner`, cascading delete); a user can own multiple projects.
- `ProjectMembership` connects users and projects and stores `role` and `joined_at`. Its `(project, user)` pair is unique, so it acts as an explicit many-to-many join model without a declared `ManyToManyField`.
- An issue belongs to one project and has one reporter; both foreign keys cascade on deletion.
- An issue may have one assignee. The assignee foreign key is nullable and uses `SET_NULL` when the user is deleted.
- A comment belongs to one issue and one author; both foreign keys cascade on deletion.
- Deleting a project cascades through its memberships and issues; deleting an issue cascades to its comments.
- Issue indexes cover `(project, status)`, `(project, priority)`, and `(project, assignee)`.
