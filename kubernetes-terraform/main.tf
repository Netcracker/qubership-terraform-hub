terraform {
  backend "s3" {
    bucket = "state-storage-terraform"  # Bucket name
    key = "kubernetes-install.tfstate"  # State filename
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
  projectname   = var.EKS_NEW_CLUSTERNAME
#  spot_price = data.aws_ec2_spot_price.current.spot_price + data.aws_ec2_spot_price.current.spot_price * 0.02

  vpc_cidr = var.vpc_cidr
  azs      = slice(data.aws_availability_zones.available.names, 0, 3)

  tags = {
    project    = local.projectname
    Environment = "dev"
    requestor   = "Red-Team"
    created-by  = "Terraform-CI"
    cost-usage = local.projectname
  }
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = local.projectname
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

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.0"

  name    = local.projectname
  kubernetes_version = "1.33"
  upgrade_policy = {
    support_type = "STANDARD"
  }

  # EKS Addons
  addons = {
    coredns                = {}
    eks-pod-identity-agent = {
      before_compute = true
    }
    kube-proxy             = {}
    vpc-cni                = {
      before_compute = true
    }
    aws-ebs-csi-driver = {
      most_recent              = true
      service_account_role_arn = module.ebs_csi_irsa_role.iam_role_arn
    }
    }

    endpoint_public_access = true
    enable_cluster_creator_admin_permissions = true
    create_cloudwatch_log_group = false

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  eks_managed_node_groups = {
      name = {
      # Starting on 1.30, AL2023 is the default AMI type for EKS managed node groups
      name           = local.projectname
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = ["m6i.large"]
      capacity_type  = "SPOT"

      min_size     = 3
      max_size     = 4
      desired_size = 3
    }
  }
  tags = local.tags
}

module "ebs_csi_irsa_role" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name             = "ebs-csi"
  attach_ebs_csi_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"]
    }
  }
}