# An IAM user for use by GitHub Actions; access keys are stored as organization secrets.
resource "aws_iam_user" "ops_github" {
  name = "fantasy-github"
}

#Pushing layers to S3

data "aws_iam_policy_document" "push_layers_to_s3" {
  statement {
    effect = "Allow"
    actions = [
      "s3:PutObjectACL",
      "s3:PutObject",
      "s3:ListBucket",
      "s3:GetObject",
      "s3:DeleteObject",
      "s3:CreateMultipartUpload"
    ]
    resources = [
      "${aws_s3_bucket.fantasy_project.arn}/layers/*",
      aws_s3_bucket.fantasy_project.arn
    ]
  }
}

resource "aws_iam_policy" "push_layers_to_s3" {
  name   = "push-fantasy-layers-to-s3"
  policy = data.aws_iam_policy_document.push_layers_to_s3.json
}

resource "aws_iam_user_policy_attachment" "ops_github_push_layers_to_s3" {
  user       = aws_iam_user.ops_github.name
  policy_arn = aws_iam_policy.push_layers_to_s3.arn
}
