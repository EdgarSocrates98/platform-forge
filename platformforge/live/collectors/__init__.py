"""Live collectors — read-only provider observation (cycle §15–§39).

Every collector is pure logic over an injected `transport` callable;
the actual host call (kubectl subprocess, boto3 session) lives in
`transport.py` modules which are the ONLY network boundary.
"""
