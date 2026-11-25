variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
}

variable "vpc_name" {
  description = "Name prefix for the VPC resources."
  type        = string
}

variable "aws_region" {
  description = "AWS region used to resolve the EC2 API endpoint service name."
  type        = string
}

variable "availability_zones" {
  description = "Two Availability Zones for the subnets."
  type        = list(string)
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets."
  type        = list(string)
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets."
  type        = list(string)
}

variable "jenkins_access_cidr" {
  description = "CIDR allowed to access Jenkins in the public subnet."
  type        = string
}

variable "cluster_name" {
  description = "EKS cluster name used for subnet discovery tags."
  type        = string
}