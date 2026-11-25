output "jenkins_url" {
  description = "Jenkins web interface URL."
  value       = "http://${module.jenkins.public_dns}:8080"
}

output "jenkins_instance_id" {
  description = "Jenkins EC2 instance ID."
  value       = module.jenkins.instance_id
}

output "eks_cluster_name" {
  description = "EKS cluster name."
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "EKS API endpoint."
  value       = module.eks.cluster_endpoint
}

output "ecr_repository_url" {
  description = "ECR image repository URL."
  value       = module.ecr.repository_url
}

output "private_subnet_ids" {
  description = "Private subnet IDs hosting EKS worker nodes."
  value       = module.network.private_subnet_ids
}
output "alb_controller_role_arn" {
  value = module.eks.alb_controller_role_arn
}