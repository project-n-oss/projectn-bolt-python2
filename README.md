# Bolt SDK

This SDK provides an authentication solution for programatically interacting with Bolt. It wraps the boto3 interface so project wide integration is as easy as refactoring `import boto3` to `import bolt as boto3`.

The package affects the signing and routing protocol of the boto3 S3 client, therefore any non S3 clients created through this SDK will be un-affected by the wrapper.

## Prerequisites

The minimum supported version of Python is version 2.

## Installation

```bash
python -m pip install bolt-sdk-py2
```

## Usage

In order to use this package, toy first need to set some environment variables

```bash
export BOLT_CUSTOM_DOMAIN=<YOUR_CUSTOM_DOMAIN>
export BOLT_REGION=<YOUR_BOLT_CLUSTER_REGION>
# Optional if not running on an ec2 instance to force read from a read-replica in this az
export BOLT_AZ_ID='<az-id>'
```

If the region and AZ environment variables aren't specified when running on an EC2 instance, the SDK will use the ec2 metadata api to fetch the instance's region and availability zone id.

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

Import the logging and set default level to `DEBUG`.

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```
