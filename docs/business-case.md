# ScaleLink Business Case for Cloud Computing

## Purpose

This analysis evaluates when a cloud-native Kubernetes deployment is justified for ScaleLink and when a simpler deployment would be more appropriate.

The business case is based on a workload that may change dramatically over time rather than remaining constant.

## Workload scenario

| Situation | Redirect traffic | Business meaning |
| --- | ---: | --- |
| Ordinary traffic | 100 redirects/min | Normal predictable demand |
| Viral event | 50,000 redirects/min | Sudden temporary demand spike |
| After the event | 300 redirects/min | Demand falls again after the spike |

The viral scenario represents a 500-fold increase from the ordinary traffic level.

A fixed deployment sized only for ordinary demand could become overloaded during the viral period.

A deployment permanently sized for the viral peak would waste capacity during normal periods.

This is the main business argument for elasticity.

## Independent scaling

ScaleLink separates Link and Analytics into different microservices.

The two services have different responsibilities and therefore do not necessarily require the same number of replicas.

An illustrative production scaling pattern could be:

| Component | Ordinary traffic | Viral traffic |
| --- | ---: | ---: |
| Link Service | 1 | 10 |
| Analytics Service | 1 | 4 |
| PostgreSQL | 1 | 1 |

These numbers illustrate the business value of independent scaling. They are not measured capacity claims for the coursework Minikube cluster.

The coursework deployment directly demonstrated independent scaling from 1 to 3 replicas for both application microservices.

## Why Link may scale more aggressively

The Link Service is on the critical user-facing request path.

Every redirect request reaches Link, so a viral URL directly increases Link traffic.

Its primary business objective is to resolve the short code and return the redirect with low delay.

During a traffic spike it may therefore need substantially more replicas.

## Why Analytics may scale differently

Analytics performs a different workload.

It receives click-event REST calls and stores analytics information.

Its resource requirements can differ from the Link Service, so forcing both services to use the same replica count would be inefficient.

Independent scaling allows capacity to be allocated according to the load of each service rather than scaling the whole application as one unit.

## PostgreSQL

PostgreSQL remains one persistent StatefulSet replica in the coursework architecture.

Scaling Link and Analytics does not automatically remove database limitations.

At very large production traffic levels the database could become a bottleneck and would require separate capacity planning, monitoring and possibly a more advanced database architecture.

## Business advantages of cloud-native deployment

### Elasticity

Cloud infrastructure can increase application capacity during a demand spike and reduce it again when demand falls.

This is valuable for ScaleLink because viral traffic may be temporary and difficult to predict.

### Independent resource allocation

Link and Analytics can receive different amounts of compute capacity.

For example, a viral event might justify approximately 10 Link instances but only 4 Analytics instances.

This avoids scaling every component to the same level.

### Automated recovery

Kubernetes Deployments automatically recreate failed application pods.

This reduces dependence on manual intervention when an individual container fails.

### Service discovery

Kubernetes Services provide stable internal names even when pods are recreated or scaled.

This reduces operational coupling to individual container IP addresses.

### Operational consistency

Declarative manifests describe deployments, services, autoscaling, resource constraints and health probes.

The evidence pack demonstrates that ScaleLink can be rebuilt from these manifests.

## Costs and disadvantages

Cloud-native architecture is not free simply because resources can autoscale.

Kubernetes introduces additional operational responsibilities including:

- cluster management;
- deployment configuration;
- networking and service discovery;
- security configuration;
- monitoring and logging;
- autoscaling configuration;
- upgrades and maintenance;
- persistent-storage management;
- troubleshooting distributed services.

Microservices also introduce network communication and distributed failure modes that do not exist in a single-process application.

Autoscaling can also increase cost quickly during unexpected load if limits and monitoring are poorly configured.

## Low-traffic counterexample

Consider a ScaleLink deployment receiving only 50 redirects per day.

For that workload Kubernetes would probably be unjustified.

A single VM or a single container deployment could be:

- simpler;
- cheaper;
- easier to understand;
- easier to monitor;
- easier to secure;
- easier to operate.

Running a Kubernetes platform for such a small stable workload could create more operational cost and complexity than business value.

The appropriate architecture therefore depends on the workload and business requirements.

## Decision comparison

| Situation | Appropriate direction | Reason |
| --- | --- | --- |
| 50 redirects/day, stable | Single VM/container | Minimal complexity and cost |
| Small predictable production workload | Simple container or small managed platform | Scaling requirements are limited |
| Moderate workload with growth | Cloud deployment may be justified | Easier capacity expansion and automation |
| Highly bursty or viral workload | Independent scalable services become valuable | Capacity can follow changing demand |
| Very high sustained traffic | Cloud-native architecture plus database redesign may be needed | Application scaling alone is insufficient |

## Total-cost perspective

A cloud decision should consider total cost rather than compute capacity alone.

Relevant costs include:

- compute;
- persistent storage;
- networking;
- backups;
- monitoring and logging;
- managed-service fees;
- engineering and operational time.

A technically sophisticated architecture can still be a poor business decision if its operating cost exceeds the value it provides.

## Critical limitation of the current design

The application microservices can scale independently, but PostgreSQL remains a single persistent database instance.

At sufficiently high traffic levels, increasing Link replicas from 1 to 10 would not guarantee ten times the application capacity because database throughput may become the limiting factor.

The current HPA also demonstrates CPU-based autoscaling rather than proving production sizing for 50,000 redirects per minute.

Therefore the viral-load numbers in this business case are planning examples, not benchmark results.

## Possible production evolution

If ScaleLink became a high-volume commercial service, further improvements could include:

- production load testing;
- database performance tuning or managed database services;
- database replication where appropriate;
- stronger monitoring and alerting;
- TLS and production ingress;
- external secret management;
- asynchronous event processing for analytics if required;
- cost controls and autoscaling guardrails.

These additions should be introduced only when business requirements justify their cost and complexity.

## Business conclusion

Cloud computing is valuable for ScaleLink when traffic is variable, unpredictable or large enough that elasticity, automated recovery and independent scaling provide measurable operational value.

The viral-link scenario demonstrates why independently scaling Link and Analytics can be more efficient than scaling the whole system uniformly.

However, cloud-native Kubernetes architecture is not automatically the best solution.

For a workload such as 50 redirects per day, a single VM or container would probably provide a better balance of cost, simplicity and operational effort.

The appropriate decision is therefore to use the simplest architecture that satisfies the expected workload, resilience, scalability and business requirements.
