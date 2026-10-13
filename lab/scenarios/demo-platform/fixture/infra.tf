resource "aws_s3_bucket" "assets" {
  bucket = "acme-assets"
  acl    = "public-read"
  tags   = { team = "web" }
}
