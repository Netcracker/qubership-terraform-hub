data "aws_ami" "ubuntu" {

  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/*"]
  }

  filter {
    name = "virtualization-type"
    values = ["hvm"]
  }

  owners = ["099720109477"]
}

resource "aws_network_interface" "github_runner_vpc" {
  subnet_id   = "subnet-0368c7276a5ec6f92"
  #private_ips = ["172.16.10.100"]

  tags = {
    Name = "github_runner_network_interface",
    cost-usage = "github-runner"
  }
}

#output "test" {
#  value = data.aws_ami.ubuntu
#}
resource "aws_instance" "test" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t3a.nano"
  key_name = "ec2_eks_id_rsa"
  #associate_public_ip_address = false

  primary_network_interface {
    network_interface_id = aws_network_interface.github_runner_vpc.id
  }

  user_data = <<-EOL
  #!/bin/bash -xe
  #apt update
  #mkdir actions-runner && cd actions-runner
  curl -o actions-runner-linux-x64-2.328.0.tar.gz -L https://github.com/actions/runner/releases/download/v2.328.0/actions-runner-linux-x64-2.328.0.tar.gz
  tar xzf ./actions-runner-linux-x64-2.328.0.tar.gz
  ./config.sh --url https://github.com/Netcracker/qubership-terraform-hub --token BNVUPA5ZGJWY77ATSWD3CJLIZLF4E --ephemeral
  ./run.sh
  EOL

  tags = {
    Name = "Ephemeral-runner-test",
    cost-usage = "github-runner"
  }
}