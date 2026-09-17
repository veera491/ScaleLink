# ScaleLink Database Contract

Contract version: 1.0
Frozen: 2026-09-15

ScaleLink uses PostgreSQL.

For this coursework deployment, both microservices use one PostgreSQL
deployment to reduce Minikube resource usage.

Logical service responsibilities remain separated.

---

# Table: links

Schema:

    id          BIGSERIAL PRIMARY KEY
    short_code  VARCHAR(16) NOT NULL UNIQUE
    target_url  TEXT NOT NULL
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()

Purpose:

- id is the internal link identifier
- short_code is the externally visible shortened identifier
- target_url stores the destination
- created_at records creation time

short_code must be unique.

Required index:

    UNIQUE INDEX on links(short_code)

---

# Table: click_events

Schema:

    id          BIGSERIAL PRIMARY KEY
    link_id     BIGINT NOT NULL
    clicked_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    referrer    TEXT NULL
    user_agent  VARCHAR(32) NULL

Foreign-key relationship:

    click_events.link_id
        references links.id
        ON DELETE CASCADE

Required indexes:

    INDEX on click_events(link_id)
    INDEX on click_events(clicked_at)

---

# Logical ownership

Link Service owns application operations on:

    links

Analytics Service owns application operations on:

    click_events

The Link Service must not directly query click statistics.

The Analytics Service must not create, edit or delete shortened links.

Communication between the services occurs through REST.

---

# Persistence

PostgreSQL data in Kubernetes must use a PersistentVolumeClaim.

Container-local filesystem storage must not be considered persistent.

---

# Time handling

Database timestamps use:

    TIMESTAMPTZ

Application and API timestamps should be represented using UTC.

---

# Secrets

Database credentials must not be committed to Git.

Do not commit:

- .env
- actual passwords
- credential files
- database dumps containing credentials
- Kubernetes Secret manifests containing real credentials

Secrets will be supplied at runtime or deployment time.

Contract version: 1.0
