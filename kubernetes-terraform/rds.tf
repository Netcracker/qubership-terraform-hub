# # Create Security Group for RDS
# resource "aws_security_group" "rds_sg" {
#   name        = "rds-security-group"
#   description = "Security group for RDS instance"

#   ingress {
#     description = "Allow Postgres access"
#     from_port   = 5432
#     to_port     = 5432
#     protocol    = "tcp"
#     cidr_blocks = ["79.132.140.0/24"] # Fornex VPN server IP
#   }

#   egress {
#     from_port   = 0
#     to_port     = 0
#     protocol    = "-1"
#     cidr_blocks = ["0.0.0.0/0"]
#   }
# }

# # RDS Subnet Group
# resource "aws_db_subnet_group" "rds_subnet_group" {
#   name       = "rds-subnet-group"
#   subnet_ids = module.vpc.private_subnets

#   tags = {
#     Name = "rds-subnet-group"
#   }
# }

# module "security_group" {
#   source  = "terraform-aws-modules/security-group/aws"
#   version = "~> 5.0"

#   name        = local.name
#   description = "Complete PostgreSQL example security group"
#   vpc_id      = module.vpc.vpc_id

#   # ingress
#   ingress_with_cidr_blocks = [
#     {
#       from_port   = 5432
#       to_port     = 5432
#       protocol    = "tcp"
#       description = "PostgreSQL access from within VPC"
#     }
#   ]
# }

# # RDS Instance
# resource "aws_db_instance" "rds_instance" {
#   allocated_storage    = 20
#   max_allocated_storage = 100 # Enables autoscaling of storage
#   engine               = "postgres" 
#   engine_version       = "16.3"
#   instance_class       = "db.t3.micro"
#   username             = var.rds_master_username
#   password             = var.rds_master_password
#   db_subnet_group_name = aws_db_subnet_group.rds_subnet_group.name
#   vpc_security_group_ids = [module.security_group.security_group_id]
  

#   publicly_accessible = false
#   multi_az            = false # Single node; set to true for Multi-AZ deployments
#   skip_final_snapshot = true

#   tags = {
#     Name = "rds-instance"
#   }
# }

# output "rds_endpoint" {
#   description = "The RDS instance endpoint"
#   value       = aws_db_instance.rds_instance.endpoint
# }

# output "rds_instance_id" {
#   description = "The RDS instance ID"
#   value       = aws_db_instance.rds_instance.id
# }