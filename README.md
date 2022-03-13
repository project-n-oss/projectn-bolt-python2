# Bolt SDK

This SDK provides an authentication solution for programatically interacting with Bolt. It wraps the boto3 interface so project wide integration is as easy as refactoring `import boto3` to `import bolt as boto3`.

The package affects the signing and routing protocol of the boto3 S3 client, therefore any non S3 clients created through this SDK will be un-affected by the wrapper.

## Prerequisites

The minimum supported version of Python is version 3.

## Installation

```git clone git@github.com:project-n-oss/projectn-bolt-python.git```

Copy the module to the appropriate location based in your Python version. For example,

```cp -r bolt/ /usr/lib/python3.7/site-packages/```

## Configuration

For the client to work it must have knowledge of Bolt's *region* and *url*, as well as preferred *availability zone ID*

The URL must be formatted as follows:

`https://<subdomain>{region}<domain>`

An example is:

`https://bolt.{region}.google.com`

Where the `{region}` within the URL is a string literal placeholder that will be replaced by the python sdk

**There are two  ways to expose Bolt's URL to the SDK:**

1. Declare the ENV variables: `BOLT_URL` and `BOLT_HOSTNAME`

```bash
export BOLT_URL="<url>"
export BOLT_HOSTNAME="<url>"
```
2. Declare the ENV variable: `BOLT_CUSTOM_DOMAIN`, which constructs Bolt URL and hostname based on default naming
```bash
export BOLT_CUSTOM_DOMAIN="example.com"
```
**There are two ways to expose Bolt's location to the SDK:**

1. If running on an EC2 instance the SDK will by default use that instance's region and zone ID
2. With the ENV variables: `AWS_REGION` and `AWS_ZONE_ID`.
```bash
export AWS_REGION='<region>'
export AWS_ZONE_ID='<az-id>'
```

## Debugging

Import the default logger and set its level to DEBUG

`logging.getLogger().setLevel(logging.DEBUG)`
