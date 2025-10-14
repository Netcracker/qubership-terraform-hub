# Consul Installation

## 🔍 Overview
**Automates [Consul](https://github.com/Netcracker/qubership-consul) installation into provisioned EKS cluster**

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
| Variable  | TF_VAR_CONSUL_INSTALL_NAMESPACE    | Namespace, where Consul will be installed   |

3. Edit consul/example-config.yaml file according to your specific configuration needs, [additional documentation on parameters](https://github.com/Netcracker/qubership-consul/blob/main/docs/public/installation.md)
3. Navigate to Github Actions
4. Run workflow
5. Consul should be installed successfully.

---