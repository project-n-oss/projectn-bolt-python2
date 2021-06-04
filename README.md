# Bolt SDK

This SDK provides an authentication solution for programatically interacting with Bolt. It wraps the boto3 interface so project wide integration is as easy as refactoring `import boto3` to `import bolt as boto3`.

The package affects the signing and routing protocol of the boto3 S3 client, therefore any non S3 clients created through this SDK will be un-affected by the wrapper.

## Prerequisites

The minimum supported version of Python is version 3.

## Installation

`python3 -m pip install bolt-sdk`

## Configuration

For the client to work it must have knowledge of Bolt's *region* and *url*

The URL must be formatted as follows:

`https://<subdomain>{region}<domain>`

An example is:

`https://bolt.{region}.google.com`

Where the `{region}` within the URL is a string literal placeholder that will be replaced by the python sdk

**To expose Bolt's URL to the SDK:**

1. Declare the ENV variable: `BOLT_URL`

```bash
export BOLT_URL="<url>"
```

**There are two ways to expose Bolt's region to the SDK:**

1. If running on an EC2 instance the SDK will by default use that EC2s region
2. With the ENV variable: `AWS_REGION`.
```bash
export AWS_REGION='<region>'
```

## Debugging

Import the default logger and set its level to DEBUG

`logging.getLogger().setLevel(logging.DEBUG)`
