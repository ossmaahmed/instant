variable "name" {
  description = "Name of the Jenkins EC2 instance and related resources."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where the Jenkins instance will be placed."
  type        = string
}

variable "subnet_id" {
  description = "Public subnet ID for the Jenkins instance."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type for Jenkins."
  type        = string
}

variable "key_name" {
  description = "Optional existing EC2 key pair name; enables SSH ingress when set."
  type        = string
  default     = null
  nullable    = true
}

variable "access_cidr" {
  description = "CIDR allowed to access Jenkins on port 8080 and SSH when enabled."
  type        = string
}

variable "associate_public_ip" {
  description = "Whether to associate a public IPv4 address with the instance."
  type        = bool
  default     = true
}
