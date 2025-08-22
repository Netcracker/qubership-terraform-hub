# Qubership Terraform Hub

A set of tools and scripts to install and manage various resources in AWS and Kubernetes. 

## 🔍 Overview
**Automates common AWS related tasks:**
- EKS provision
- Infrastructure installation
- EC2 instances management
- Scheduled start/stop of EC2/EKS resources

**🔑 Key pieces:**
- `kubernetes-terraform` – Set of Terraform code for provisioning/deleting EKS cluster (Optional infrastructure components installation withing same workflow).
- `ec2-scheduled` - Terraform code for managing state of EC2 instances (and EKS autoscaling groups).
- `Infrastructure components` - terraform and shell scripts to install supported infra components into EKS cluster.

---

## 📘 Documents
Documentation for individual tool/script can be found in docs folder, contents are:

| Component         | Purpose                                                  | Document                                              |
|-------------------|----------------------------------------------------------|-------------------------------------------------------|
| Kubernetes        | Provision VPC, EKS Cluster and infrastructure components | [Kubernetes Installation](docs/kubernetes-install.md) |
| EC2 Start         | Scheduled start of predefined EC2 instances              | [EC2 Start](docs/ec2-start.md)                        |
| EC2 Stop          | Scheduled stop of predefined EC2 instances               | [EC2 Stop](docs/ec2-stop.md)                          |
| EC2 Control       | Reusable workflow to on-demand start/stop EC2 Instance   | [EC2 Control](docs/ec2-control.md)                    |
| Postgres Install  | Install Postgres to EKS Cluster                          | [Postgres](docs/postgres.md)                          |
| Consul Install    | Install Consul to EKS Cluster                            | [Consul](docs/consul.md)                              |
| Zookeeper Install | Install Zookeeper to EKS Cluster                         | [Zookeeper](docs/zookeeper.md)                        |
| Kafka Install     | Install Kafka to EKS Cluster                             | [Kafka](docs/kafka.md)                                |

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

Need to contribute? Read the fork workflow: [Fork Sequence Guide](docs/fork-sequence.md).

---

## 📘 Standards & Change Policy
Stable interface & evolution rules (naming, inputs/outputs, version pinning, minimal permissions, security and deprecation) are documented in [docs/standards-and-change-policy.md](docs/standards-and-change-policy.md).

---
## 🤝 Contributing

We welcome contributions from the community! To contribute:

1. Review and sign the [CLA](CLA/cla.md).
2. Check the [CODEOWNERS](CODEOWNERS) file for areas of responsibility.
3. Open an issue to discuss your changes.
- For bug / feature / task use the <u>[Issue Guidelines](docs/issue-guidelines.md)</u> (required fields, templates, labels).
4. Submit a pull request with tests and documentation updates.

> IMPORTANT: Before opening an issue or pull request you MUST read the <u>[Contribution & PR Conduct](docs/code-of-conduct-prs.md)</u> and the <u>[Issue Guidelines](docs/issue-guidelines.md)</u>. They define required issue / PR fields, labels, and formatting.

---

## 📄 License

This project is licensed under the [Apache License 2.0](LICENSE)