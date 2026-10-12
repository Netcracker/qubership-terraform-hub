output "vpc_id" {
  description = "The ID of the VPC."
  value       = module.vpc.vpc_id
}

output "public_subnets" {
  description = "The public subnets."
  value       = module.vpc.public_subnets
}

output "private_subnets" {
  description = "The private subnets (what clusters put into vpc.subnet_ids)."
  value       = module.vpc.private_subnets
}
