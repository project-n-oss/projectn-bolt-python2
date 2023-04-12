# Bolt SDK

This SDK provides an authentication solution for programatically interacting with Bolt. It wraps the boto3 interface so project wide integration is as easy as refactoring `import boto3` to `import bolt as boto3`.

The package affects the signing and routing protocol of the boto3 S3 client, therefore any non S3 clients created through this SDK will be un-affected by the wrapper.

## Prerequisites

The minimum supported version of Python is version 2.

## Installation

```bash
python -m pip install bolt-sdk-py2
```

## Configuration

For the client to work it must have knowledge of Bolt's *service discovery url* (`BOLT_URL`)
These are parameterized by the *region* of Bolt's deployment. A preferred *availability zone ID* can also be provided for AZ-aware routing.

**Expose Bolt's URL to the SDK:**
1. Declare the ENV variable: `BOLT_CUSTOM_DOMAIN`, which constructs Bolt URL and hostname based on default naming
```bash
export BOLT_CUSTOM_DOMAIN="example.com"
```


**There are two ways to expose Bolt's region/preferred availability zone to the SDK:**

1. If running on an EC2 instance the SDK will by default use that instance's region and zone ID
2. With the ENV variables: `AWS_REGION` and `AWS_ZONE_ID`.
```bash
export AWS_REGION='<region>'
export AWS_ZONE_ID='<az-id>'
```
## Example usage

```python
import bolt
# Create an S3 client
s3_client = bolt.client("s3")
# Define a function that performs the put_object operation
s3_client.put_object(Body="data", Bucket="BUCKET_NAME", Key="key")
obj = s3_client.get_object(Bucket="BUCKET_NAME", Key="key")
body = obj["Body"].read()
```
## Debugging

Import the default logger and set its level to DEBUG

`logging.getLogger().setLevel(logging.DEBUG)`


