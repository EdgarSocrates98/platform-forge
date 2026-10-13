resource "aws_s3_bucket" "public_assets" {
  bucket = "acme-public-assets"
  acl    = "public-read"
  tags   = { team = "web", cost_center = "web" }
}
