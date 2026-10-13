resource "aws_security_group" "web" {
  name = "web-sg"
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_s3_bucket" "data" {
  bucket = "corp-data"
}
resource "aws_db_instance" "db" {
  engine         = "postgres"
  instance_class = "db.t3.micro"
  storage_encrypted = false
}
