# Capabilities reference

Each section in `spec` enables a capability. Only declared sections are provisioned. Use these in help boxes or wizards when the user is editing a section.

---

## compute

**What it does:** Runs your app as an ECS Fargate service. Creates ECR repo, ECS cluster, target group, ALB listener rule, DNS, and Cloudflare Access.

**When to use:** Any service that needs a long-running container (web app, API, worker).

**Example:**

```yaml
spec:
  compute:
    port: 80
    cpu: 256
    memory: 512
    instances:
      min: 1
    healthCheck:
      path: /health
```

**Key fields:** `port`, `cpu`, `memory`, `instances.min`, `healthCheck.path`.

---

## storage

**What it does:** Provisions EFS (NFS) with mount targets and an access point. Containers or Lambdas can mount it at a path.

**When to use:** Shared filesystem for app data, uploads, or Lambda + ECS sharing.

**Example:**

```yaml
spec:
  storage:
    efs:
      encrypted: true
      lifecycle: AFTER_30_DAYS
      accessPoint:
        path: /data
        uid: 1000
        gid: 1000
```

**Key fields:** `efs.encrypted`, `efs.lifecycle`, `efs.accessPoint.path` / `uid` / `gid`.

---

## cache

**What it does:** Creates an ElastiCache Redis cluster (single node by default). Used for sessions, rate limiting, or job queues.

**When to use:** You need Redis.

**Example:**

```yaml
spec:
  cache:
    engine: redis
    nodeType: cache.t3.micro
    numNodes: 1
```

**Key fields:** `nodeType`, `numNodes`.

---

## database

**What it does:** Creates an RDS Postgres instance in the VPC. Not exposed to the internet.

**When to use:** Relational data store for the service.

**Example:**

```yaml
spec:
  database:
    engine: postgres
    instanceClass: db.t3.micro
    allocatedStorage: 20
```

**Key fields:** `instanceClass`, `allocatedStorage`. Optional: `dbName`, `dbUsername` (defaults from service name and `admin`).

---

## serviceDiscovery

**What it does:** Creates an AWS Cloud Map private DNS namespace (and a discovery service). Lets services find each other by name inside the VPC.

**When to use:** Multi-service or agent-style apps that resolve hostnames like `myservice.my-namespace.local`.

**Example:**

```yaml
spec:
  serviceDiscovery:
    namespace: myapp.local
```

**Key fields:** `namespace` (DNS name for the private namespace).

---

## lambda

**What it does:** Provisions Lambda functions from container images (ECR), with VPC and EFS mount. Creates a Function URL per function. **Requires `storage`** (EFS) to be declared.

**When to use:** Serverless endpoints or event handlers that share the same EFS as compute.

**Example:**

```yaml
spec:
  storage: { efs: {} }   # required for lambda
  lambda:
    functions:
      - name: my-fn
        image: my-fn-image
        memory: 2048
        timeout: 120
```

**Key fields per function:** `name`, `image` (ECR repo suffix), `memory`, `timeout`.

---

## triggers

**What it does:** Creates an EventBridge Scheduler schedule group and IAM role so you can create scheduled invocations (e.g. cron-style triggers for Lambdas). Optionally supports a webhook gateway concept in agent setups.

**When to use:** Scheduled jobs or time-based triggers.

**Example:**

```yaml
spec:
  triggers:
    eventbridge:
      scheduleGroup: my-schedules
```

**Key fields:** `eventbridge.scheduleGroup` (optional; defaults to service name).

---

## secrets

**Not a capability** — a list of secret names. The engine does not create secrets; it passes through environment variables with these names into the compute container (e.g. from CI or a secret manager). Declare the names so the engine knows what to inject.

```yaml
spec:
  secrets:
    - DATABASE_URL
    - API_KEY
```
