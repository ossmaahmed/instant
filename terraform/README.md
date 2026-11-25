# iVolve AWS infrastructure

This Terraform configuration creates:

- A VPC with two public and two private subnets in separate Availability Zones, an internet gateway, a single NAT gateway, route tables, and public/private network ACLs.
- A Jenkins EC2 instance in a public subnet, with a security group and an SSM instance role.
- An EKS cluster and a managed node group with two workers in the private subnets.
- The Amazon EBS CSI driver add-on and node permissions for provisioning EBS-backed Kubernetes volumes.
- Amazon VPC CNI network-policy enforcement for Kubernetes NetworkPolicy resources.
- A private ECR repository with image scanning and a 30-image lifecycle policy.
- An encrypted S3 Terraform state backend with S3-native state locking.

## Prerequisites

- Terraform 1.10 or later.
- AWS credentials with permissions to create the resources in these modules.
- An existing S3 bucket named `backend` in `us-east-1`, with versioning enabled. The caller needs access to the state object and its `.tflock` lock object. The backend bucket is not created by this configuration.
- An EC2 key pair in `us-east-1` if SSH access to Jenkins is needed.

If `terraform init` returns `403 Forbidden`, confirm that the bucket exists in the intended AWS account and region and that the active AWS identity can access it. The least-privilege policy in `backend-access-policy.json` must be attached to the Terraform caller by an AWS administrator. If the bucket belongs to another account, its owner must also allow cross-account access. Do not switch to local state as a workaround for an S3 access denial.

## Configure and deploy

Review `terraform.tfvars` before applying. Replace `jenkins_access_cidr` with a trusted IP range instead of `0.0.0.0/0`; this range controls Jenkins access and the EKS public API endpoint. Set `jenkins_key_name` in `terraform.tfvars` to an existing EC2 key pair name to enable SSH ingress; otherwise administer the instance through Systems Manager Session Manager.

From this directory:

```shell
terraform init
terraform fmt -recursive
terraform validate
terraform plan
terraform apply
```

The Jenkins EC2 instance intentionally has no `user_data`; configure it after applying Terraform using the role-based Ansible playbook in [`../ansible/README.md`](../ansible/README.md). Set `jenkins_key_name` to an existing EC2 key pair and allow SSH from the Ansible control machine's trusted IP range in `jenkins_access_cidr`. The playbook's dynamic inventory discovers the running instance by its `AnsibleGroup=jenkins` tag.

After the Ansible playbook completes, Jenkins is available at the `jenkins_url` output. The default EC2 instance types are `t3.small`; AWS instance free-tier eligibility depends on the account's offer and usage, and EKS control-plane, NAT gateway, and other resources can still incur charges.

Configure kubectl after applying:

```shell
aws eks update-kubeconfig --region us-east-1 --name ivolve-eks
```

The NAT gateway is shared by the private subnets to reduce cost; it is a single-AZ egress dependency. The EKS public API endpoint and Jenkins HTTP endpoint are reachable only from the CIDRs configured in `terraform.tfvars`.
