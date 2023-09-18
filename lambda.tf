data "aws_iam_policy_document" "policy_data" {

  statement {
    effect    = "Allow"
    actions   = ["*"]
    resources = ["*"]

  }

}

data "aws_iam_policy_document" "iam_lambda_service" {

  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }

}

resource "aws_iam_policy" "lambda_role_policy" {
  name   = "fantasy_lambda_role_policy"
  policy = data.aws_iam_policy_document.policy_data.json
}

resource "aws_iam_role" "lambda_role" {
  name               = "fantasy_lambda_role"
  assume_role_policy = data.aws_iam_policy_document.iam_lambda_service.json
}

resource "aws_iam_role_policy_attachment" "lambda_policy_attachment" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_role_policy.arn

}


data "archive_file" "zip_lambda" {
  type        = "zip"
  source_dir  = "${path.module}/python/code/"
  output_path = "${path.module}/python/zips/script.zip"
}


resource "aws_cloudwatch_event_rule" "daily-cloudwatch" {
  name = "everyday"

  schedule_expression = "cron(30 6 * * ? *)"

}

data "aws_s3_object" "layers_zip" {
  bucket = aws_s3_bucket.fantasy_project.id
  key    = "layers/lambda_deployment.zip"
}

resource "aws_lambda_layer_version" "lambda_layer" {
  s3_bucket           = data.aws_s3_object.layers_zip.bucket
  s3_key              = data.aws_s3_object.layers_zip.key
  s3_object_version   = data.aws_s3_object.layers_zip.version_id
  layer_name          = "python_layer"
  compatible_runtimes = ["python3.8"]
  source_code_hash    = data.aws_s3_object.layers_zip.metadata.Hash
}

resource "aws_lambda_function" "financial_analysis" {

  filename         = data.archive_file.zip_lambda.output_path
  function_name    = "fantasy_project"
  handler          = "script.lambda_handler"
  runtime          = "python3.8"
  role             = aws_iam_role.lambda_role.arn
  source_code_hash = data.archive_file.zip_lambda.output_base64sha256
  timeout          = 600
  layers           = [aws_lambda_layer_version.lambda_layer.arn]

  environment {
    variables = {
      DEV_MODE = "production",
    }
  }
}

resource "aws_cloudwatch_event_target" "cloudwatch_to_lambda" {
  rule = aws_cloudwatch_event_rule.daily-cloudwatch.name
  arn  = aws_lambda_function.financial_analysis.arn

}

resource "aws_lambda_permission" "cloudwatch-perm" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.financial_analysis.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily-cloudwatch.arn
}

#FOR SECRETS MANAGER ROTATION

# data "archive_file" "zip_lambda_rotator" {
#   type        = "zip"
#   source_dir  = "${path.module}/python/secrets_rotater/"
#   output_path = "${path.module}/python/zips/secrets_rotater.zip"
# }

# resource "aws_lambda_function" "secrets_rotater" {
#   filename         = data.archive_file.zip_lambda_rotator.output_path
#   function_name    = "secrets_rotater"
#   handler          = "script.lambda_handler"
#   runtime          = "python3.8"
#   role             = aws_iam_role.lambda_role.arn
#   source_code_hash = data.archive_file.zip_lambda_rotator.output_base64sha256
#   timeout          = 30
#   layers           = [aws_lambda_layer_version.lambda_layer.arn]
# }

# resource "aws_lambda_permission" "secrets-perm" {
#   action        = "lambda:InvokeFunction"
#   function_name = aws_lambda_function.secrets_rotater.function_name
#   principal     = "secretsmanager.amazonaws.com"
#   source_arn    = data.aws_secretsmanager_secret.fantasy_project_api.arn
# }
