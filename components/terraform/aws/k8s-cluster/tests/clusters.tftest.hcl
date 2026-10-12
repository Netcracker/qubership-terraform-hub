# Offline check (no AWS access): terraform init -backend=false && terraform test
# Plans the component for an adopted cluster (clusters/<name>.yaml) and for a regular one.

mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = { names = ["us-east-1a", "us-east-1b", "us-east-1c"] }
  }
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }
  mock_data "aws_partition" {
    defaults = { partition = "aws", dns_suffix = "amazonaws.com" }
  }
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012", arn = "arn:aws:iam::123456789012:user/ci" }
  }
  mock_data "aws_iam_session_context" {
    defaults = { issuer_arn = "arn:aws:iam::123456789012:user/ci" }
  }
}
mock_provider "tls" {}
mock_provider "time" {}
mock_provider "null" {}
mock_provider "cloudinit" {}

run "adopted_cluster" {
  command = plan
  variables { cluster_name = "Qubership-pioneer" }
  assert {
    condition     = output.vpc_id == "vpc-03fee08f5aa5940a3" && length(module.vpc.private_subnets) == 0
    error_message = "cluster file is not applied: the cluster must use the shared VPC and create no network"
  }
}

run "adopted_cluster_in_shared_vpc" {
  command = plan
  variables { cluster_name = "api-hub-demo" }
  assert {
    condition     = length(module.vpc.private_subnets) == 0
    error_message = "a cluster with vpc.id in its file must not create a network"
  }
}

run "regular_cluster" {
  command = plan
  variables { cluster_name = "some-new-cluster" }
  assert {
    condition     = module.vpc.name == "some-new-cluster"
    error_message = "a cluster without a file must get the component defaults"
  }
}
