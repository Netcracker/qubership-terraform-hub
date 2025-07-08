resource "aws_ec2_instance_state" "stop_github_runner" {
  instance_id = var.GITHUB_RUNNER_ID
  state       = "stopped"
}

resource "aws_ec2_instance_state" "stop_opensearch_runner" {
  instance_id = var.OPENSEARCH_RUNNER_ID
  state       = "stopped"
}