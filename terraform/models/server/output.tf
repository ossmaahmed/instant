output "instance_id" {
  description = "ID of the Jenkins EC2 instance."
  value       = aws_instance.jenkins.id
}

output "public_ip" {
  description = "Public IPv4 address of the Jenkins instance."
  value       = aws_instance.jenkins.public_ip
}

output "public_dns" {
  description = "Public DNS name of the Jenkins instance."
  value       = aws_instance.jenkins.public_dns
}
