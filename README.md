# Bolt SDK

This SDK provides an authentication solution for programatically interacting with Bolt. It wraps the boto3 interface so project wide integration is as easy as refactoring `import boto3` to `import bolt as boto3`.

The package affects the signing and routing protocol of the boto3 S3 client, therefore any non S3 clients created through this SDK will be un-affected by the wrapper.

## Prerequisites

The minimum supported version of Python is version 3.

## Installation

```bash
python3 -m pip install bolt-sdk
```

## Configuration

For the client to work it must have knowledge of Bolt's *service discovery url* (`BOLT_URL`) and Bolt's *server hostname* (`BOLT_HOSTNAME`)
These are parameterized by the *region* of Bolt's deployment. A preferred *availability zone ID* can also be provided for AZ-aware routing.

**There are two  ways to expose Bolt's URL to the SDK:**
1. Declare the ENV variable: `BOLT_CUSTOM_DOMAIN`, which constructs Bolt URL and hostname based on default naming
```bash
export BOLT_CUSTOM_DOMAIN="example.com"
```

2. Directly declare the ENV variables: `BOLT_URL` and `BOLT_HOSTNAME`
`BOLT_URL` must be formatted as follows:

`https://<subdomain>{region}<domain>`

An example is:

`https://bolt.{region}.google.com`

Where the `{region}` within the URL is a string literal placeholder that will be replaced by the python sdk

```bash
export BOLT_URL="<url>"
export BOLT_HOSTNAME="<url>"
```

**There are two ways to expose Bolt's region/preferred availability zone to the SDK:**

1. If running on an EC2 instance the SDK will by default use that instance's region and zone ID
2. With the ENV variables: `AWS_REGION` and `AWS_ZONE_ID`.
```bash
export AWS_REGION='<region>'
export AWS_ZONE_ID='<az-id>'
```

## Debugging

Import the default logger and set its level to DEBUG

`logging.getLogger().setLevel(logging.DEBUG)`


## Tests
Basic integration tests are provided for the modified Session/Client interfaces. They must be run in an environment with a properly configured Bolt deployment accessible.
```bash
python3 tests/tests.py
```
