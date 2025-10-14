# ec2-control
 
## 🔍 Overview
**Reusable workflow, that is used to remotely start-stop AWS EC2 instances on-demand**

---

## 📘 How to use
1. Create action in your repository with following contents

        jobs:
          start-ec2:
            uses: Netcracker/qubership-terraform-hub/.github/workflows/ec2-control.yml@main
            with:
              instance_id: ${{ vars.AWS_GITHUB_RUNNER_ID }} #Instance ID to manage state
              action: 'start' # Action to perform, start or stop is expected
            secrets:
              AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }} # AWS Credentials with EC2 instance permissions
              AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }} # AWS Credentials with EC2 instance permissions

2. Fill in following secrets and variables:

| Type      | Name                               | Description                                   |
|-----------|------------------------------------|-----------------------------------------------|
| Secret    | AWS_ACCESS_KEY_ID                  | AWS Credentials with EC2 instance permissions |
| Secret    | AWS_SECRET_ACCESS_KEY              | AWS Credentials with EC2 instance permissions |
| Variable  | AWS_GITHUB_RUNNER_ID               | EC2 Instance ID                               |

3. Run action as standalone workflow or as part of another workflow.

---