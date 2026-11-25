variable "cluster_name" {
  description = "Name of the EKS cluster."
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version for the EKS control plane."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnet IDs spread across two Availability Zones."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) == 2
    error_message = "The EKS node group requires exactly two private subnets."
  }
}

variable "public_access_cidrs" {
  description = "CIDRs allowed to reach the public EKS API endpoint."
  type        = list(string)
}

variable "node_instance_type" {
  description = "Instance type used for EKS worker nodes."
  type        = string
}

variable "desired_node_count" {
  description = "Desired number of EKS worker nodes."
  type        = number
  default     = 2
}

variable "min_node_count" {
  description = "Minimum number of EKS worker nodes."
  type        = number
  default     = 2
}

variable "max_node_count" {
  description = "Maximum number of EKS worker nodes."
  type        = number
  default     = 2
}
