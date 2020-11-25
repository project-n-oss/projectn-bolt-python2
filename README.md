# bolt-python-sdk

This SDK provides an authentication and authorization solution for programatically interacting with Bolt. It wraps the boto3 interface so project wide integration is as easy as refactoring `import boto3` to `import bolt as boto3`. 

The package only effects the signing and routing protocol of the boto3 S3 client, so any non S3 clients created through this SDK will by un-affected by the wrapper.

## Prerequisites

The minimum supported version of Python is version 3.

## Installation

`python3 -m pip install bolt-python-sdk`

## Configuration

There are two ways to expose Bolt's URL to the SDK:

1. With the ENV variable: `BOLT_URL`
```bash
export BOLT_URL='<url>'
```

2. By passing in the argument `bolt_url` to either of these functions. (Will override ENV variable)
```python
import bolt as boto3
boto3.client('s3', bolt_url='<url>')
# or
boto3.Session().client('s3', bolt_url='<url>')
```
