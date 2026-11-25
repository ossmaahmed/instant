terraform {
  backend "s3" {
    bucket       = "osama-ivolve-tfstate-2026"
    key          = "ivolve/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}
