# ScaleLink Security

ScaleLink applies a small set of practical security controls appropriate for the coursework deployment. The controls reduce unnecessary exposure, validate untrusted input, constrain resource consumption, reduce container privileges, and provide controlled failure behaviour.

## Threats and mitigations

| Threat | Mitigation |
| --- | --- |
| Public database | PostgreSQL is exposed only through an internal Kubernetes ClusterIP/headless Service on port 5432. It has no NodePort or LoadBalancer. |
| Public Analytics API | The Analytics service uses ClusterIP only and is reachable internally through Kubernetes service discovery. |
| Credentials in manifests or application source | Database credentials and DATABASE_URL are supplied through the `scalelink-secrets` Kubernetes Secret using `secretKeyRef`. The repository contains only `secret.template.yaml` with deployment-time placeholders. |
| Secrets committed to Git | `.gitignore` excludes `.env` files and real Kubernetes secret manifest names such as `secret.yaml`, `secrets.yaml`, `*-secret.yaml`, and `*-secrets.yaml`. |
| Invalid or malicious URL input | The Link service validates `target_url` with Pydantic `HttpUrl`, applies a 2048-character limit, and rejects invalid or unsupported URL schemes with HTTP 422. |
| Resource exhaustion | Link, Analytics, and PostgreSQL have explicit CPU and memory requests and limits. |
| Failed or unhealthy application pods | Link and Analytics expose `/health` and `/ready`, which are configured as Kubernetes liveness and readiness probes. |
| Direct public database access | PostgreSQL has no NodePort or LoadBalancer exposure. |
| Excess container privileges | Link and Analytics explicitly run as non-root UID 10001, disable privilege escalation, drop all Linux capabilities, and use the RuntimeDefault seccomp profile. The PostgreSQL server process itself runs as non-root UID/GID 70. |
| Unexpected application errors | API operations use controlled exception handling and return defined HTTP responses instead of exposing raw database failures. Analytics failures during redirects are logged but do not prevent redirects. |

## Resource boundaries

The deployed resource configuration is intentionally modest because the development Kubernetes environment has limited capacity.

- Link: CPU request 100m, CPU limit 500m, memory request 128Mi, memory limit 256Mi.
- Analytics: CPU request 100m, CPU limit 500m, memory request 128Mi, memory limit 256Mi.
- PostgreSQL: CPU request 100m, CPU limit 500m, memory request 256Mi, memory limit 512Mi.

Resources are explicitly bounded, preventing individual services from consuming unlimited cluster capacity.

## Container privilege model

The Link and Analytics workloads use explicit Kubernetes security contexts:

- `runAsNonRoot: true`
- `runAsUser: 10001`
- `allowPrivilegeEscalation: false`
- all Linux capabilities dropped
- `seccompProfile: RuntimeDefault`

The PostgreSQL image has different startup behaviour. An interactive `kubectl exec` process may start as root, but inspection of `/proc/1/status` confirmed that the actual PostgreSQL server process (PID 1) runs with UID and GID 70. Forcing an arbitrary Kubernetes `runAsUser` value onto the database image was therefore avoided because it could interfere with the image's initialization and persistent-volume ownership behaviour without improving the privilege level of the database server itself.

## Secret-management limitation

Kubernetes Secrets provide separation between application configuration and sensitive credential values, but they should not be described as magical or complete encryption.

Their protection still depends on Kubernetes configuration, access control, cluster security, and how Secrets are stored and distributed. The ScaleLink repository therefore contains only a template with placeholder values and ignores local manifests containing real credentials.

For a production deployment, stronger secret management could use an external secret-management system with features such as centralized access control, credential rotation, auditing, and integration with Kubernetes workloads.

## Error handling and resilience

ScaleLink deliberately separates redirect availability from Analytics availability. If the Analytics service is unavailable or returns an error, the Link service records the failure in its logs but continues the redirect.

Database and API failures are converted into controlled responses such as HTTP 404, 422, 500, or 503 rather than exposing raw internal exceptions to clients.

## Scope

These controls are appropriate for the assessed local Kubernetes deployment. They do not claim that the Minikube environment is equivalent to a production Internet-facing platform. A production system could additionally introduce TLS termination, authentication and authorization where required, network policies, stronger secret management, centralized logging and monitoring, and production-grade database backup and recovery controls.