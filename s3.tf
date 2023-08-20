resource "aws_s3_bucket" "fantasy_project" {
  bucket        = "dylan-andrew-fantasy-project"
  acl           = "private"
  force_destroy = true

}

resource "aws_s3_bucket_public_access_block" "fantasy_project" {
  bucket                  = aws_s3_bucket.fantasy_project.id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true

}
