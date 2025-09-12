resource "aws_ec2_instance_state" "stop_opensearch_runner" {
  instance_id = var.OPENSEARCH_RUNNER_ID
  state       = "stopped"

}
