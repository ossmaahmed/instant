# Jenkins EC2 configuration with Ansible

The playbook configures running Amazon Linux 2023 Jenkins instances with Java 17, Jenkins, Docker, and Trivy. The configuration is split into reusable Ansible roles.

## Prerequisites

- Terraform has been applied and the instance is running.
- Ansible is installed on the control machine.
- The control machine has AWS credentials with `ec2:DescribeInstances` access, the `amazon.aws` collection, and the Python `boto3`/`botocore` packages installed for dynamic inventory.
- The Jenkins EC2 instance has an EC2 key pair configured in Terraform and its private key is available to SSH. Terraform must allow SSH from the control machine's IP.
- The control machine can reach the instance over SSH.

The EC2 instance is tagged `AnsibleGroup=jenkins` by Terraform. Dynamic inventory uses that tag and the `us-east-1` region from `terraform/terraform.tfvars`; update `inventory/aws_ec2.yml` if the Terraform region changes. AWS credentials are resolved using the standard AWS SDK credential chain.

## Install collection and run

From this directory:

```shell
python -m pip install boto3 botocore
ansible-galaxy collection install -r requirements.yml
ansible-inventory --graph
ansible-playbook site.yml --private-key <path-to-ec2-private-key>
```

The inventory connects as `ec2-user` using each instance's public IP. For a key already configured in SSH, omit `--private-key`. Ansible privilege escalation is enabled by the playbook.

After the play succeeds, Jenkins is available on port 8080. Retrieve the initial administrator password on the instance with:

```shell
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```

The Docker role adds the Jenkins service account to the `docker` group so Jenkins jobs can use Docker, then restarts Jenkins so its service process receives the updated group membership.
