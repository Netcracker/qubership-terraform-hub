# Kubernetes install

Collection of scripts, that provision new EKS clusters and infra componennts

## 🔍 Overview
**Automates EKS and Infra components installation:**

**Currently supported components:**
- EKS
- Postgres (pg-skipper)
- Consul
- Zookeeper
- Kafka

---

## 📘 How to use
1. Fork Repository
2. Fill in following secrets and variables:

| Type      | Name                               | Description                                                         |
|-----------|------------------------------------|---------------------------------------------------------------------|
| Secret    | AWS_ACCESS_KEY_ID                  | AWS credentials, used for cloud connection                          |
| Secret    | AWS_SECRET_ACCESS_KEY              | AWS credentials, used for cloud connection                          |
| Variable  | AWS_REGION                         | Region for new cluster                                              |
| Secret    | S3_STATE_STORAGE_ACCESS_KEY_ID     | Credentials for S3 bucket access (used for terraform state storage) |
| Secret    | S3_STATE_STORAGE_SECRET_ACCESS_KEY | Credentials for S3 bucket access (used for terraform state storage) |
| Variable  | S3_STATE_STORAGE_BUCKET_NAME       | Bucket name for terraform state storage)                            |
| Variable  | TF_VAR_EKS_NEW_CLUSTERNAME         | Name for new EKS cluster                                            |
| Variable  | TF_VAR_CONSUL_INSTALL_NAMESPACE    | Namespace, where Consul will be installed                           |
| Variable  | TF_VAR_PG_INSTALL_NAMESPACE        | Namespace, where Postgres will be installed                         |
| Secret    | POSTGRESUSER                       | Postgres admin user                                                 |
| Secret    | POSTGRESPASSWORD                   | Postgres admin password                                             |
| Secret    | REPLICATORPASSWOR                  | Postgres replicator user credentials                                |
| Variable  | TF_VAR_KAFKA_INSTALL_NAMESPACE     | Namespace, where Kafka will be installed                            |
| Variable  | TF_VAR_ZOOKEEPER_INSTALL_NAMESPACE | Namespace, where Zookeeper will be installed                        |

3. Navigate to Github Actions
4. Run workflow Kubernetes and Infra Install with required parameters, supported:
- EKS Install
- EKS Delete previously provisioned EKS cluster
- Install Consul
- Install Postgres
- Install Zookeeper
- Install Kafka
5. Use any appropriate tool for access (awscli for example)

---