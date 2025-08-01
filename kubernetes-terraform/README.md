# Kubernetes-Terraform

This folder contains terraform code for automating creation of kubernetes cluster in AWS

---

## How to use
Create following secrets and variables

## Secrets and variables, required for installation

| Name                          | Purpose                                                                              |
| ----------------------------- | ------------------------------------------------------------------------------------ |
| AWS_ACCESS_KEY_ID             | Acceess key id from AWS user                                                         |
| AWS_SECRET_ACCESS_KEY         | Access key secret from AWS user                                                      |
| AWS_REGION                    | AWS region, where new cluster will reside                                            |
| TF_VAR_EKS_NEW_CLUSTERNAME    | Name for new cluster                                                                 |
| TF_VAR_PG_INSTALL_NAMESPACE   | Namespace where Postgress will be installed                                          |

## Workflow run

- Navigate to actions > Kubernetes and Infra Install > Run workflow
- Select neccessary actions and list of infra components to install
- Issue Run Workflow

### Current limitations and planned improvements

- rework tf state storage to bucket_name/cluster_name
- change tf state storage user to separate AWS use
- change infra components action run logic to call different actions
- include all infra components into checkbox
- improve k8s installation tf steps to include ingress creation
- implement inventory file and example (default) settings file
