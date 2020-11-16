"""
Simple wrapper of boto3 client.
Bolt will do some special stuff in the background to ensure that:
- Signing is disabled
?## - Addressing style is == to path

- Implement a hook which intercepts request ()
    cli.register_last('before-send.s3', Bolt.send)
- Splits bolt url into parts
- adds custom header
    prepared_request.headers['X-Bolt-Identity-Request'] = get_session().create_client('sts').generate_presigned_url(
        'get_caller_identity', ExpiresIn=10)

Only intercepts for s3 commands.
Parse the BOLT url from the environment (or some other way) possibly KW args.
"""

from urllib.parse import urlsplit, urlunsplit

import boto3
from boto3 import Session
from botocore.handlers import disable_signing
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.session import get_session

def client(*args, **kwargs):
  # If client specifies 's3' service then mutate request for Bolt.
  # Otherwise, return an unmodified client.

  if kwargs.get('session_name') == 's3' or 's3' in args:
    session = Session(profile_name='nobolt')
    creds = session.get_credentials()

    # Use inner function to curry 'creds' into callback
    def inject_header(*args, **kwargs):
      bolt_url='https://bolt.turing-aws-gxxq.bolt.projectn.co'  # Remove Hardcoded Bolt URL

      # Modify request URL to redirect to bolt
      scheme, host, _, _, _ = urlsplit(bolt_url)
      prepared_request = kwargs['request']
      _, _, path, query, fragment = urlsplit(prepared_request.url)
      prepared_request.url = urlunsplit((scheme, host, path, query, fragment))

      # Sign a get-caller-identity request
      REGION='us-east-2' # Get session region
      method='GET'
      url = 'https://sts.amazonaws.com/'
      data = 'Action=GetCallerIdentity&Version=2011-06-15'
      request = AWSRequest(method=method, url=url, data=data, params=None, headers=None)
      SigV4Auth(creds, "sts", REGION).add_auth(request)

      # Pass signed STS headers into Bolt request
      # Needs: "X-Amz-Security-Token"
      for key in ["X-Amz-Date", "Authorization"]:
        prepared_request.headers[key] = request.headers[key]

    session.events.register_last('before-send.s3', inject_header)
    session.events.register(
      'choose-signer', disable_signing, unique_id='bolt-disable-signing')

    return session.client('s3')

  else:
    return boto3.client(*args, **kwargs)



s3 = client('s3')
print(s3.list_buckets())
