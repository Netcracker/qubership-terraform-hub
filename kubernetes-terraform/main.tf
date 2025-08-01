terraform {
  backend "s3" {
    bucket = "state-storage-terraform"  # Имя вашего бакета
    key = "github-test/kubernetes-install.tfstate"  # Путь к файлу состояния
    region  = "us-east-1"
  }
}
provider "aws" {
  region = var.region
}
data "aws_availability_zones" "available" {
  # Exclude local zones
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

locals {
  name   = var.EKS_NEW_CLUSTERNAME
#  spot_price = data.aws_ec2_spot_price.current.spot_price + data.aws_ec2_spot_price.current.spot_price * 0.02

  vpc_cidr = var.vpc_cidr
  azs      = slice(data.aws_availability_zones.available.names, 0, 3)

  tags = {
    project    = local.name
    Environment = "dev"
    requestor   = "Red-Team"
  }
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = local.name
  cidr = local.vpc_cidr

  azs             = local.azs
  private_subnets = [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 4, k)]
  public_subnets  = [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 8, k + 48)]
  intra_subnets   = [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 8, k + 52)]

  enable_nat_gateway = true
  single_nat_gateway = true

  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
  }

  tags = local.tags
}


# Create EKS Cluster
module "eks_al2023" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.EKS_NEW_CLUSTERNAME
  cluster_version = "1.33"

  # EKS Addons
  cluster_addons = {
  #  coredns                = {}
    eks-pod-identity-agent = {}
    kube-proxy             = {}
    vpc-cni                = {}
  }

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  tags = local.tags
}

