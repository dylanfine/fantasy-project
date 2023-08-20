terraform {

  backend "s3" {
    bucket = "dylan-tf-bucket"
    key    = "fantasy_project.json"
    region = "us-east-2"
  }
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.11.0"
    }
  }
}

# Configure the AWS Provider
provider "aws" {

  region = "us-east-2"
}

