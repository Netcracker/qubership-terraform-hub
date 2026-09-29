# Qubership Terraform Hub

A set of tools and scripts to install and manage various resources in AWS and Kubernetes. 

## 🔍 Overview
**Automates common AWS related tasks:**
- EKS provision
- Infrastructure installation
- EC2 instances management
- Scheduled start/stop of EC2/EKS resources

**🔑 Key pieces:**
- `components/terraform/<cloud>/k8s-cluster` – Terraform for provisioning/deleting a Kubernetes cluster in AWS (EKS), Google Cloud (GKE) or Azure (AKS), driven by [Atmos](https://atmos.tools) stacks in `stacks/` (see below).
- `ec2-scheduled` - Terraform code for managing state of EC2 instances (and EKS autoscaling groups).
- `Infrastructure components` - terraform and shell scripts to install supported infra components into EKS cluster.

---

## 📘 Documents
Documentation for individual tool/script can be found in docs folder, contents are:

| Component         | Purpose                                                  | Document                                              |
|-------------------|----------------------------------------------------------|-------------------------------------------------------|
| Kubernetes        | Provision VPC, EKS Cluster and infrastructure components | [Kubernetes Installation](docs/kubernetes-install.md) |
| EC2 Start         | Scheduled start of predefined EC2 instances              | [EC2 Start](docs/ec2-start.md)                        |
| EC2 Stop          | Scheduled stop of predefined EC2 instances               | [EC2 Stop](docs/ec2-stop.md)                         |
| EC2 Control       | Reusable workflow to on-demand start/stop EC2 Instance   | [EC2 Control](docs/ec2-control.md)                    |
| Postgres Install  | Install Postgres to EKS Cluster                          | [Postgres](docs/postgres.md)                          |
| Consul Install    | Install Consul to EKS Cluster                            | [Consul](docs/consul.md)                              |
| Zookeeper Install | Install Zookeeper to EKS Cluster                         | [Zookeeper](docs/zookeeper.md)                        |
| Kafka Install     | Install Kafka to EKS Cluster                             | [Kafka](docs/kafka.md)                                |
| Order New AWS Env | Order new AWS environment (instance or EKS cluster)      | [New_Env](docs/order_new_env.MD)                                |

---

## 🚀 Getting Started

1. **Fork the repository**
   - **Please note that secrets and variables will not be forked, please refer to individual components documentation for list of required variables and secrets** 

2. **Explore Workflows**
    - Browse the [`workflows/`](.github/workflows/) folder for individual workflows.
    - Browse the [`docs/`](docs/) folder for documentation on individual workflows.

3. **Use a Reusable Workflow***
   Call Action in your own workflow YAML, for example:
   ```yaml
   jobs:
     start-ec2:
       uses: Netcracker/qubership-terraform-hub/.github/workflows/ec2-control.yml@main
       with:
         instance_id: ${{ vars.AWS_GITHUB_RUNNER_ID }}
         action: 'start'
       secrets:
         AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
         AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
   ```

   > **Note:** Consult the individual workflow docs for specific input parameters and examples.

4. **Run locally with Atmos**
   Stacks are `<cloud>-<stage>`: `aws-dev`, `gcp-dev`, `azure-dev`. Each cluster gets its own Terraform workspace (state), named after `CLUSTER_NAME`.
   ```bash
   export CLUSTER_NAME=my-cluster
   atmos terraform plan k8s-cluster -s aws-dev    # or gcp-dev / azure-dev
   atmos terraform apply k8s-cluster -s aws-dev
   ```
   Credentials come from the usual env vars (`AWS_*`, `GOOGLE_APPLICATION_CREDENTIALS` + `GOOGLE_PROJECT`, `ARM_*`). Before first use of GCP/Azure, set the state bucket / storage account in `stacks/mixins/gcp.yaml` / `stacks/mixins/azure.yaml`.

   Full cluster + [ArgoCD](components/helmfile/argocd) lifecycle is in [stacks/workflows/k8s.yaml](stacks/workflows/k8s.yaml); Terraform/helm/helmfile are installed by the Atmos toolchain:
   ```bash
   export CLUSTER_NAME=my-cluster KUBECONFIG=/tmp/my-cluster.kubeconfig
   NODE_COUNT=4 atmos workflow deploy-cluster -f k8s -s aws-dev   # create / update / scale
   atmos workflow deploy-argocd -f k8s -s aws-dev                 # install / upgrade ArgoCD
   atmos workflow destroy -f k8s -s aws-dev
   ```
   In GitHub use the **Kubernetes Cluster (Atmos)** workflow ([k8s-cluster.yml](.github/workflows/k8s-cluster.yml)). Secrets per cloud: `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`; `GCP_CREDENTIALS` (service account JSON); `ARM_CLIENT_ID`/`ARM_CLIENT_SECRET`/`ARM_TENANT_ID`/`ARM_SUBSCRIPTION_ID`.

---

## 📘 Standards & Change Policy
Stable interface & evolution rules (naming, inputs/outputs, version pinning, minimal permissions, security and deprecation) are documented in [docs/standards-and-change-policy.md](docs/standards-and-change-policy.md).

---
## 🤝 Contributing

We welcome contributions from the community! To contribute:

1. Review and sign the [CLA](https://github.com/Netcracker/qubership-workflow-hub/blob/release/v2.2.0/CLA/cla.md).
2. Check the [CODEOWNERS](CODEOWNERS) file for areas of responsibility.
3. Open an issue to discuss your changes.
- For bug / feature / task use the <u>[Issue Guidelines](docs/issue-guidelines.md)</u> (required fields, templates, labels).
4. Submit a pull request with tests and documentation updates.

> IMPORTANT: Before opening an issue or pull request you MUST read the <u>[Contribution & PR Conduct](docs/code-of-conduct-prs.md)</u> and the <u>[Issue Guidelines](docs/issue-guidelines.md)</u>. They define required issue / PR fields, labels, and formatting.

---

## 📄 License

This project is licensed under the [Apache License 2.0](LICENSE)
