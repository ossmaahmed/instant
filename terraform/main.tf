module "network" {
  source = "./models/vpc"

  vpc_cidr             = var.vpc_cidr
  vpc_name             = var.vpc_name
  aws_region           = var.aws_region
  availability_zones   = var.availability_zones
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  jenkins_access_cidr  = var.jenkins_access_cidr
  cluster_name         = var.cluster_name
}

module "jenkins" {
  source = "./models/server"

  name                = var.jenkins_name
  vpc_id              = module.network.vpc_id
  subnet_id           = module.network.public_subnet_ids[0]
  instance_type       = var.jenkins_instance_type
  key_name            = var.jenkins_key_name
  access_cidr         = var.jenkins_access_cidr
  associate_public_ip = true
}

module "eks" {
  source = "./models/eks"

  depends_on = [module.network]

  cluster_name        = var.cluster_name
  kubernetes_version  = var.kubernetes_version
  subnet_ids          = module.network.private_subnet_ids
  public_access_cidrs = [var.jenkins_access_cidr]
  node_instance_type  = var.eks_node_instance_type
  desired_node_count  = 3
  min_node_count      = 2
  max_node_count      = 3
}

module "ecr" {
  source = "./models/ecr"

  repository_name = var.ecr_repository_name
}