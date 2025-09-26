# EC2 Start/Stop

## 🔍 Overview
**A Workflow, that start/stops EC2 instances and scales EKS clusters on schedule**

---

## 📘 How to use
1. Fork Repository
2. Fill in following secrets and variables:

| Type      | Name                               | Description                                |
|-----------|------------------------------------|--------------------------------------------|
| Secret    | AWS_ACCESS_KEY_ID                  | AWS credentials, used for cloud connection |
| Secret    | AWS_SECRET_ACCESS_KEY              | AWS credentials, used for cloud connection |
| Variable  | AWS_REGION                         | Region for new cluster                     |
| Variable  | vars.TF_VAR_Pioneer_ASG_NAME       | Name of Auto Scale Group Name to manage    |
| Variable  | vars.TF_VAR_OPENSEARCH_RUNNER_ID   | EC2 Instance Name to manage                |

3. Edit workflow file (ec2-start.yaml/ec2-stop.yaml) and include/exclude needed instances/ASG
4. Set schedule to run action, cron syntax is used
Example: 

        0 9 * * 1-5
Will run at 9am Mon-Fri

---