resource "aws_launch_template" "qubership" {
  name_prefix   = "qubership"
  image_id      = var.image_id
  instance_type = var.instance_type
}

resource "aws_autoscaling_group" "qubership" {
  capacity_rebalance  = true
  desired_capacity    = 4
  max_size            = 6
  min_size            = 2
  name                = "qubership"
  vpc_zone_identifier = module.vpc.private_subnets

  mixed_instances_policy {
    instances_distribution {
      on_demand_base_capacity                  = 0
      on_demand_percentage_above_base_capacity = 25
      spot_allocation_strategy                 = "capacity-optimized"
    }

    launch_template {
      launch_template_specification {
        launch_template_id = aws_launch_template.qubership.id
      }

      override {
        instance_type     = var.instance_type
        weighted_capacity = "3"
      }

      override {
        instance_type     = "c3.large"
        weighted_capacity = "2"
      }
    }
  }
}

resource "aws_iam_role" "eks_worker_node" {
  name = "eks-worker-node-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action    = "sts:AssumeRole"
        Effect    = "Allow"
        Principal = { Service = "ec2.amazonaws.com" }
      },
    ]
  })
}


resource "aws_iam_role_policy_attachment" "eks_worker_node_policies" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  ])

  role       = aws_iam_role.eks_worker_node.name
  policy_arn = each.value
}

resource "aws_launch_template" "spot_launch_template" {
  name_prefix   = "spot-instance-"
  instance_type = var.instance_type
  image_id      = var.image_id

  # Spot instance configuration
  instance_market_options {
    market_type = "spot"

    spot_options {
      max_price                      = "0.05" # Maximum bid price per hour
      spot_instance_type             = "one-time" # Use "persistent" for persistent requests
      instance_interruption_behavior = "terminate"
    }
  }
  tag_specifications {
    resource_type = "instance"

    tags = {
      Name = "SpotInstance"
    }
  }
}

resource "aws_security_group" "allow_ssh" {
  name        = "allow_ssh"
  description = "Allow SSH access"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["79.132.140.0/24"] # Fornex VPN
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_iam_instance_profile" "eks_worker_profile" {
  name = "eks-worker-profile"
  role = aws_iam_role.eks_worker_node.name
}

data "aws_ami" "eks_optimized" {
  most_recent = true

  filter {
    name   = "name"
    values = ["amazon-eks-node-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  owners = ["602401143452"] # Amazon EKS AMI owner ID
}
