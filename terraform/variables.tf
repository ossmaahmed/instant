variable "aws_region" {
  description = "AWS region for the infrastructure."
  type        = string
}

variable "vpc_name" {
  description = "Name prefix for the network resources."
  type        = string
  default     = "instant"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Two Availability Zones used by the public and private subnets."
  type        = list(string)

  validation {
    condition     = length(var.availability_zones) == 2
    error_message = "Exactly two Availability Zones are required."
  }
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for the two public subnets."
  type        = list(string)

  validation {
    condition     = length(var.public_subnet_cidrs) == 2
    error_message = "Exactly two public subnet CIDRs are required."
  }
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for the two private subnets."
  type        = list(string)

  validation {
    condition     = length(var.private_subnet_cidrs) == 2
    error_message = "Exactly two private subnet CIDRs are required."
  }
}

variable "jenkins_name" {
  description = "Name of the Jenkins EC2 instance."
  type        = string
  default     = "instant-jenkins"
}

variable "jenkins_instance_type" {
  description = "EC2 instance type used by Jenkins."
  type        = string
  default     = "t3.small"
}

variable "jenkins_key_name" {
  description = "Optional existing EC2 key pair name for SSH access."
  type        = string
  default     = null
  nullable    = true
}

variable "jenkins_access_cidr" {
  description = "CIDR allowed to access Jenkins on ports 8080 and 22."
  type        = string
}

variable "cluster_name" {
  description = "Name of the EKS cluster."
  type        = string
  default     = "instant-eks"
}

variable "kubernetes_version" {
  description = "Kubernetes version for the EKS control plane."
  type        = string
  default     = "1.34"
}

variable "eks_node_instance_type" {
  description = "EC2 instance type for the EKS managed node group."
  type        = string
  default     = "t3.small"
}

variable "ecr_repository_name" {
  description = "Name of the ECR image repository."
  type        = string
  default     = "instant-app"
}