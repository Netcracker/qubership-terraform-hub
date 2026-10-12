variable "name" {
  description = "The name of the VPC (prefix of subnet and route table names)."
  type        = string
}

variable "region" {
  description = "The AWS region of the VPC."
  default     = "us-east-1" # N.Virginia
}

variable "cidr" {
  description = "The CIDR block for the VPC."
  default     = "10.0.0.0/16"
}

variable "manage_defaults" {
  description = "Adopt the default security group, route table and network ACL. Keep false for a VPC that was not created here."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags for every resource of the VPC."
  type        = map(string)
  default     = {}
}

variable "subnet_tags" {
  description = "Extra tags for the public and private subnets, e.g. kubernetes.io/cluster/<name> = shared."
  type        = map(string)
  default     = {}
}
