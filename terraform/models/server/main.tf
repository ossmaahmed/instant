data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

resource "aws_security_group" "jenkins" {
  name        = "${var.name}-sg"
  description = "Access rules for the Jenkins instance."
  vpc_id      = var.vpc_id

  tags = {
    Name = "${var.name}-sg"
  }
}

resource "aws_vpc_security_group_ingress_rule" "jenkins_http" {
  security_group_id = aws_security_group.jenkins.id
  description       = "Jenkins web interface."
  cidr_ipv4         = var.access_cidr
  from_port         = 8080
  to_port           = 8080
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "ssh" {
  count = var.key_name == null ? 0 : 1

  security_group_id = aws_security_group.jenkins.id
  description       = "SSH administration."
  cidr_ipv4         = var.access_cidr
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.jenkins.id
  description       = "Allow outbound traffic for package installation and updates."
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_iam_role" "ssm" {
  name = "${var.name}-ssm-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Name = "${var.name}-ssm-role"
  }
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Lets the Jenkins pipelines log in to ECR and push images without static credentials.
resource "aws_iam_role_policy_attachment" "ecr" {
  role       = aws_iam_role.ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser"
}

resource "aws_iam_instance_profile" "ssm" {
  name = "${var.name}-instance-profile"
  role = aws_iam_role.ssm.name
}

resource "aws_instance" "jenkins" {
  ami                         = data.aws_ami.amazon_linux.id
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [aws_security_group.jenkins.id]
  associate_public_ip_address = var.associate_public_ip
  key_name                    = var.key_name
  iam_instance_profile        = aws_iam_instance_profile.ssm.name

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  tags = {
    Name         = var.name
    AnsibleGroup = "jenkins"
  }

  depends_on = [aws_iam_role_policy_attachment.ssm]

  lifecycle {
    ignore_changes = [ami]
  }
}