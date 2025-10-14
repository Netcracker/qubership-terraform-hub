# Postgres Installation

## 🔍 Overview
**Automates Postgres DB installation into provisioned EKS cluster**

[PG Skipper](https://github.com/Netcracker/pgskipper-operator) is used as Postgres installation.

---

## 📘 How to use
1. Fork Repository
2. Fill in following secrets and variables:

| Type      | Name                               | Description                                 |
|-----------|------------------------------------|---------------------------------------------|
| Secret    | AWS_ACCESS_KEY_ID                  | AWS credentials, used for cloud connection  |
| Secret    | AWS_SECRET_ACCESS_KEY              | AWS credentials, used for cloud connection  |
| Variable  | AWS_REGION                         | Region, where EKS cluster is installed      |
| Variable  | TF_VAR_EKS_NEW_CLUSTERNAME         | Name of EKS cluster                         |
| Variable  | TF_VAR_PG_INSTALL_NAMESPACE        | Namespace, where Postgres will be installed |
| Secret    | POSTGRESUSER                       | Postgres admin user                         |
| Secret    | POSTGRESPASSWORD                   | Postgres admin password                     |
| Secret    | REPLICATORPASSWOR                  | Postgres replicator user credentials        |

3. Edit pg_skipper/values.yaml file according to your specific configuration needs, [additional documentation on parameters](https://github.com/Netcracker/pgskipper-operator/blob/main/docs/public/installation.md)
3. Navigate to Github Actions
4. Run workflow  
5. Postgres should be installed successfully.

---