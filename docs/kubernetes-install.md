# Kubernetes install

Provision a Kubernetes cluster on AWS (EKS), Azure (AKS) or Google Cloud (GKE) and deploy infrastructure apps into it.
Everything is driven by [Atmos](https://atmos.tools): Terraform for the cluster, Helmfile for everything inside it.

## 🔍 Overview

Two independent layers, each with its own GitHub workflow:

| Layer   | Workflow                                                          | What it does                                                                                              |
|---------|-------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| Cluster | [Kubernetes Cluster (Atmos)](../.github/workflows/k8s-cluster.yml) | Create / update / scale / destroy the cluster and apply the cluster baseline                              |
| Apps    | [Kubernetes Apps (Atmos)](../.github/workflows/k8s-apps.yml)       | Deploy / upgrade / remove apps on an existing cluster, dependencies first                                 |

**The cluster looks the same on every cloud.** The baseline ([components/helmfile/cluster-base](../components/helmfile/cluster-base)) adds:

- StorageClass `default-rwo` (default class, `WaitForFirstConsumer`, expandable) — the only cloud-specific part is the CSI driver behind it, set in `stacks/mixins/<cloud>.yaml`;
- cert-manager.

Apps only rely on that baseline, so their configuration is identical on every cloud.

## 📦 Apps

Registry: [stacks/catalog/apps.yaml](../stacks/catalog/apps.yaml) (chart, pinned version, namespace, dependencies).
Values: [components/helmfile/apps/values](../components/helmfile/apps/values) (`<app>.yaml`, or `<app>.yaml.gotmpl` when env is needed).

| App        | Chart                                                                                    | Namespace  | Needs                     |
|------------|------------------------------------------------------------------------------------------|------------|---------------------------|
| argocd     | [argo-cd](https://github.com/argoproj/argo-helm/tree/main/charts/argo-cd)                | argocd     |                           |
| consul     | [qubership-consul](https://github.com/Netcracker/qubership-consul)                       | consul     |                           |
| zookeeper  | [qubership-zookeeper](https://github.com/Netcracker/qubership-zookeeper)                 | zookeeper  |                           |
| kafka      | [qubership-kafka](https://github.com/Netcracker/qubership-kafka)                         | kafka      | zookeeper                 |
| postgres   | [pgskipper-operator](https://github.com/Netcracker/pgskipper-operator) (patroni-core)    | postgres   |                           |
| rabbitmq   | [qubership-rabbitmq](https://github.com/Netcracker/qubership-rabbitmq)                   | rabbitmq   |                           |
| opensearch | [qubership-opensearch](https://github.com/Netcracker/qubership-opensearch)               | opensearch |                           |
| dbaas      | [qubership-dbaas](https://github.com/Netcracker/qubership-dbaas)                         | dbaas      | postgres                  |
| mistral    | [qubership-mistral-operator](https://github.com/Netcracker/qubership-mistral-operator)   | mistral    | postgres, kafka, rabbitmq |
| monitoring | [qubership-monitoring-operator](https://github.com/Netcracker/qubership-monitoring-operator) | monitoring |                       |
| arangodb   | [kube-arangodb](https://github.com/arangodb/kube-arangodb) + ArangoDeployment            | arangodb   |                           |
| cassandra  | [k8ssandra-operator](https://github.com/k8ssandra/k8ssandra-operator) + K8ssandraCluster | cassandra  | cert-manager (baseline)   |

`mistral` is disabled (`installed: false`): its chart references an undefined template `mistral.operatorImage` in every release.

To add an app: add an entry to the registry and, if needed, `components/helmfile/apps/values/<app>.yaml`.

## 📘 How to use

1. Fill in secrets (GitHub environment, `dev` by default):

| Cloud / app | Secrets                                                                                                   |
|-------------|-----------------------------------------------------------------------------------------------------------|
| AWS         | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (variable `AWS_REGION`, default `us-east-1`)               |
| Azure       | `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID`                             |
| GCP         | `GCP_CREDENTIALS` (service account JSON)                                                                  |
| argocd      | `ARGOCD_ADMIN_PASSWORD` (optional; otherwise generated)                                                  |
| postgres    | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `REPLICATOR_PASSWORD` (optional; dev defaults otherwise)           |
| dbaas       | `BACKUP_DAEMON_DBAAS_ACCESS_PASSWORD`, `DBAAS_CLUSTER_DBA_CREDENTIALS_PASSWORD`, `DBAAS_TENANT_PASSWORD`, `DBAAS_DB_EDITOR_CREDENTIALS_PASSWORD`, `DISCR_TOOL_USER_PASSWORD` (optional; dev defaults otherwise) |

2. Run **Kubernetes Cluster (Atmos)**: `cloud`, `cluster_name`, `action=deploy` (`node_count` / `instance_type` to scale).
3. Run **Kubernetes Apps (Atmos)**: same `cloud` / `cluster_name`, `apps` (e.g. `kafka,postgres` or `all`), `action=diff`, then `deploy`.
4. Tear down with **Kubernetes Cluster (Atmos)** `action=destroy`: removes apps, their volumes, the baseline and the cluster.

The same from a shell (credentials in env):

```bash
export CLUSTER_NAME=my-cluster KUBECONFIG=/tmp/my-cluster.kubeconfig
atmos workflow deploy-cluster -f k8s -s aws-dev                  # cluster + baseline
APPS=kafka,postgres atmos workflow deploy-apps -f apps -s aws-dev
atmos workflow destroy -f k8s -s aws-dev
```
